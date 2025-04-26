import asyncio
import os
import time
from model.CullingImagesMetaData import ImagesMetaData, TemporaryImageURL
from services.Culling.separateBlurImages import separate_blur_images
from config.settings import get_settings
from services.Culling.separateClosedEye import ClosedEyeDetection
from config.syncDatabase import celery_sync_session
from services.Culling.separateDuplicateImages import separate_duplicate_images
from utils.UpsertMetaDataToDB import insert_image_metadata
from utils.CustomExceptions import SignatureDoesNotMatch, URLExpiredException, UnauthorizedAccess
from utils.S3Utils import S3Utils
from Celery.utils import create_celery
import requests
from sqlalchemy import delete, select
from model.CullingFolders import CullingFolder
from celery import chain
from sqlalchemy.orm.attributes import flag_modified

#-----instances----
celery = create_celery()
settings = get_settings()
s3_utils = S3Utils(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_region=settings.AWS_REGION,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    bucket_name=settings.AWS_BUCKET_SMART_CULL_NAME,
                    aws_endpoint_url=settings.AWS_ENDPOINT_URL)


#----------------------FOR BULK INSERT ALL IMAGES RECORD IN DATABASE-------------------------------
# Helper function to perform bulk saving
def bulk_save(images_record: list, folder_id:str):
    if not images_record:
        raise Exception('No images found to insert into the database')

    try:
        with celery_sync_session() as db_session:
            response = insert_image_metadata(
                db_session=db_session,
                bulk_insert_fields=images_record,
                model=ImagesMetaData
            )
            if response.get('status') == 'COMPLETED':
                folder = db_session.scalar(select(CullingFolder).where(
                    CullingFolder.id == folder_id
                ))
                
                # Check if folder exists
                if folder:
                    # updating folder data
                    folder.culling_done = True
                    folder.culling_in_progress = False
                    folder.culling_task_ids=[]
                    flag_modified(folder, "culling_task_ids")
                    
                    # deleting temp images record
                    db_session.execute(delete(TemporaryImageURL).where(
                        TemporaryImageURL.culling_folder_id == folder_id
                    ))
                else:
                    # Handle case where user is not found, e.g., log an error or raise an exception
                    print(f"folder with id {folder} not found.")
                
                    
                db_session.commit()
                return response

    except Exception as e:
        print(f"Error during bulk insert: {e}")
        raise
        

#---------------------Independenst Task For Culling------------------------------------------------

#This task is used to get images from AWS server from the link which have provided as param to it 
@celery.task(name='get_images_from_aws', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':5}, queue='culling')
def get_images_from_aws(self, uploaded_images_url:list, local_folder_path):
    images = []
    # Ensure event folder exists
    os.makedirs(local_folder_path, exist_ok=True)

    # Create 'images' directory inside event folder
    path_to_save_images = os.path.join(local_folder_path, "images")
    os.makedirs(path_to_save_images, exist_ok=True)  # Safe directory creation

    for index, image_url in enumerate(uploaded_images_url):
        try:
            # Stream download to avoid memory overload
            response = requests.get(image_url, stream=True)
            response.raise_for_status()  # Check HTTP errors first

            # Extract filename and content type
            image_name = image_url.split("/")[-1].split('?')[0]
            content_type = f'image/{image_name.split(".")[-1]}'
            
            # Local file path
            local_path = os.path.join(path_to_save_images, image_name)
            
            # Save image to disk
            # with open(image_path, 'wb') as img_file:
            #     img_file.write(image_content)
                
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Get file size from disk (more accurate)
            image_size = os.path.getsize(local_path)
            
            # Store metadata + local path
            images.append({
                'name': image_name,
                'content_type': content_type,
                'size': image_size,
                'local_path':local_path
            })
            # images.append(local_path)

            # Update progress
            progress = ((index + 1) / len(uploaded_images_url)) * 100
            self.update_state(
                state='PROGRESS',
                meta={"progress": progress, "info": f"Downloaded {image_name}"}
            )
            time.sleep(0.1)  # Optional: For progress visualization

        except requests.exceptions.HTTPError as e:
            # Improved error handling using status codes
            if response.status_code == 403:
                raise URLExpiredException(f"Expired URL: {image_url}")
            elif response.status_code == 404:
                raise SignatureDoesNotMatch(f"Invalid signature: {image_url}")
            else:
                raise

    self.update_state(
        state='SUCCESS',
        meta={"progress": 100, "info": "All images downloaded locally"}
    )
    time.sleep(0.4)
    return images  # Returns list of metadata + local paths

# @celery.task(name='get_images', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':5}, queue='culling')
# def get_images(self, uploaded_images_url: list):
#     images = []

#     for index, image_path in enumerate(uploaded_images_url):
#         try:
#             # Normalize path for cross-platform safety
#             image_path = os.path.normpath(image_path)

#             # Read image content from local file
#             with open(image_path, 'rb') as f:
#                 image_content = f.read()

#             # Detect MIME type
#             content_type, _ = mimetypes.guess_type(image_path)
#             if content_type is None:
#                 content_type = 'application/octet-stream'  # fallback

#             image_name = os.path.basename(image_path)
#             image_size = len(image_content)

#             images.append({
#                 'content_type': content_type,
#                 'name': image_name,
#                 'size': image_size,
#                 'content': image_content
#             })

#             progress = ((index + 1) / len(uploaded_images_url)) * 100
#             self.update_state(state='PROGRESS', meta={
#                 "progress": progress,
#                 "info": f"Processing {image_name} ({index + 1}/{len(uploaded_images_url)})"
#             })

#             time.sleep(0.1)  # simulate delay for UI responsiveness

#         except FileNotFoundError:
#             self.update_state(state='FAILURE', meta={
#                 "error": f"File not found: {image_path}"
#             })
#             raise
#         except Exception as e:
#             self.update_state(state='FAILURE', meta={
#                 "error": str(e)
#             })
#             raise

#     self.update_state(state='SUCCESS', meta={
#         "progress": 100,
#         "info": "Images retrieved successfully"
#     })

#     return images

#This task is used to separate blur images and upload them to aws server and finally return non-blur images, blur images metadata
@celery.task(name='blur_image_separation', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':3}, queue='culling')
def blur_image_separation(self, images_path, user_id:str, folder:str, folder_id:int):
    
    print()
    print()
    print()
    print("total images received", len(images_path))
    
    # Validation
    if not folder or not folder_id:
        raise ValueError("Invalid folder or folder_id. Both must be provided.")
    
    if not images_path:
        raise ValueError("No images provided for processing.")

    output_from_blur = asyncio.run (separate_blur_images(
                                                            images_path=images_path,
                                                            root_folder=user_id,
                                                            inside_root_main_folder=folder,
                                                            folder_id=folder_id,
                                                            S3_util_obj=s3_utils,
                                                            task=self
                                                        ))  
    return output_from_blur

#This task is used to separate closed eye images and upload them to aws server and finally return non-closed-eye images, closed-eye images metadata
@celery.task(name='closed_eye_separation', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3}, queue='culling')
def closed_eye_separation(self, output_from_blur:dict, user_id:str, folder:str, folder_id:int):
    non_blur_images = output_from_blur.get('non_blur_images')
    images_metadata = output_from_blur.get('images_metadata')

    if len(non_blur_images)==0 and len(images_metadata)!=0:
        self.update_state(state='SUCCESS', meta={'progress': 100, 'info': "Closed eye images separation completed!"})
        # time.sleep(1)
        return {
            'status': 'closed_eye_warning',
            'message': "No images were found to detect closed eye, only blurred images were processed.",
            'images_metadata': images_metadata
        }
    
    if len(non_blur_images)==0 and len(images_metadata)==0:
        return {
            'status': 'FAILURE',
            'message': 'Error occurred in culling'
        }
    
    print()
    print()
    print()
    print("blur images len", len(images_metadata))
    print("non blur images len", len(non_blur_images))
    
    closed_eye_detect_obj = ClosedEyeDetection(
        S3_util_obj=s3_utils,
        root_folder=user_id,
        inside_root_main_folder=folder,
    )
    result = asyncio.run(closed_eye_detect_obj.separate_closed_eye_images_and_upload_to_s3(     prev_images_metadata=images_metadata,
                                                                                                images_path=non_blur_images, 
                                                                                                task=self, 
                                                                                                folder_id=folder_id
                                                                                            ))
    return result

#This task is used to separate duplicate images and upload them to aws server and finally return fine collection and duplicate images metadata
@celery.task(name='duplicate_image_separation', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3}, queue='culling')
def duplicate_image_separation(self, output_from_closed_eye:dict, user_id:str, folder:str, folder_id:int):
    if output_from_closed_eye.get('status') == 'error':
        return(output_from_closed_eye.get('message'))
    
    if output_from_closed_eye.get('status') == 'closed_eye_warning':
        return output_from_closed_eye
    
    if output_from_closed_eye.get('status')=='SUCCESS':
        if not output_from_closed_eye.get('open_eye_images') and output_from_closed_eye.get('images_metadata'):
            self.update_state(state='SUCCESS', meta={'progress': 100, 'info': "Duplicate images separation completed!"})
            # time.sleep(1)
            return {
                'status': 'duplicate_images_warning',
                'message': "No images were found to detect duplicate, only closed eye and blurred images are processed.",
                'images_metadata': output_from_closed_eye.get('images_metadata')
            }
    print()
    print()
    print()
    print("closed eye detected images len", len(output_from_closed_eye.get('images_metadata')))
    print("non closed eye images len", len(output_from_closed_eye.get('open_eye_images')))
    
    result = asyncio.run(separate_duplicate_images(prev_image_metadata=output_from_closed_eye.get('images_metadata'),
                                                   folder_id=folder_id,
                                                   root_folder=user_id,
                                                   inside_root_main_folder=folder,
                                                   S3_util_obj=s3_utils,
                                                   task=self,
                                                   images_path=output_from_closed_eye.get('open_eye_images')
                                                    ))
    
    print()
    print()
    print('all images metadata len',len(result.get('images_metadata')))
    return result
    


#This task is use to bulk save images metadata into database
@celery.task(name='bulk_save_image_metadata_db', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3}, queue='culling')
def bulk_save_image_metadata_db(self, culled_metadata: dict, folder_id:str):
    try:
        # Check for error status in culled_metadata
        if culled_metadata.get('status') == 'error':
            raise Exception(culled_metadata.get('message'))

        images_to_save = None

        # Decide which metadata to save based on the status
        if culled_metadata.get('status') == 'closed_eye_warning':
            images_to_save = culled_metadata.get('images_metadata')
            print("meta data from closed eye warning", images_to_save)
        elif culled_metadata.get('status') == 'duplicate_images_warning':
            print("meta data from duplicate_images_warning", images_to_save)
            images_to_save = culled_metadata.get('images_metadata')
        elif culled_metadata.get('status') == 'SUCCESS':
            print("SUCCESS METADATA", images_to_save)
            images_to_save = culled_metadata.get('images_metadata')

        # Ensure there's metadata to save
        if images_to_save:
            response = bulk_save(images_record=images_to_save, folder_id=folder_id)
            self.update_state(state='SUCCESS', meta={'progress': 100, 'info': "Images save to database successfully!"})
            # time.sleep(1)
            return response

        return {
            "status": "NO_DATA",
            "message": "No metadata available to save to the database"
        }

    except Exception as e:
        print(f"Error in bulk_save_image_metadata_db: {str(e)}")
        raise
    
# @celery.task_done(name='del_before_cull_images', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3}, queue='culling')
# def del_before_cull_images(self, response_from_database:dict, user_id:str, folder:str):
#     if response_from_database.get('status')=='success' and response_from_database.get('message')=='successfully inserted all metadata to database':
#         response = asyncio.run(
#                 try:
#                 folder_key=f'{user_id}/{folder}/{}'
#                     response = await self.S3.delete_object(
#                                                            folder_key
#                                                         )
#                 except Exception as e:
#                     raise Exception(f"Error uploading image to S3: {str(e)}")
#             )

#-----------------------Chaining All Above Task Here----------------------------------
@celery.task(name='culling_task', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':5}, queue='culling')
def culling_task(self, user_id:str, uploaded_images_url, folder:str, folder_id:str, local_folder_path:str):

    self.update_state(state='STARTED', meta={'status': 'Task started'})
    task_ids=[]
    try:
        # Chain the results
        chain_result = chain(
            get_images_from_aws.s(uploaded_images_url, local_folder_path),
            blur_image_separation.s(user_id, folder, folder_id),
            closed_eye_separation.s(user_id, folder, folder_id),
            duplicate_image_separation.s(user_id, folder, folder_id),
            bulk_save_image_metadata_db.s(folder_id),
        ) 

        result = chain_result.apply_async()

        #to get the task id's of each one in chaining
        task_ids.append(result.id)
        while result.parent:
            result = result.parent
            task_ids.append(result.id)

        task_ids.reverse()  # Reverse to get the correct order of execution
        
        print("\n\n\n task_ids",task_ids)
        clean_ids = [str(tid) for tid in task_ids] 
        
        try:
            with celery_sync_session() as db_session:
                folder_record = db_session.scalar(select(CullingFolder).where(
                    CullingFolder.id == folder_id,
                ))
                if folder_record:
                    folder_record.culling_task_ids    = clean_ids
                    folder_record.culling_in_progress = True
                    db_session.add(folder_record)
                    db_session.commit()

        except Exception as e:
            raise Exception(e)

        self.update_state(state='SUCCESS', meta={'status': 'Culling task executing in background', 'task_ids': task_ids})
    
    except URLExpiredException() as e:
        self.update_state(state='FAILURE', meta={'status': str(e), 'task_ids': task_ids})
        raise
    except Exception as e:
        self.update_state(state='FAILURE', meta={'status': f"Unexpected error: {str(e)}", 'task_ids': task_ids})
        raise

    return {'task_ids': task_ids}




