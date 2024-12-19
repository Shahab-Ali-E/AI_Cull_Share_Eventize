from datetime import datetime, timedelta
import time
from PIL import Image
import io
import torch
from uuid import uuid4
from config.settings import get_settings
from dependencies.mlModelsManager import ModelManager

settings = get_settings()

# LABELS
predicted_labels = ['undistorted', 'blurred']
upload_image_folder = settings.BLUR_FOLDER

#models
models = ModelManager.get_models(settings=settings)
feature_extractor = models['feature_extractor']
blur_detect_model = models['blur_detect_model']


async def separate_blur_images(images:list, root_folder:str, inside_root_main_folder:str, folder_id:int, S3_util_obj, task):
    non_blur_images = []
    blurred_metadata = []
    response = None
    total_img_len = len(images)

    for index, image in enumerate(images):
        try:
            # Image preprocessing
            content = image['content']
            open_images = Image.open(io.BytesIO(content)).convert('RGB')
            inputs = feature_extractor(open_images, return_tensors='pt')
            if isinstance(inputs, dict):
                inputs = {k: v.to(blur_detect_model.device) for k, v in inputs.items()}
            else:
                inputs = inputs.to(blur_detect_model.device)
        except Exception as e:
            raise Exception(f"Error processing image: {str(e)}")

        try:
            # Model prediction
            with torch.no_grad():
                outputs = blur_detect_model(**inputs)
            logits = outputs.logits
            predicted_class_idx = logits.argmax(-1).item()
            predicted_label_name = predicted_labels[predicted_class_idx]
        except Exception as e:
            raise Exception(f"Error during model inference: {str(e)}")

        if predicted_label_name == "blurred":
            # Prepare and upload image
            filename = f"{uuid4()}__{image['name']}"
            byte_arr = io.BytesIO()
            format = open_images.format if open_images.format else 'JPEG'
            open_images.save(byte_arr, format=format)
            byte_arr.seek(0)
            try:
                response = await S3_util_obj.upload_smart_cull_images(root_folder=root_folder, 
                                                                        main_folder=inside_root_main_folder, 
                                                                        upload_image_folder=upload_image_folder, 
                                                                        image_data=byte_arr,
                                                                        filename=filename
                                                                    )
            except Exception as e:
                raise Exception(f"Error uploading image to S3: {str(e)}")
            
            #generating presinged url so user can download image
            key = f"{root_folder}/{inside_root_main_folder}/{upload_image_folder}/{filename}"
            presigned_url = await S3_util_obj.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)

            image_metadata = {
                'id': filename,
                'name': image['name'],
                'file_type': image['content_type'],
                'detection_status':'Blur',
                'images_download_path': presigned_url,
                'images_download_validity':datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),   
                'culling_folder_id': folder_id
            }
            blurred_metadata.append(image_metadata)
        else:
            non_blur_images.append(image)

        # Update the progress
        if task:
            progress = ((index + 1) / total_img_len) * 100
            task.update_state(state='PROGRESS', meta={'progress': progress, 'info': 'Blur image separation processing'})
            
    response = 'Blur ' + response if response == 'image uploaded successfully' else response
    task.update_state(state='SUCCESS', meta={'progress': 100, 'info': 'Blur image separation done!'})
    # time.sleep(1)
    return {
            'status': 'SUCCESS',
            'non_blur_images': non_blur_images,
            'images_metadata':blurred_metadata,
            's3_response':response
        }  
