import io
import cv2
import numpy as np
from tensorflow.keras.preprocessing.image import img_to_array # type: ignore
from uuid import uuid4
from PIL import Image
from utils.SaveImageMetaDataToDB import save_image_metadata_to_DB
from config.settings import get_settings

settings = get_settings()

class ClosedEyeDetection:

    def __init__(self, face_cascade, closed_eye_detection_model, S3_util_obj, root_folder, inside_root_main_folder, DBModel, session):
        self.face_cascade = face_cascade
        self.model = closed_eye_detection_model
        self.S3 = S3_util_obj
        self.root_folder = root_folder
        self.DBModel = DBModel
        self.session = session
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
            image_grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            # Detect faces in the grayscale image
            faces = self.face_cascade.detectMultiScale(image_grey, scaleFactor=1.16, minNeighbors=5, minSize=(25, 25), flags=0)
            # List to store extracted faces data
            extracted_faces = []
            # Iterate through detected faces and save them
            for x, y, w, h in faces:
                extracted_faces.append((x, y, w, h))
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
        return 'closed' if prediction[0][0] < 0.5 else 'open'

    # It will process a single image and return how many faces in it were closed or open
    async def process_image(self, raw_image):
        # Load image as byte data
        image_data = raw_image['content']
        
        extracted_faces, image = await self.detect_faces(image_data)
        predictions = []

        for (x, y, w, h) in extracted_faces:
            face_image = image[y:y+h, x:x+w]
            preprocessed_face = await self.preprocess_face_image(face_image)
            eye_state = await self.predict_eye_state(preprocessed_face)
            predictions.append(eye_state)

        results = {raw_image['name']: predictions}
        return results

    # It will take single or bunch of images and upload them to S3 after making prediction
    async def separate_closed_eye_images_and_upload_to_s3(self, images, task):
        open_eyes_images = []  # Initialize the list outside the loop
        response = None
        total_img_len = len(images)
        
        for index, image in enumerate(images):
            result = await self.process_image(image)

            # Perform check if the image is closed eye, upload it to S3; if it's open, store in the array
            for value in result.items():
                content = image['content']
                open_images = Image.open(io.BytesIO(content)).convert('RGB')
                if "closed" in value:
                    filename = f"{uuid4()}__{image['name']}"
                    byte_arr = io.BytesIO()
                    format = open_images.format if open_images.format else 'JPEG'
                    open_images.save(byte_arr, format=format)
                    byte_arr.seek(0)
                    try:
                        response = self.S3.upload_image(
                            root_folder=self.root_folder,
                            main_folder=self.inside_root_main_folder,
                            upload_image_folder=self.upload_image_folder,
                            image_data=byte_arr,
                            filename=filename
                        )
                    except Exception as e:
                        raise Exception(f"Error uploading image to S3: {str(e)}")
                    
                    Bucket_Folder = f'{self.inside_root_main_folder}/{self.upload_image_folder}'

                    # Saving the closed eye images into Database
                    DB_response = await save_image_metadata_to_DB(DBModel=self.DBModel,
                                                                img_id=filename,
                                                                img_filename=image['name'],
                                                                img_content_type=image['content_type'],
                                                                user_id=self.root_folder,
                                                                bucket_folder=Bucket_Folder,
                                                                session=self.session
                                                                )
                    print(DB_response)
                else:
                    open_eyes_images.append(image)  # Append the image if eyes are open

            # Updating progress here
            if task:
                task.update_state(state='PROGRESS', meta={'current': index+1, 'total': total_img_len, 'info': 'Closed eye image separation processing'})

        return open_eyes_images, response or "No images were uploaded"
