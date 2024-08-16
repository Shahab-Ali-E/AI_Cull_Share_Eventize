import asyncio
from fastapi.responses import JSONResponse
from config.settings import get_settings
import cv2
import torch
import numpy as np
from transformers import AutoImageProcessor, ResNetForImageClassification 
from Celery.utils import create_celery
from celery import chain
from PIL import Image
from services.Culling.tasks.cullingTask import get_images_from_aws
from utils.CustomExceptions import URLExpiredException
from utils.QdrantUtils import QdrantUtils
import requests

#---instances---
settings = get_settings()
celery = create_celery()
qdrant_util = QdrantUtils()

#---Model---
face_extractor = cv2.CascadeClassifier(settings.FACE_CASCADE_MODEL)

#---------------------Independent Tasks For Image Share------------------------------------------------

@celery.task(name='extract_faces', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5}, queue='smart_sharing')
def extract_faces(self, images):
    extracted_faces = []
    for image in images:
        image_data = image['content']
        image_name = image['name']

        try:
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
            faces = face_extractor.detectMultiScale(image_grey, scaleFactor=1.16, minNeighbors=5, minSize=(25, 25), flags=0)

            # Iterate through detected faces and save them
            face_images = []
            for i,(x, y, w, h) in enumerate(faces):
                face_image = image[y:y+h, x:x+w]
                face_pil = Image.fromarray(face_image) # Convert array to pillow image obj
                face_images.append(face_pil)
            
            extracted_faces.append({
                'name': image_name,
                'faces': face_images
            })
        except Exception as e:
            raise Exception(f"Error detecting faces in {image_name}: {str(e)}")

    return extracted_faces

@celery.task(name='generate_embeddings', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5}, queue='smart_sharing')
def generate_embeddings(self, faces_data):
    # Initialize processor and model for embeddings
    processor = AutoImageProcessor.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL)
    model = ResNetForImageClassification.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL)

    all_embeddings = []

    try:
        for face_data in faces_data:
            image_name = face_data['name']
            pil_objs = face_data['faces']

            if not pil_objs:
                continue  # Skip if no faces detected

            # Process images into tensors
            inputs = processor(
                images=pil_objs,
                return_tensors='pt'  # Use 'pt' for PyTorch tensors
            )

            pixel_values = inputs['pixel_values']
            if isinstance(pixel_values, list):
                pixel_values = torch.stack(pixel_values)

            # Get model output
            with torch.no_grad():  # Disable gradient calculation
                outputs = model(pixel_values=pixel_values)

            embeddings = outputs.logits

            for embedding in embeddings:
                all_embeddings.append({
                    'name': image_name,
                    'embeddings':embedding.cpu().numpy()
                }) # Convert embeddings to numpy arrays for easier handling

    except Exception as e:
        raise Exception(f"Error generating embeddings: {str(e)}")

    return all_embeddings

@celery.task(name='uploading_embeddings', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5}, queue='smart_sharing')
def uploading_embeddings(self, all_embeddings, event_name):
    response = qdrant_util.upload_image_embeddings(
                                                                collection_name=event_name,
                                                                vector_data=all_embeddings,
                                                                embedding_size=1000
                                                                )
                            # )
    
    return response

#-----------------------Chaining All Above Task Here----------------------------------

@celery.task(name='image_share_task', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 2}, queue='smart_sharing')
def image_share_task(self, user_id:str, uploaded_images_url:list, event_name:str):
    # self.update_state(state='STARTED', meta={'status': 'Task started'})

    task_ids = []
    try:
        # Chain the tasks correctly
        chain_result = chain(
            get_images_from_aws.s(uploaded_images_url),
            extract_faces.s(),
            generate_embeddings.s(),
            uploading_embeddings.s(event_name)
        )

        result = chain_result.apply_async()

        # Get the task IDs of each task in the chain
        task_ids.append(result.id)
        while result.parent:
            result = result.parent
            task_ids.append(result.id)

        task_ids.reverse()  # Reverse to get the correct order of execution

        self.update_state(state='SUCCESS', meta={'status': 'Image sharing task executing in background', 'task_ids': task_ids})
    
    except URLExpiredException() as e:
        self.update_state(state='FAILURE', meta={'status': str(e), 'task_ids': task_ids})
        raise
    except Exception as e:
        self.update_state(state='FAILURE', meta={'status': f"Unexpected error: {str(e)}", 'task_ids': task_ids})
        raise
    
    return JSONResponse(task_ids)
