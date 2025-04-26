from datetime import datetime, timedelta
import io
import os
import time
from uuid import uuid4
import cv2
import numpy as np
from PIL import Image
import torch
from config.settings import get_settings
from dependencies.mlModelsManager import ModelManager
import asyncio
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


settings = get_settings()

# Load models
models = ModelManager.get_models(settings)
face_detector = models['face_detector']  
feature_extractor = models['feature_extractor']  
closed_eye_model = models['closed_eye_detection_model']  

class ClosedEyeDetection:
    def __init__(self, S3_util_obj, root_folder: str, inside_root_main_folder: str):
        self.face_detector = face_detector
        self.model = closed_eye_model
        self.feature_extractor = feature_extractor
        self.S3 = S3_util_obj
        self.root_folder = root_folder
        self.inside_root_main_folder = inside_root_main_folder
        self.upload_image_folder = settings.CLOSED_EYE_FOLDER
        self.labels = ['ClosedFace', 'OpenFace']

    def is_face_forward_facing(self, landmarks, tolerance=0.1):
        left_eye, right_eye, nose = landmarks['left_eye'], landmarks['right_eye'], landmarks['nose']
        return abs(((left_eye[0] + right_eye[0]) / 2) - nose[0]) / abs(right_eye[0] - left_eye[0]) <= tolerance

    async def detect_faces(self, image_data):
        if not image_data:
            logger.error("Image data is empty")
            raise ValueError("Image data is empty")

        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            logger.error("Failed to decode image")
            raise ValueError("Failed to decode image")

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        boxes, _, landmarks = self.face_detector.detect(image_rgb, landmarks=True)

        if boxes is None:
            logger.info("No faces detected.")
            return [], image

        extracted_faces = [
            tuple(map(int, box[:4]))
            for box, lm in zip(boxes, landmarks)
            if self.is_face_forward_facing({'left_eye': lm[0], 'right_eye': lm[1], 'nose': lm[2]})
        ]

        logger.info(f"Detected {len(extracted_faces)} faces.")
        return extracted_faces, image


    async def preprocess_face_image(self, face_image):
        inputs = self.feature_extractor(Image.fromarray(face_image), return_tensors="pt")
        return {k: v.to(self.model.device) for k, v in inputs.items()}

    async def predict_eye_state(self, face_inputs):
        with torch.no_grad():
            prediction = self.labels[self.model(**face_inputs).logits.argmax(-1).item()]
            logger.info(f"Predicted eye state: {prediction}")
            return prediction


    async def process_image(self, image_data):
        extracted_faces, image = await self.detect_faces(image_data['content'])
        
        for x1, y1, x2, y2 in extracted_faces:
            face_inputs = await self.preprocess_face_image(image[y1:y2, x1:x2])
            prediction = await self.predict_eye_state(face_inputs)
            logger.info(f"Predicted eye state: {prediction}")
            if prediction == "ClosedFace":
                return {image_data['name']: ["ClosedFace"]}
        
        return {image_data['name']: ["OpenFace"]}

    async def separate_closed_eye_images_and_upload_to_s3(self, images_path, folder_id, task=None, prev_images_metadata=None):
        prev_images_metadata = prev_images_metadata or []
        open_eye_images = []
        metadata_list = prev_images_metadata.copy()
        total_images = len(images_path)

        async def upload_closed_eye_image(image_info):
            try:
                # Read image from local path
                with open(image_info['local_path'], 'rb') as f:
                    image_content = f.read()
                
                # Process and upload
                filename = f"{uuid4()}__{image_info['name']}"
                byte_arr = io.BytesIO()
                
                # Normalize format
                format_map = {
                    "image/jpeg": "JPEG",
                    "image/jpg": "JPEG",
                    "image/png": "PNG",
                    "image/webp": "WEBP",
                }
                
                img_format = format_map.get(image_info['content_type'].lower(), "JPEG")
                Image.open(io.BytesIO(image_content)).convert('RGB').save(byte_arr, format=img_format)
                byte_arr.seek(0)

                # Upload to S3
                key = f"{self.root_folder}/{self.inside_root_main_folder}/{self.upload_image_folder}/{filename}"
                await self.S3.upload_smart_cull_images(
                    self.root_folder, 
                    self.inside_root_main_folder, 
                    self.upload_image_folder, 
                    byte_arr, 
                    filename
                )
                
                # Generate presigned URL
                presigned_url = await self.S3.generate_presigned_url(
                    key, 
                    expiration=settings.PRESIGNED_URL_EXPIRY_SEC
                )

                # Cleanup local file
                os.remove(image_info['local_path'])

                return {
                    'id': filename,
                    'name': image_info['name'],
                    'detection_status': 'ClosedEye',
                    'file_type': img_format,
                    'image_download_path': presigned_url,
                    'image_download_validity': datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
                    'culling_folder_id': folder_id
                }
            except Exception as e:
                logger.error(f"Failed to upload closed eye image: {str(e)}")
                return None

        async def process_single_image(index, image_info):
            try:
                logger.info(f"Processing image {index + 1}/{total_images}: {image_info['name']}")
                
                # Load image from local path
                with open(image_info['local_path'], 'rb') as f:
                    image_content = f.read()
                
                # Perform detection
                results = await self.process_image({
                    'content': image_content,
                    'name': image_info['name'],
                    'local_path': image_info['local_path']
                })

                for image_name, prediction in results.items():
                    logger.info(f"Image {image_name}: Prediction {prediction}")
                    
                    if "ClosedFace" in prediction:
                        metadata = await upload_closed_eye_image(image_info)
                        if metadata:
                            metadata_list.append(metadata)
                    else:
                        # Retain local path for open-eye images
                        open_eye_images.append({
                            'local_path': image_info['local_path'],
                            'name': image_info['name'],
                            'content_type': image_info['content_type']
                        })

                # Update progress
                if task:
                    progress = ((index + 1) / total_images) * 100
                    task.update_state(
                        state='PROGRESS',
                        meta={'progress': round(progress, 2), 'info': f'Processed {image_info["name"]}'}
                    )

            except Exception as e:
                logger.error(f"Error processing {image_info['name']}: {str(e)}")
                if task:
                    task.update_state(
                        state='PROGRESS',
                        meta={'progress': ((index + 1) / total_images) * 100, 
                            'info': f'Failed {image_info["name"]}: {str(e)}'}
                    )

        # Process images concurrently
        await asyncio.gather(*[
            process_single_image(i, img) 
            for i, img in enumerate(images_path)
        ])

        # Final status update
        if task:
            task.update_state(
                state='SUCCESS',
                meta={'progress': 100, 'info': 'Closed eye processing complete'}
            )

        time.sleep(0.2)
        return {
            'status': 'SUCCESS',
            'open_eye_images': open_eye_images,
            'images_metadata': metadata_list,
            's3_response': 'Closed eye images processed successfully'
        }