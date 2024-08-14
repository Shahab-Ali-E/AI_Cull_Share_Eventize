from io import BytesIO
from fastapi.responses import JSONResponse
from numpy import asarray
from fastapi import HTTPException
from config.settings import get_settings
import cv2
import torch
import numpy as np
from transformers import AutoImageProcessor, ResNetForImageClassification 
from Celery.utils import create_celery
import requests
from celery import chain
from PIL import Image
#---instances---
settings = get_settings()
celery = create_celery()

#---Model---
face_extractor = cv2.CascadeClassifier(settings.FACE_CASCADE_MODEL)

#---------------------Independent Tasks For Image Share------------------------------------------------

#This task is used to get images from AWS server from the link which have provided as param to it 
@celery.task(name='get_images_from_aws', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':5}, queue='image_share')
def get_images_from_aws(self, uploaded_images_url):
    images = []

    for index, image in enumerate(uploaded_images_url):
        response = requests.get(image)
        image_content = response.content
        content_type = 'image/'+ image.split('/')[-1].split('.')[-1].split('?')[0]
        image_name = image.split("/")[-1].split('?')[0]
        image_size = len(image_content)

        images.append({
            'content_type': content_type,
            'name': image_name,
            'size': image_size,
            'content': image_content
        })
        progress = ((index + 1) / len(uploaded_images_url)) * 100
        self.update_state(state='PROGRESS', meta={"progress": progress, "info": "Getting images to process"})
    
    return images

@celery.task(name='extract_faces', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':5}, queue='image_share')
# This task will extract all faces from image
def extract_faces(images):
    # List to store extracted faces data
    extracted_faces = []
    image_data = images['content']
    image_name = images['name']

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
        for i,(x, y, w, h) in enumerate(faces):
            face_image = image[y:y+h, x:x+w]
            face_pil = Image.fromarray(face_image)#convert array to pillow image obj

            file_name = image_name
            
            extracted_faces.append((file_name, face_pil))
    except Exception as e:
        raise Exception(f"Error detecting faces: {str(e)}")

    return extracted_faces

@celery.task(name='generate_embeddings', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5}, queue='image_share')
def generate_embeddings(self, faces_data):
    # Initialize processor and model for embeddings
    processor = AutoImageProcessor.from_pretrained("microsoft/resnet-50")
    model = ResNetForImageClassification.from_pretrained("microsoft/resnet-50")

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

            # Append names and their corresponding embeddings
            image_embeddings = []
            for embedding in embeddings:
                image_embeddings.append(embedding.cpu().numpy())  # Convert embeddings to numpy arrays for easier handling

            all_embeddings.append({
                'name': image_name,
                'embeddings': image_embeddings
            })
    except Exception as e:
        raise Exception(f"Error generating embeddings: {str(e)}")

    return all_embeddings


#-----------------------Chaining All Above Task Here----------------------------------

@celery.task(name='upload_image_s3_store_metadata_in_DB', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':5}, queue='culling')
def image_share_task(self, user_id, uploaded_images_url):

    self.update_state(state='STARTED', meta={'status': 'Task started'})

    task_ids=[]
    # Chain the results
    chain_result = chain(
        get_images_from_aws.s(uploaded_images_url),
        extract_faces.s(),
        generate_embeddings.s()
    )

    result = chain_result.apply_async()

    #to get the task id's of each one in chaining
    task_ids.append(result.id)
    while result.parent:
        result = result.parent
        task_ids.append(result.id)

    task_ids.reverse()  # Reverse to get the correct order of execution

    self.update_state(state='SUCCESS', meta={'status': 'Culling task executing in background', 'task_ids': task_ids})

    return JSONResponse(task_ids)