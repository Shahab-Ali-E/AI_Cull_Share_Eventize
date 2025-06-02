from datetime import datetime, timedelta
import os
import time
from PIL import Image
import io
import torch
from uuid import uuid4
from src.config.settings import get_settings
from src.dependencies.mlModelsManager import ModelManager

settings = get_settings()

# LABELS
predicted_labels = ['undistorted', 'blurred']
upload_image_folder = settings.BLUR_FOLDER

#models
models = ModelManager.get_models(settings=settings)
feature_extractor = models['feature_extractor']
blur_detect_model = models['blur_detect_model']


async def separate_blur_images(images_path:list, root_folder:str, inside_root_main_folder:str, folder_id:int, S3_util_obj, task):
    non_blur_images = []
    blurred_metadata = []
    total_img_len = len(images_path)
    progress = 0.0

    for index, image_info in enumerate(images_path):
        image_path = image_info['local_path']  # Get path from dict
        image_name = image_info['name']
        content_type = image_info['content_type']
        
        try:
            # Open image from local path
            with open(image_path, 'rb') as f:
                image_file = f.read()
            
            # Load image for processing
            open_images = Image.open(io.BytesIO(image_file)).convert('RGB')
            
            # Prepare model inputs
            inputs = feature_extractor(open_images, return_tensors='pt')
            inputs = {k: v.to(blur_detect_model.device) for k, v in inputs.items()} \
                     if isinstance(inputs, dict) else inputs.to(blur_detect_model.device)

            # Model prediction
            with torch.no_grad():
                outputs = blur_detect_model(**inputs)
            predicted_label_name = predicted_labels[outputs.logits.argmax(-1).item()]

            if predicted_label_name == "blurred":
                # Upload to S3
                filename = f"{uuid4()}__{image_name}"
                byte_arr = io.BytesIO()
                open_images.save(byte_arr, format=open_images.format or 'JPEG')
                byte_arr.seek(0)

                await S3_util_obj.upload_smart_cull_images(
                    root_folder=root_folder,
                    main_folder=inside_root_main_folder,
                    upload_image_folder=upload_image_folder,
                    image_data=byte_arr,
                    filename=filename
                )

                # Generate presigned URL
                key = f"{root_folder}/{inside_root_main_folder}/{upload_image_folder}/{filename}"
                presigned_url = await S3_util_obj.generate_presigned_url(
                    key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC
                )

                # Add metadata
                blurred_metadata.append({
                    'id': filename,
                    'name': image_name,
                    'file_type': content_type,
                    'detection_status': 'Blur',
                    'image_download_path': presigned_url,
                    'image_download_validity': datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
                    'culling_folder_id': folder_id
                })

                # Remove local blurred image
                os.remove(image_path)
            else:
                # Keep non-blurred image path
                non_blur_images.append({
                'name': image_info['name'],
                'content_type': image_info['content_type'],
                'local_path':image_info['local_path'],
            })

            # Update progress
            progress = ((index + 1) / total_img_len) * 100
            task.update_state(
                state='PROGRESS',
                meta={'progress': round(progress, 2), 'info': f'Processed {image_name}'}
            )

        except Exception as e:
            # Handle failures but keep processing other images
            error_msg = f"Failed {image_name}: {str(e)}"
            task.update_state(
                state='PROGRESS',
                meta={'progress': progress, 'info': error_msg}
            )
            continue

    # Final status update
    task.update_state(
        state='SUCCESS',
        meta={'progress': 100, 'info': 'Blur separation completed'}
    )
    time.sleep(0.2)
    return {
        'status': 'SUCCESS',
        'non_blur_images': non_blur_images, 
        'images_metadata': blurred_metadata,
        's3_response': 'Blur images uploaded successfully'
    }
