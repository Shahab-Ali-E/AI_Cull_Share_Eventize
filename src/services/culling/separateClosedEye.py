from datetime import datetime, timedelta
import io
import time
import cv2
import numpy as np
from tensorflow.keras.preprocessing.image import img_to_array # type: ignore
from uuid import uuid4
from PIL import Image
import torch
from config.settings import get_settings
from dependencies.mlModelsManager import ModelManager
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()

#models
models = ModelManager.get_models(settings)
face_detector = models['face_detector'] # for detecting face
feature_extractor = models['feature_extractor']  # For image preprocessing
closed_eye_model = models['closed_eye_detection_model']  # ViT-based model

class ClosedEyeDetection:

    def __init__(self, S3_util_obj, root_folder:str, inside_root_main_folder:str):
        self.face_detector = face_detector
        self.model = closed_eye_model
        self.feature_extractor = feature_extractor
        self.S3 = S3_util_obj
        self.root_folder = root_folder
        self.inside_root_main_folder = inside_root_main_folder
        self.upload_image_folder = settings.CLOSED_EYE_FOLDER
        self.labels =  ['ClosedFace', 'OpenFace']
        
    def is_face_forward_facing(self, detection, tolerance=0.1):
        """
        Determines if a face is forward-facing based on landmark positions.
        """
        landmarks = detection.get('keypoints', {})
        if not landmarks:
            return False

        left_eye, right_eye = landmarks['left_eye'], landmarks['right_eye']
        nose = landmarks['nose']

        eye_center_x = (left_eye[0] + right_eye[0]) / 2
        nose_symmetry_x = abs(eye_center_x - nose[0]) / abs(right_eye[0] - left_eye[0])

        return nose_symmetry_x <= tolerance

    async def detect_faces(self, image_data):
        try:
            if not image_data:
                raise ValueError("Image data is empty")

            # Convert image bytes to numpy array and decode
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Failed to decode image")

            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            detections = self.face_detector.detect_faces(image_rgb)

            extracted_faces = []
            for detection in detections:
                if self.is_face_forward_facing(detection):
                    x, y, width, height = detection['box']
                    x, y = max(0, x), max(0, y)
                    extracted_faces.append((x, y, width, height))
            return extracted_faces, image
        except Exception as e:
            raise Exception(f"Error detecting faces: {str(e)}")

    # For preprocessing of an image
    async def preprocess_face_image(self, face_image):
        # face = cv2.resize(face_image, (150, 150))  # Resize to match the input size of your model
        # face = face.astype('float32') / 255.0  # Normalize to [0, 1]
        # face = img_to_array(face)  # Convert to array
        # face = np.expand_dims(face, axis=0)  # Add batch dimension
        # return face
        
        face_pil = Image.fromarray(cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB))
        inputs = self.feature_extractor(face_pil, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        return inputs

    # To predict whether eye is closed or not in a single face
    async def predict_eye_state(self, face_image):
        # prediction = self.model.predict(face_image)
        # print('closed' if prediction[0][0] < 0.6 else 'open')
        # return 'closed' if prediction[0][0] < 0.6 else 'open'
        
        with torch.no_grad():
            outputs = self.model(**face_image)
        logits = outputs.logits
        predicted_class_idx = logits.argmax(-1).item()
        predicted_label = self.labels[predicted_class_idx]
        print(predicted_label)
        return predicted_label

    # It will process a single image and return how many faces in it were closed or open
    async def process_image(self, raw_image):
        # Load image as byte data
        # image_data = raw_image['content']
        
        # extracted_faces, image = await self.detect_faces(image_data)
        # predictions = []

        # for (x, y, width, height) in extracted_faces:
        #     face_image = image[y:y+height, x:x+width]
        #     preprocessed_face = await self.preprocess_face_image(face_image)
        #     eye_state = await self.predict_eye_state(preprocessed_face)
        #     predictions.append(eye_state)

        # results = {raw_image['name']: predictions}
        # return results
        
        image_data = raw_image['content']
        extracted_faces, image = await self.detect_faces(image_data)
        predictions = []

        for (x, y, width, height) in extracted_faces:
            face_image = image[y:y + height, x:x + width]
            face_inputs = await self.preprocess_face_image(face_image)
            eye_state = await self.predict_eye_state(face_inputs)
            predictions.append((eye_state, face_image))

        # If no faces are detected, consider it an open face
        if not extracted_faces:
            predictions.append(('OpenFace', image))

        return predictions

    # It will take single or bunch of images and upload them to S3 after making prediction
    async def separate_closed_eye_images_and_upload_to_s3(self, images:list, folder_id:int, task, prev_image_metadata:list=[]):
        # open_eyes_images = []
        # images_metadata = prev_image_metadata
        # response = None
        # total_img_len = len(images)
        # for index, image in enumerate(images):
        #     result = await self.process_image(image)
            
        #     for img_name, predictions in result.items():
        #         content = image['content']
        #         open_images = Image.open(io.BytesIO(content)).convert('RGB')
                
        #         if "closed" in predictions:
        #             filename = f"{uuid4()}__{img_name}"
        #             byte_arr = io.BytesIO()
        #             format = open_images.format if open_images.format else 'JPEG'
        #             open_images.save(byte_arr, format=format)
        #             byte_arr.seek(0)
                    
        #             try:
        #                 response = await self.S3.upload_smart_cull_images(
        #                                                         root_folder=self.root_folder,
        #                                                         main_folder=self.inside_root_main_folder,
        #                                                         upload_image_folder=self.upload_image_folder,
        #                                                         image_data=byte_arr,
        #                                                         filename=filename
        #                                                     )
        #             except Exception as e:
        #                 raise Exception(f"Error uploading image to S3: {str(e)}")
                    
        #             #generating presinged url so user can download image
        #             key = f"{self.root_folder}/{self.inside_root_main_folder}/{self.upload_image_folder}/{filename}"
        #             presigned_url = await self.S3.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)

        #             metadata = {
        #                 'id': filename,
        #                 'name': img_name,
        #                 'detection_status':'ClosedEye',
        #                 'file_type': image['content_type'],
        #                 'images_download_path': presigned_url,
        #                 'images_download_validity':datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
        #                 'culling_folder_id': folder_id
        #             }

        #             #appending closed images metadata to and array
        #             images_metadata.append(metadata)
                    
        #         else:
        #             open_eyes_images.append(image)  # Append the image if eyes are open

        #     # Updating progress here
        #     if task:
        #         progress = ((index + 1) / total_img_len) * 100
        #         task.update_state(state='PROGRESS', meta={'progress': progress, 'info': 'Closed eye image separation processing'})

        # response = 'closed eye' + response if response == 'image uploaded successfully' else response
        # task.update_state(state='SUCCESS', meta={'progress': 100, 'info': 'Closed eye image separation done!'})
        # time.sleep(1)  
        # return {
        #     'status': 'SUCCESS',
        #     'open_eye_images': open_eyes_images,
        #     'images_metadata':images_metadata,
        #     's3_response':response
        # }
        open_eyes_images = []
        images_metadata = prev_image_metadata
        response = None
        total_img_len = len(images)

        for index, image in enumerate(images):
            results = await self.process_image(image)

            for eye_state, processed_image in results:
                # content = image['content']
                image_name = image['name']

                if eye_state == "ClosedFace":
                    filename = f"{uuid4()}__{image_name}"
                    byte_arr = io.BytesIO()
                    processed_image_pil = Image.fromarray(cv2.cvtColor(processed_image, cv2.COLOR_BGR2RGB))
                    processed_image_pil.save(byte_arr, format="JPEG")
                    byte_arr.seek(0)

                    try:
                        response = await self.S3.upload_smart_cull_images(
                            root_folder=self.root_folder,
                            main_folder=self.inside_root_main_folder,
                            upload_image_folder=self.upload_image_folder,
                            image_data=byte_arr,
                            filename=filename,
                        )
                    except Exception as e:
                        raise Exception(f"Error uploading image to S3: {str(e)}")

                    # Generate metadata for the closed eye image
                    key = f"{self.root_folder}/{self.inside_root_main_folder}/{self.upload_image_folder}/{filename}"
                    presigned_url = await self.S3.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)
                    metadata = {
                        'id': filename,
                        'name': image_name,
                        'detection_status': 'ClosedEye',
                        'file_type': image['content_type'],
                        'images_download_path': presigned_url,
                        'images_download_validity': datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
                        'culling_folder_id': folder_id
                    }

                    images_metadata.append(metadata)
                else:
                    open_eyes_images.append(image)  # Append the image if eyes are open

            # Updating progress
            if task:
                progress = ((index + 1) / total_img_len) * 100
                task.update_state(state='PROGRESS', meta={'progress': progress, 'info': 'Closed eye image separation processing'})

        response = 'Closed Eye ' + response if response == 'image uploaded successfully' else response
        task.update_state(state='SUCCESS', meta={'progress': 100, 'info': 'Closed eye image separation done!'})
        # time.sleep(1)
        return {
            'status': 'SUCCESS',
            'open_eye_images': open_eyes_images,
            'images_metadata': images_metadata,
            's3_response': response
        }

