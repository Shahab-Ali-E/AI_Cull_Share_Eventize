from datetime import datetime, timezone
from PIL import Image
import io
import torch
from uuid import uuid4
from utils.SaveImageMetaDataToDB import save_image_metadata_to_DB
from config.settings import get_settings

settings = get_settings()

# LABELS
predicted_labels = ['undistorted', 'blurred']
upload_image_folder = settings.BLUR_FOLDER

async def separate_blur_images(images, feature_extractor, blur_detect_model, root_folder, inside_root_main_folder, S3_util_obj, DBModel, session, task):
    results = []
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
                response = S3_util_obj.upload_image(root_folder=root_folder, 
                                                    main_folder=inside_root_main_folder, 
                                                    upload_image_folder=upload_image_folder, 
                                                    image_data=byte_arr,
                                                    filename=filename)
            except Exception as e:
                raise Exception(f"Error uploading image to S3: {str(e)}")

            Bucket_Folder = f'{inside_root_main_folder}/{upload_image_folder}'
            # Saving the blur images into Database
            await save_image_metadata_to_DB(DBModel=DBModel,
                                                          img_id=filename,
                                                          img_filename=image['name'],
                                                          img_content_type=image['content_type'],
                                                          user_id=root_folder,
                                                          bucket_folder=Bucket_Folder,
                                                          session=session
                                                          )
        else:
            results.append(image)

        # Update the progress
        if task:
            progress = ((index + 1) / total_img_len) * 100
            task.update_state(state='PROGRESS', meta={'progress': progress, 'info': 'Blur image separation processing'})

        task.update_state(state='PROGRESS', meta={'progress': 100, 'info': "Blur images separation completed !"})

    return results, response or "No blur images were found"
