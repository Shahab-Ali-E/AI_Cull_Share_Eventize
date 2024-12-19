from datetime import datetime, timedelta
from uuid import uuid4
from PIL import Image
import io
from utils.generateEmeddings import generate_embeddings
from sklearn.metrics.pairwise import cosine_similarity
from config.settings import get_settings
import time
settings = get_settings()

async def separate_duplicate_images(images:list, root_folder:str, inside_root_main_folder:str, folder_id:int, S3_util_obj, task, prev_image_metadata:list=[]):
    all_images_metadata = prev_image_metadata
    total_img_len = len(images)
    image_embeddings = []
    duplicate = set()

    for idx,image in enumerate(images):
        try:
            # Image embeddings generation
            content = image['content']
            name = image['name']
            image_pil = Image.open(io.BytesIO(content)).convert('RGB')
            embeddings = generate_embeddings(image_name=name, image_pillow_obj=image_pil)
            image_embeddings.append({**embeddings,'content': content, 'content_type':image['content_type']})

        except Exception as e:
            raise Exception(f"Error processing image:{str(e)}")
        
        #calculating 25% of progress
        progress = round(((idx + 1) / total_img_len) * 33.3,2 )
        task.update_state(state='PROGRESS', meta={'progress': progress, 'info': 'Duplicate image separation processing'})

        
    # Compute cosine similarity between each pair of embeddings
    num_embeddings = len(image_embeddings)
    similarity_checks_done =0
    total_similarity_checks = num_embeddings * (num_embeddings - 1) // 2 #n(n−1)/2 

    for i in range(num_embeddings):
        for j in range(i+1, num_embeddings):
            embeddings_i = image_embeddings[i]['embeddings']
            embeddings_j = image_embeddings[j]['embeddings']

            cosine_similarity_result = cosine_similarity([embeddings_i], [embeddings_j])[0][0] * 100
            #if image to be duplicate then upload them to s3 and prepare their metadata
            if cosine_similarity_result > settings.BLUR_IMAGE_THRESHOLD:
                for img_data in [image_embeddings[i], image_embeddings[j]]:
                    duplicate.add(img_data['name'])
                    filename = f"{uuid4()}__{img_data['name']}"
                    # Uploading the duplicate image content to S3
                    try:
                        await S3_util_obj.upload_smart_cull_images(
                            root_folder=root_folder, 
                            main_folder=inside_root_main_folder, 
                            upload_image_folder=settings.DUPLICATE_FOLDER,
                            image_data=io.BytesIO(img_data['content']),
                            filename=filename
                        )
                    except Exception as e:
                        raise Exception(f"Error uploading image to S3: {str(e)}")
                    
                    #generating presinged url so user can download image
                    key = f"{root_folder}/{inside_root_main_folder}/{settings.DUPLICATE_FOLDER}/{filename}"
                    presigned_url = await S3_util_obj.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)
                    #prepare metadata of uploaded images to save into database
                    image_metadata = {
                        'id': filename,
                        'name': img_data['name'],
                        'images_download_path': presigned_url,
                        'file_type': img_data['content_type'],
                        'detection_status':'ClosedEye',
                        'images_download_validity':datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
                        'culling_folder_id': folder_id
                    }
                    all_images_metadata.append(image_metadata)
            # Update progress for cosine similarity computation
            similarity_checks_done += 1
            progress = round(33.3 + ((similarity_checks_done / total_similarity_checks) * 33.3), 2)
            task.update_state(state='PROGRESS', meta={'progress': progress, 'info': 'Duplicate image separation processing'})

    #Lastly all good images uploaded to s3 and prepare it's metadata
    non_duplicate = [img_data for img_data in image_embeddings if img_data['name'] not in duplicate]        
    for index, img_data in enumerate(non_duplicate):
        filename = f"{uuid4()}__{img_data['name']}"
        # Uploading the duplicate image content to S3
        try:
            await S3_util_obj.upload_smart_cull_images(
                root_folder=root_folder, 
                main_folder=inside_root_main_folder, 
                upload_image_folder=settings.FINE_COLLECTION_FOLDER,
                image_data=io.BytesIO(img_data['content']),
                filename=filename
            )
        except Exception as e:
            raise Exception(f"Error uploading image to S3: {str(e)}")
        
        #generating presinged url so user can download image
        key = f"{root_folder}/{inside_root_main_folder}/{settings.FINE_COLLECTION_FOLDER}/{filename}"
        presigned_url = await S3_util_obj.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)
        #prepare metadata of uploaded images to save into database
        image_metadata = {
            'id': filename,
            'name': img_data['name'],
            'images_download_path': presigned_url,
            'detection_status':'FineCollection',
            'file_type': img_data['content_type'],
            'images_download_validity':datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
            'culling_folder_id': folder_id
        }
        all_images_metadata.append(image_metadata)
        # Update progress for good image uploading
        if task:
            progress = round(66.6 + (((index + 1) / len(non_duplicate)) * 33.3), 2)
            task.update_state(state='PROGRESS', meta={'progress': progress, 'info': 'Duplicate image separation processing'})
            print(progress)

    task.update_state(state='SUCCESS', meta={'progress': 100, 'info': 'Duplicate image separation done!'})
    # time.sleep(1)
    return {
        'status': 'SUCCESS',
        'images_metadata':all_images_metadata,
    }
