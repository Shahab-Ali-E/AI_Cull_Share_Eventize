from datetime import datetime, timedelta
import io
import time
import cv2
import numpy as np
from tensorflow.keras.preprocessing.image import img_to_array # type: ignore
from uuid import uuid4
from PIL import Image
from config.settings import get_settings
from dependencies.mlModelsManager import ModelManager
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()

#models
models = ModelManager.get_models(settings)

class ClosedEyeDetection:

    def __init__(self, S3_util_obj, root_folder:str, inside_root_main_folder:str):
        self.face_detector = models['face_detector']
        self.model = models['closed_eye_detection_model']
        self.S3 = S3_util_obj
        self.root_folder = root_folder
        self.inside_root_main_folder = inside_root_main_folder
        self.upload_image_folder = settings.CLOSED_EYE_FOLDER

    # To extract faces from image
    async def detect_faces(self, image_data):
        try:
            if not image_data or len(image_data) == 0:
                raise ValueError("Image data is empty or not provided")
            # Convert byte data to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            if nparr.size == 0:
                raise ValueError("Converted numpy array is empty")
            
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if image is None or image.size == 0:
                raise ValueError("Failed to decode image from numpy array")
      
            # Convert the image to grayscale for face detection
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            # Detect faces in the grayscale image
            faces = self.face_detector.detect_faces(image_rgb)
            # List to store extracted faces data
            extracted_faces = []
            # Iterate through detected faces and save them
            for detection in faces:
                x, y, width, height = detection['box']
                extracted_faces.append((x, y, width, height))
        except Exception as e:
            raise Exception(f"Error detecting faces: {str(e)}")
        
        return extracted_faces, image

    # For preprocessing of an image
    async def preprocess_face_image(self, face_image):
        face = cv2.resize(face_image, (150, 150))  # Resize to match the input size of your model
        face = face.astype('float32') / 255.0  # Normalize to [0, 1]
        face = img_to_array(face)  # Convert to array
        face = np.expand_dims(face, axis=0)  # Add batch dimension
        return face

    # To predict whether eye is closed or not in a single face
    async def predict_eye_state(self, face_image):
        prediction = self.model.predict(face_image)
        print('closed' if prediction[0][0] < 0.6 else 'open')
        return 'closed' if prediction[0][0] < 0.6 else 'open'

    # It will process a single image and return how many faces in it were closed or open
    async def process_image(self, raw_image):
        # Load image as byte data
        image_data = raw_image['content']
        
        extracted_faces, image = await self.detect_faces(image_data)
        predictions = []

        for (x, y, width, height) in extracted_faces:
            face_image = image[y:y+height, x:x+width]
            preprocessed_face = await self.preprocess_face_image(face_image)
            eye_state = await self.predict_eye_state(preprocessed_face)
            predictions.append(eye_state)

        results = {raw_image['name']: predictions}
        return results

    # It will take single or bunch of images and upload them to S3 after making prediction
    async def separate_closed_eye_images_and_upload_to_s3(self, images:list, folder_id:int, task, prev_image_metadata:list=[]):
        open_eyes_images = []
        images_metadata = prev_image_metadata
        response = None
        total_img_len = len(images)
        for index, image in enumerate(images):
            result = await self.process_image(image)
            
            for img_name, predictions in result.items():
                content = image['content']
                open_images = Image.open(io.BytesIO(content)).convert('RGB')
                
                if "closed" in predictions:
                    filename = f"{uuid4()}__{img_name}"
                    byte_arr = io.BytesIO()
                    format = open_images.format if open_images.format else 'JPEG'
                    open_images.save(byte_arr, format=format)
                    byte_arr.seek(0)
                    
                    try:
                        response = await self.S3.upload_smart_cull_images(
                                                                root_folder=self.root_folder,
                                                                main_folder=self.inside_root_main_folder,
                                                                upload_image_folder=self.upload_image_folder,
                                                                image_data=byte_arr,
                                                                filename=filename
                                                            )
                    except Exception as e:
                        raise Exception(f"Error uploading image to S3: {str(e)}")
                    
                    #generating presinged url so user can download image
                    key = f"{self.root_folder}/{self.inside_root_main_folder}/{self.upload_image_folder}/{filename}"
                    presigned_url = await self.S3.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)

                    metadata = {
                        'id': filename,
                        'name': img_name,
                        'detection_status':'ClosedEye',
                        'file_type': image['content_type'],
                        'images_download_path': presigned_url,
                        'images_download_validity':datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
                        'culling_folder_id': folder_id
                    }

                    #appending closed images metadata to and array
                    images_metadata.append(metadata)
                    
                else:
                    open_eyes_images.append(image)  # Append the image if eyes are open

            # Updating progress here
            if task:
                progress = ((index + 1) / total_img_len) * 100
                task.update_state(state='PROGRESS', meta={'progress': progress, 'info': 'Closed eye image separation processing'})

        response = 'closed eye' + response if response == 'image uploaded successfully' else response
        task.update_state(state='SUCCESS', meta={'progress': 100, 'info': 'Closed eye image separation done!'})
        time.sleep(1)  
        return {
            'status': 'SUCCESS',
            'open_eye_images': open_eyes_images,
            'images_metadata':images_metadata,
            's3_response':response
        }

