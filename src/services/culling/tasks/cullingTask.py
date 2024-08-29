import asyncio
import time
from services.Culling.separateBlurImages import separate_blur_images
from fastapi.responses import JSONResponse
from config.settings import get_settings
from services.Culling.separateClosedEye import ClosedEyeDetection
from config.Database import get_db
from services.Culling.separateDuplicateImages import separate_duplicate_images
from utils.UpsertMetaDataToDB import upsert_image_metadata_DB
from utils.CustomExceptions import URLExpiredException
from utils.S3Utils import S3Utils
from Celery.utils import create_celery
import requests
from celery import chain


#-----instances----
celery = create_celery()
settings = get_settings()
s3_utils = S3Utils(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_region=settings.AWS_REGION,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    bucket_name=settings.AWS_BUCKET_SMART_CULL_NAME,
                    aws_endpoint_url=settings.AWS_ENDPOINT_URL)


#----------------------FOR BULK INSERT ALL IMAGES RECORD IN DATABASE-------------------------------
async def bulk_save(images_record:list):
    if not images_record:
        raise Exception('no images found to insert into database')
    
    async for db_session in get_db():
        async with db_session.begin():
            try:
                response = await upsert_image_metadata_DB(db_session=db_session,
                                                            bulk_insert_fields=images_record
                                                            )

                if response.get('status')=='success':
                    await db_session.commit()
                    return response
            except Exception as e:
                    raise Exception(str(e))
        

#---------------------Independenst Task For Culling------------------------------------------------

#This task is used to get images from AWS server from the link which have provided as param to it 
@celery.task(name='get_images_from_aws', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':5}, queue='culling')
def get_images_from_aws(self, uploaded_images_url:list):
    images = []

    for index, image in enumerate(uploaded_images_url):
        response = requests.get(image)
        image_content = response.content
        content_type = 'image/'+ image.split('/')[-1].split('.')[-1].split('?')[0]
        image_name = image.split("/")[-1].split('?')[0]
        image_size = len(image_content)

        if b'<Error>' in image_content and b'<Code>AccessDenied</Code>' in image_content:
            raise URLExpiredException()
        
        else:
            images.append({
                'content_type': content_type,
                'name': image_name,
                'size': image_size,
                'content': image_content
            })
            progress = ((index + 1) / len(uploaded_images_url)) * 100
            self.update_state(state='PROGRESS', meta={"progress": progress, "info": "Getting images to process"})
    
    return images

#This task is used to separate blur images and upload them to aws server and finally return non-blur images, blur images metadata
@celery.task(name='blur_image_separation', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':3}, queue='culling')
def blur_image_separation(self, images, user_id:str, folder:str, folder_id:int):
    # Validation
    if not folder or not folder_id:
        raise ValueError("Invalid folder or folder_id. Both must be provided.")
    
    if not images:
        raise ValueError("No images provided for processing.")

    output_from_blur = asyncio.run (separate_blur_images(
                                                            images=images,
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
    blurred_metadata = output_from_blur.get('images_metadata')

    if len(non_blur_images)==0 and len(blurred_metadata)!=0:
        self.update_state(state='PROGRESS', meta={'progress': 100, 'info': "Closed eye images separation completed!"})
        time.sleep(1)
        return {
            'status': 'closed_eye_warning',
            'message': "No images were found to detect closed eye, only blurred images were processed.",
            'blurred_metadata': blurred_metadata
        }
    
    if len(non_blur_images)==0 and len(blurred_metadata)==0:
        return {
            'status': 'error',
            'message': 'Error occurred in culling'
        }
    
    closed_eye_detect_obj = ClosedEyeDetection(
        S3_util_obj=s3_utils,
        root_folder=user_id,
        inside_root_main_folder=folder,
    )
    result = asyncio.run(closed_eye_detect_obj.separate_closed_eye_images_and_upload_to_s3(     prev_image_metadata=blurred_metadata,
                                                                                                images=non_blur_images, 
                                                                                                task=self, 
                                                                                                folder_id=folder_id
                                                                                            ))
    return result

#This task is used to separate duplicate images and upload them to aws server and finally return fine collection and duplicate images metadata
@celery.task(name='duplicate_image_separation', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3}, queue='culling')
def duplicate_image_separation(self, output_from_closed_eye:dict, user_id:str, folder:str, folder_id:int):
    if output_from_closed_eye.get('status') == 'error':
        return(output_from_closed_eye.get('message'))
    
    if output_from_closed_eye.get('status') == 'warning':
        return output_from_closed_eye
    
    if output_from_closed_eye.get('status')=='success':
        if not output_from_closed_eye.get('open_eye_images', []) and output_from_closed_eye.get('images_metadata', []):
            self.update_state(state='PROGRESS', meta={'progress': 100, 'info': "Duplicate images separation completed!"})
            time.sleep(1)
            return {
                'status': 'blur_image_warning',
                'message': "No images were found to detect duplicate, only closed eye and blurred images were processed.",
                'closed_eye_metadata': output_from_closed_eye.get('closed_eye_metadata', [])
            }
        
    result = asyncio.run(separate_duplicate_images(prev_image_metadata=output_from_closed_eye.get('images_metadata'),
                                                   folder_id=folder_id,
                                                   root_folder=user_id,
                                                   inside_root_main_folder=folder,
                                                   S3_util_obj=s3_utils,
                                                   task=self,
                                                   images=output_from_closed_eye.get('open_eye_images')
                                                    ))
    return result


#This task is use to bulk save images metadata into database
@celery.task(name='bulk_save_image_metadata', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3}, queue='culling') 
def bulk_save_image_metadata_db(self, culled_metadata:dict):
    try:
        if culled_metadata.get('status') == 'error':
            raise Exception(images_metadata.get('message'))
        
        # Handle cases where blurred metadata is present
        if culled_metadata.get('status') == 'closed_eye_warning':
            blurred_metadata = culled_metadata.get('blurred_metadata', [])
            if blurred_metadata:
                # Save only the blurred metadata to the database
                return asyncio.run(bulk_save(images_record=blurred_metadata))
        
        # Handle cases where only blur and closed eye metadata were present
        if culled_metadata.get('status') == 'blur_image_warning':
            closed_eye_metadata = culled_metadata.get('closed_eye_metadata', [])
            if closed_eye_metadata:
                # Save only the closed_eye_ provided to the database
                return asyncio.run(bulk_save(images_record=closed_eye_metadata))

        #Lastly save all metadata to database
        if culled_metadata.get('status') == 'success':
            images_metadata = culled_metadata.get('images_metadata')
            if images_metadata:
                return asyncio.run(bulk_save(images_record=images_metadata))

    except Exception as e:
        raise e
    
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
def culling_task(self, user_id:str, uploaded_images_url, folder:str, folder_id:int):

    self.update_state(state='STARTED', meta={'status': 'Task started'})
    task_ids=[]
    try:
        # Chain the results
        chain_result = chain(
            get_images_from_aws.s(uploaded_images_url),
            blur_image_separation.s(user_id, folder, folder_id),
            closed_eye_separation.s(user_id, folder, folder_id),
            duplicate_image_separation.s(user_id, folder, folder_id),
            bulk_save_image_metadata_db.s(),
            # del_before_cull_images.s()
        ) 

        result = chain_result.apply_async()

        #to get the task id's of each one in chaining
        task_ids.append(result.id)
        while result.parent:
            result = result.parent
            task_ids.append(result.id)

        task_ids.reverse()  # Reverse to get the correct order of execution

        self.update_state(state='SUCCESS', meta={'status': 'Culling task executing in background', 'task_ids': task_ids})
    
    except URLExpiredException() as e:
        self.update_state(state='FAILURE', meta={'status': str(e), 'task_ids': task_ids})
        raise
    except Exception as e:
        self.update_state(state='FAILURE', meta={'status': f"Unexpected error: {str(e)}", 'task_ids': task_ids})
        raise

    return JSONResponse(task_ids)




