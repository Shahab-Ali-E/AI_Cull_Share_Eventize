# from datetime import datetime, timedelta
# from uuid import uuid4
# from PIL import Image
# import io
# from utils.generateEmeddings import generate_embeddings
# from sklearn.metrics.pairwise import cosine_similarity
# from config.settings import get_settings
# import time
# settings = get_settings()

# async def separate_duplicate_images(images:list, root_folder:str, inside_root_main_folder:str, folder_id:int, S3_util_obj, task, prev_image_metadata:list=[]):
#     start_time = time.time()  # Start profiling
#     all_images_metadata = prev_image_metadata
#     total_img_len = len(images)
#     print("total len of images",total_img_len)
#     image_embeddings = []
#     duplicate = set()

#     for idx,image in enumerate(images):
#         image_start_time = time.time()
#         try:
#             # Image embeddings generation
#             content = image['content']
#             name = image['name']
#             image_pil = Image.open(io.BytesIO(content)).convert('RGB')
#             embeddings = generate_embeddings(image_name=name, image_pillow_obj=image_pil)
#             image_embeddings.append({**embeddings,'content': content, 'content_type':image['content_type']})

#         except Exception as e:
#             raise Exception(f"Error processing image:{str(e)}")
        
#         # Log time for each image processing
#         print(f"Image embedding {idx + 1} processed in {time.time() - image_start_time:.2f} seconds")

#         #calculating 25% of progress
#         progress = round(((idx + 1) / total_img_len) * 33.3,2 )
#         task.update_state(state='PROGRESS', meta={'progress': progress, 'info': 'Duplicate image separation processing'})

        
#     # Compute cosine similarity between each pair of embeddings
#     # Step 2: Detect duplicates
#     num_embeddings = len(image_embeddings)
#     similarity_checks_done =0
#     total_similarity_checks = num_embeddings * (num_embeddings - 1) // 2 # n(n−1)/2 

#     for i in range(num_embeddings):
#         for j in range(i + 1, num_embeddings):
#             start_time = time.time()
#             embeddings_i = image_embeddings[i]['embeddings']
#             embeddings_j = image_embeddings[j]['embeddings']

#             cosine_similarity_result = cosine_similarity([embeddings_i], [embeddings_j])[0][0] * 100
            
#             # Log time taken for each comparison
#             comparison_time = time.time() - start_time
#             print(f"Comparison between image {i} and image {j} took {comparison_time:.4f} seconds")
#             print(f'Similarity between image {i} and image {j} is {cosine_similarity_result}')
            
#             if cosine_similarity_result > settings.BLUR_IMAGE_THRESHOLD:
#                 print('len of img_data',len([image_embeddings[i], image_embeddings[j]]))
#                 for img_data in [image_embeddings[i], image_embeddings[j]]:
#                     if img_data['name'] not in duplicate:  # Prevent duplicate addition
#                         duplicate.add(img_data['name'])
#                     # Uploading the duplicate image content to S3
#                     try:
#                         await S3_util_obj.upload_smart_cull_images(
#                             root_folder=root_folder, 
#                             main_folder=inside_root_main_folder, 
#                             upload_image_folder=settings.DUPLICATE_FOLDER,
#                             image_data=io.BytesIO(img_data['content']),
#                             filename=filename
#                         )
#                     except Exception as e:
#                         raise Exception(f"Error uploading image to S3: {str(e)}")
                    
#                     # generating presinged url so user can download image
#                     key = f"{root_folder}/{inside_root_main_folder}/{settings.DUPLICATE_FOLDER}/{filename}"
#                     presigned_url = await S3_util_obj.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)
#                     # prepare metadata of uploaded images to save into database
#                     image_metadata = {
#                         'id': str(uuid4()),#filename,
#                         'name': img_data['name'],
#                         'images_download_path': 'https://google.com',#presigned_url,
#                         'file_type': img_data['content_type'],
#                         'detection_status':'Duplicate',
#                         'images_download_validity':datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
#                         'culling_folder_id': folder_id
#                     }
#                     all_images_metadata.append(image_metadata)
#             # Update progress for cosine similarity computation
#             similarity_checks_done += 1
#             progress = round(33.3 + ((similarity_checks_done / total_similarity_checks) * 33.3), 2)
#             task.update_state(state='PROGRESS', meta={'progress': progress, 'info': 'Duplicate image separation processing'})

#     #Lastly all good images uploaded to s3 and prepare it's metadata
#     non_duplicate = [img_data for img_data in image_embeddings if img_data['name'] not in duplicate]      
#     # for index, img_data in enumerate(non_duplicate):
#     #     filename = f"{uuid4()}__{img_data['name']}"
#     for index,img_data in enumerate(non_duplicate):
#         if img_data['name'] not in duplicate:
#             # Uploading the duplicate image content to S3
#             try:
#                 await S3_util_obj.upload_smart_cull_images(
#                     root_folder=root_folder, 
#                     main_folder=inside_root_main_folder, 
#                     upload_image_folder=settings.FINE_COLLECTION_FOLDER,
#                     image_data=io.BytesIO(img_data['content']),
#                     filename=filename
#                 )
#             except Exception as e:
#                 raise Exception(f"Error uploading image to S3: {str(e)}")
            
#             # generating presinged url so user can download image
#             key = f"{root_folder}/{inside_root_main_folder}/{settings.FINE_COLLECTION_FOLDER}/{filename}"
#             presigned_url = await S3_util_obj.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)
#         # prepare metadata of uploaded images to save into database
#             image_metadata = {
#                 'id': str(uuid4()), #filename,
#                 'name': img_data['name'],
#                 'images_download_path': 'https://google.com',#presigned_url,
#                 'detection_status':'FineCollection',
#                 'file_type': img_data['content_type'],
#                 'images_download_validity':datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
#                 'culling_folder_id': folder_id
#             }
#             all_images_metadata.append(image_metadata)
#         # Update progress for good image uploading
#         if task:
#             progress = round(66.6 + (((index + 1) / len(non_duplicate)) * 33.3), 2)
#             task.update_state(state='PROGRESS', meta={'progress': progress, 'info': 'Duplicate image separation processing'})
#             print(progress)

#     task.update_state(state='SUCCESS', meta={'progress': 100, 'info': 'Duplicate image separation done!'})
#     # time.sleep(1)
#     return {
#         'status': 'SUCCESS',
#         'images_metadata':all_images_metadata,
#     }

# from datetime import datetime, timedelta
# from uuid import uuid4
# from PIL import Image
# import io
# from dependencies.mlModelsManager import ModelManager
# from utils.generateEmeddings import generate_embeddings
# from sklearn.metrics.pairwise import cosine_similarity
# from tensorflow.keras.applications.resnet50 import preprocess_input # type: ignore
# from config.settings import get_settings
# import time

# settings = get_settings()
# models = ModelManager.get_models(settings)
# blur_image_model = models['blur_detect_model']

# async def separate_duplicate_images(images, root_folder, inside_root_main_folder, folder_id, S3_util_obj, task, prev_image_metadata=[]):
#     start_time = time.time()
#     all_images_metadata = prev_image_metadata
    

#     # Step 1: Generate embeddings
#     image_embeddings = []
#     for idx, image in enumerate(images):
#         try:
#             start_emb_time = time.time()
#             content = image['content']
#             name = image['name']
#             image_pil = Image.open(io.BytesIO(content)).convert('RGB')
#             embeddings = generate_embeddings(image_name=name, image_pillow_obj=image_pil)
#             image_embeddings.append({**embeddings, 'content': content, 'content_type': image['content_type'], 'name': name})
#             print(f"Embedding for Image {idx + 1}/{len(images)} generated in {time.time() - start_emb_time:.2f} seconds.")
#         except Exception as e:
#             raise Exception(f"Error generating embedding for image {image['name']}: {str(e)}")

#         progress = round(((idx + 1) / len(images)) * 20, 2)
#         task.update_state(state='PROGRESS', meta={'progress': progress, 'info': 'Generating image embeddings'})

#     # Step 2: Compare images and detect duplicates
#     num_images = len(image_embeddings)
#     duplicates = set()

#     for i in range(num_images):
#         for j in range(i + 1, num_images):
#             start_cmp_time = time.time()
#             embeddings_i = image_embeddings[i]['embeddings']
#             embeddings_j = image_embeddings[j]['embeddings']
#             cosine_sim = cosine_similarity([embeddings_i], [embeddings_j])[0][0] * 100
#             print(f"Comparison between Image {i + 1} and Image {j + 1} took {time.time() - start_cmp_time:.4f} seconds.")
#             print(f"Similarity between Image {i + 1} and Image {j + 1}: {cosine_sim:.2f}%.")

#             if cosine_sim > settings.BLUR_IMAGE_THRESHOLD:
#                 duplicates.add(image_embeddings[i]['name'])
#                 duplicates.add(image_embeddings[j]['name'])
#                 print(f"Duplicate detected: Image {image_embeddings[i]['name']} and Image {image_embeddings[j]['name']}.")

#     # Step 3: Upload duplicates to S3
#     for img_data in image_embeddings:
#         if img_data['name'] in duplicates:
#             filename = f"{uuid4()}__{img_data['name']}"
#             try:
#                 await S3_util_obj.upload_smart_cull_images(
#                     root_folder=root_folder,
#                     main_folder=inside_root_main_folder,
#                     upload_image_folder=settings.DUPLICATE_FOLDER,
#                     image_data=io.BytesIO(img_data['content']),
#                     filename=filename
#                 )
#                 print(f"Duplicate image {img_data['name']} uploaded to S3.")
#                 # generating presinged url so user can download image
#                 key = f"{root_folder}/{inside_root_main_folder}/{settings.DUPLICATE_FOLDER}/{filename}"
#                 presigned_url = await S3_util_obj.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)
#             except Exception as e:
#                 raise Exception(f"Error uploading duplicate image {img_data['name']} to S3: {str(e)}")

#             metadata = {
#                 'id': filename,
#                 'name': img_data['name'],
#                 'images_download_path': presigned_url,  # Replace with presigned URL
#                 'file_type': img_data['content_type'],
#                 'detection_status': 'Duplicate',
#                 'images_download_validity': datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
#                 'culling_folder_id': folder_id
#             }
#             all_images_metadata.append(metadata)

#     # Step 4: Upload good images to S3
#     for img_data in image_embeddings:
#         if img_data['name'] not in duplicates:
#             filename = f"{uuid4()}__{img_data['name']}"
#             try:
#                 await S3_util_obj.upload_smart_cull_images(
#                     root_folder=root_folder,
#                     main_folder=inside_root_main_folder,
#                     upload_image_folder=settings.FINE_COLLECTION_FOLDER,
#                     image_data=io.BytesIO(img_data['content']),
#                     filename=filename
#                 )
#                 print(f"Good image {img_data['name']} uploaded to S3.")
                
#                 # generating presinged url so user can download image
#                 key = f"{root_folder}/{inside_root_main_folder}/{settings.FINE_COLLECTION_FOLDER}/{filename}"
#                 presigned_url = await S3_util_obj.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)
                
#             except Exception as e:
#                 raise Exception(f"Error uploading good image {img_data['name']} to S3: {str(e)}")

#             metadata = {
#                 'id': filename,
#                 'name': img_data['name'],
#                 'images_download_path': presigned_url,  # Replace with presigned URL
#                 'file_type': img_data['content_type'],
#                 'detection_status': 'FineCollection',
#                 'images_download_validity': datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
#                 'culling_folder_id': folder_id
#             }
#             all_images_metadata.append(metadata)

#     task.update_state(state='SUCCESS', meta={'progress': 100, 'info': 'Duplicate image separation completed'})
#     print(f"Total time taken: {time.time() - start_time:.2f} seconds.")
#     return {'status': 'SUCCESS', 'images_metadata': all_images_metadata}


from datetime import datetime, timedelta
from uuid import uuid4
import io
from tensorflow.keras.applications.resnet50 import preprocess_input  # type: ignore
from sklearn.metrics.pairwise import cosine_similarity
from PIL import Image
import numpy as np
from tensorflow.keras.applications import ResNet50
from src.config.settings import get_settings
from src.dependencies.mlModelsManager import ModelManager
import os
import time

settings = get_settings()
models = ModelManager.get_models(settings)
duplicate_model = models['duplicate_image_detection_model']

# Function to extract features from an image
def extract_features_from_image(image_pillow_obj, model):
    img = image_pillow_obj.resize((224, 224))
    img_array = np.array(img)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = preprocess_input(img_array)
    features = model.predict(img_array)
    return features.flatten()


async def separate_duplicate_images(
    images_path, root_folder, inside_root_main_folder, folder_id, S3_util_obj, task, prev_image_metadata=[]
):
    start_time = time.time()
    all_images_metadata = prev_image_metadata.copy()
    total_images = len(images_path)
    processed_files = set()

    # Step 1: Generate embeddings from local files
    image_features = []
    for idx, image in enumerate(images_path):
        try:
            start_emb_time = time.time()
            image_path = image['local_path']
            image_name = image['name']
            
            # Load image directly from disk
            with Image.open(image_path) as image_pil:
                features = extract_features_from_image(
                    image_pillow_obj=image_pil.convert("RGB"), 
                    model=duplicate_model
                )
            
            image_features.append({
                'name': image_name,
                'features': features,
                'local_path': image_path,
                'content_type': image['content_type']
            })
            
            print(f"Features for Image {idx + 1}/{total_images} extracted in {time.time() - start_emb_time:.2f}s")
            
            # Update progress
            progress = round(((idx + 1) / total_images) * 33.3, 2)
            task.update_state(
                state="PROGRESS",
                meta={"progress": progress, "info": f"Processing {image_name}"}
            )

        except Exception as e:
            task.update_state(
                state="PROGRESS",
                meta={"progress": progress, "info": f"Error processing {image_name}: {str(e)}"}
            )
            continue

    # Step 2: Detect duplicates using cosine similarity
    duplicates = set()
    if image_features:
        try:
            features_matrix = np.array([x['features'] for x in image_features])
            similarity_matrix = cosine_similarity(features_matrix)
            
            for i in range(len(image_features)):
                for j in range(i + 1, len(image_features)):
                    if similarity_matrix[i][j] > settings.BLUR_IMAGE_THRESHOLD:
                        duplicates.add(image_features[i]['name'])
                        duplicates.add(image_features[j]['name'])
                        
                # Update progress
                progress = round(33.3 + ((i + 1) / len(image_features)) * 33.3, 2)
                task.update_state(
                    state="PROGRESS",
                    meta={"progress": progress, "info": "Analyzing similarities"}
                )
        except Exception as e:
            task.update_state(
                state="PROGRESS",
                meta={"progress": 66.6, "info": f"Similarity analysis failed: {str(e)}"}
            )

    # Step 3: Process duplicates and non-duplicates
    async def process_image(img_data, is_duplicate):
        try:
            file_path = img_data['local_path']
            if file_path in processed_files:
                return None

            # Read content just before upload
            with open(file_path, 'rb') as f:
                content = f.read()

            # Upload to appropriate folder
            folder_type = settings.DUPLICATE_FOLDER if is_duplicate else settings.FINE_COLLECTION_FOLDER
            filename = f"{uuid4()}__{img_data['name']}"
            
            await S3_util_obj.upload_smart_cull_images(
                root_folder=root_folder,
                main_folder=inside_root_main_folder,
                upload_image_folder=folder_type,
                image_data=io.BytesIO(content),
                filename=filename
            )

            # Generate presigned URL
            key = f"{root_folder}/{inside_root_main_folder}/{folder_type}/{filename}"
            presigned_url = await S3_util_obj.generate_presigned_url(
                key, 
                expiration=settings.PRESIGNED_URL_EXPIRY_SEC
            )

            # Cleanup local file
            os.remove(file_path)
            processed_files.add(file_path)

            return {
                "id": filename,
                "name": img_data['name'],
                "file_type": img_data['content_type'],
                "detection_status": "Duplicate" if is_duplicate else "FineCollection",
                "image_download_path": presigned_url,
                "image_download_validity": datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
                "culling_folder_id": folder_id,
            }
        except Exception as e:
            task.update_state(
                state="PROGRESS",
                meta={"progress": progress, "info": f"Failed {img_data['name']}: {str(e)}"}
            )
            return None

    # Process all images
    for idx, img_data in enumerate(image_features):
        is_dup = img_data['name'] in duplicates
        metadata = await process_image(img_data, is_dup)
        if metadata:
            all_images_metadata.append(metadata)

        # Update progress
        progress = round(66.6 + ((idx + 1) / len(image_features)) * 33.3, 2)
        task.update_state(
            state="PROGRESS",
            meta={"progress": progress, "info": "Finalizing uploads"}
        )

    # Cleanup any remaining files
    for img in images_path:
        if img['local_path'] not in processed_files and os.path.exists(img['local_path']):
            os.remove(img['local_path'])

    task.update_state(
        state="SUCCESS",
        meta={"progress": 100, "info": "Duplicate processing complete"}
    )
    
    print(f"Total time: {time.time() - start_time:.2f}s")
    return {
        "status": "SUCCESS",
        "images_metadata": all_images_metadata
    }


