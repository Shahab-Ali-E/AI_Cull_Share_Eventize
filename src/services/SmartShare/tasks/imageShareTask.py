import os
import pickle
import shutil
from celery import chain
import faiss
from sqlalchemy.exc import SQLAlchemyError
import numpy as np
import requests
from tqdm import tqdm
from config.settings import get_settings
from Celery.utils import create_celery

from config.syncDatabase import celery_sync_session
from dependencies.mlModelsManager import ModelManager
from model.SmartShareFolders import PublishStatus, SmartShareFolder
from utils.CustomExceptions import SignatureDoesNotMatch, URLExpiredException, UnauthorizedAccess
from utils.MailSender import celery_send_mail
from PIL import Image
from sqlalchemy import select
from utils.template_engine import templates
from utils.generateQRCode import generate_qr_code

#---instances---
settings = get_settings()
celery = create_celery()

# #---Model---
models = ModelManager.get_models(settings)
mtcnn_model = models['face_detector']
face_net_model = models['face_net_model']

# Function for processing for face embedding
def get_face_embedding(image_path):
    """Detects faces and extracts embeddings."""
    image = Image.open(image_path).convert('RGB')
    faces = mtcnn_model(image)

    if faces is None:
        return None  # No face detected

    embeddings = []
    for face in faces:
        face = face.unsqueeze(0)  # Add batch dimension
        embedding = face_net_model(face)
        embeddings.append(embedding.detach().numpy())

    return embeddings
    

#-----------------------Celery task for smart share----------------------------------

@celery.task(name='download_and_process_images', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 4}, queue='smart_sharing')
def download_and_process_images(self, event_id, event_name:str, event_folder_path: str, urls: list[str], index_faiss_filename: str, image_map_pickle_filename: str, recipients:list[str]):
    """Downloads images from AWS, saves them locally, and processes them for face embeddings."""

    # Ensure event folder exists
    os.makedirs(event_folder_path, exist_ok=True)

    # Create 'images' directory inside event folder
    path_to_save_images = os.path.join(event_folder_path, "images")
    os.makedirs(path_to_save_images, exist_ok=True)  # Safe directory creation

    total_images = len(urls)

    with tqdm(total=total_images, desc="Downloading images", unit="image") as progress_bar:
        for _,image_url in enumerate(urls):
            try:
                response = requests.get(image_url)
                if response.status_code !=200:
                    print(f'Failed to download image {image_url}: HTTP {response.status_code}')
                    continue
                
                image_content = response.content
                image_name = image_url.split("/")[-1].split('?')[0]

                # Check for S3 access errors
                if b'<Error>' in image_content:
                    if b'<Code>AccessDenied</Code>' in image_content:
                        raise URLExpiredException()
                    if b'<Code>SignatureDoesNotMatch</Code>' in image_content:
                        raise SignatureDoesNotMatch()
                    if b'<Code>InvalidAccessKeyId</Code>' in image_content:
                        raise UnauthorizedAccess()

                # Save image to disk
                image_path = os.path.join(path_to_save_images, image_name)
                with open(image_path, 'wb') as img_file:
                    img_file.write(image_content)
                
                elapsed_time = progress_bar.format_dict.get("elapsed",0)
                rate = progress_bar.format_dict.get('rate',0)
                remaining_time = progress_bar.format_dict.get("remaining", "N/A")  # Estimated time left

                # Update progress bar & Celery state
                try:
                    progress_bar.update(1)
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": "Downloading images",
                            "total": total_images,
                            "progress": f"{progress_bar.n / total_images * 100:.2f}%",
                            "elapsed_time": elapsed_time,
                            "remaining_time": remaining_time,
                            "rate": rate
                        }
                    )
                except Exception as e:
                    print(f"Progress update error: {e}")
                    
            except Exception as e:
                print(f"Failed to download image {image_url}: {e}")

    # Step 2: Extract Face Embeddings and Build FAISS Index
    index = faiss.IndexFlatL2(512)  # FaceNet produces 512-d embeddings
    image_map = []

    saved_images = os.listdir(path_to_save_images)
    total_processed_images = len(saved_images)

    with tqdm(total=total_processed_images, desc="Processing images", unit="image") as progress_bar:
        for img_file in saved_images:
            img_path = os.path.join(path_to_save_images, img_file)
            embeddings = get_face_embedding(img_path)

            if embeddings:
                for embedding in embeddings:
                    index.add(np.array(embedding).astype('float32'))  # Ensure correct FAISS input format
                    image_map.append(img_file)

            elapsed_time = progress_bar.format_dict.get("elapsed",0)
            rate = progress_bar.format_dict.get('rate',0)
            remaining_time = progress_bar.format_dict.get("remaining", "N/A") 
            
            # Update progress
            try:
                progress_bar.update(1)
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": "Processing images",
                        "total": total_images,
                        "progress": f"{progress_bar.n / total_images * 100:.2f}%",
                        "elapsed_time": elapsed_time,
                        "remaining_time": remaining_time,
                        "rate": rate
                    }
                )
            except Exception as e:
                print(f"Progress update error: {e}")

    # Save FAISS index and image map inside event folder
    faiss_index_path = os.path.join(event_folder_path, index_faiss_filename)
    image_map_path = os.path.join(event_folder_path, image_map_pickle_filename)

    faiss.write_index(index, faiss_index_path)
    with open(image_map_path, "wb") as f:
        pickle.dump(image_map, f)
    
    # Remove the 'images' directory after processing
    shutil.rmtree(path_to_save_images, ignore_errors=True) 
    
    # updating event mark it as published
    try:
        with celery_sync_session() as db_session:
            event = db_session.scalar(select(SmartShareFolder).where(SmartShareFolder.id == event_id))
            if event:
                event.status = PublishStatus.PUBLISHED.value
            
            db_session.commit()
            
    except SQLAlchemyError as e:
        raise Exception("Error while updating event",e)
    
    # Send email after processing
    
    # Generate QR Code
    share_event_link = f'{settings.FRONTEND_HOST}/get-images/{event_id}'
    qr_code_base64 = generate_qr_code(event_link=share_event_link)
    
    # Render Jinja2 Email Template
    html_content = templates.get_template("SmartShareEventShareEmail.html").render(
        subject=f"🎉 {event_name} is Live Now!",
        event_name=event_name,
        event_link=share_event_link,
        qr_code_base64=qr_code_base64,  # Pass base64 QR
    )
    
    # Email Subject & Body
    subject = f"🎉 {event_name} is Live!"
    body = f"Your event {event_name} is now live! Check your email for details."

    # Send Email via Celery Worker
    chain(
        celery_send_mail.s(recipients, subject, html_content)
    ).apply_async()
        

    return {"status": "Published", "total_images": total_images, "processed_images": total_processed_images}

    