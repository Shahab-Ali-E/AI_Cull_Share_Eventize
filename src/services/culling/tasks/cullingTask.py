import asyncio
from transformers import ViTForImageClassification, ViTFeatureExtractor
from sqlalchemy.orm import Session
from tensorflow.keras.models import load_model  # type: ignore
from services.culling.separateBlurImages import separate_blur_images
from fastapi import HTTPException, status
from config.security import images_validation
from config.settings import get_settings
from services.culling.separateClosedEye import ClosedEyeDetection
from utils.S3Utils import S3Utils
from config.Database import session
from model.ImagesMetaData import ImagesMetaData
import cv2
# from celery import shared_task
from Celery.utils import create_celery
# import urllib.request
from urllib.request import urlopen
import io
import requests

celery = create_celery()


settings = get_settings()

#----MODELS----

# Blur detection loading 
blur_detect_model = ViTForImageClassification.from_pretrained(settings.BLUR_VIT_MODEL, from_tf=True)
feature_extractor = ViTFeatureExtractor.from_pretrained(settings.FEATURE_EXTRACTOR)

#closed eye detection loading
closed_eye_detection_model = load_model(settings.CLOSED_EYE_DETECTION_MODEL)
face_cascade = cv2.CascadeClassifier(settings.FACE_CASCADE_MODEL)



@celery.task(name='upload_image_s3_store_metadata_in_DB', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':5}, queue='culling')
def culling_task(self, user_id, uploaded_images_url, folder):

    self.update_state(state='STARTED', meta={'status': 'Task started'})
    result = asyncio.run(upload_image_s3_store_metadata_in_DB(self, user_id ,uploaded_images_url, folder))
    self.update_state(state='COMPLETED',meta={'status':'Task completed'})
    return result



async def upload_image_s3_store_metadata_in_DB(self, user_id, uploaded_images_url, folder):

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
        self.update_state(state='PROGRESS', meta={"progress":index+1, "total":len(uploaded_images_url), "info":"getting images to process"})
    

    #database session
    db_session:Session = session()
    
    #initilizing s3 utils
    s3_utils = S3Utils(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                       aws_region=settings.AWS_REGION,
                       aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                       bucket_name=settings.AWS_BUCKET_NAME)
    

    # #perform blur detection on image and separate them
    output_from_blur =  await separate_blur_images(images=images,
                                        feature_extractor=feature_extractor,
                                        blur_detect_model=blur_detect_model, 
                                        root_folder = user_id,
                                        inside_root_main_folder = folder,
                                        S3_util_obj = s3_utils,
                                        DBModel= ImagesMetaData,
                                        session=db_session,
                                        task=self
                                    )
    self.update_state(state='PROGRESS',meta={'info':"Blur images separation done !"})

    if output_from_blur[1] is None or "No images were uploaded" in output_from_blur[1]:
        return {"status": "error", "detail": "error occurred in blur detection"}
    

    #initlizing closed eye detection
    closed_eye_detect_obj =  ClosedEyeDetection(closed_eye_detection_model=closed_eye_detection_model,
                                                face_cascade=face_cascade,
                                                S3_util_obj=s3_utils,
                                                root_folder = user_id,
                                                inside_root_main_folder = folder,
                                                DBModel= ImagesMetaData,
                                                session=db_session,
                                                )
    
    self.update_state(state='PROGRESS',meta={'info':"closed eye images separation done !"})

    return  await closed_eye_detect_obj.separate_closed_eye_images_and_upload_to_s3(images=output_from_blur[0],task=self)
