import asyncio
from transformers import ViTForImageClassification, ViTFeatureExtractor
from sqlalchemy.orm import Session
from tensorflow.keras.models import load_model  # type: ignore
from services.Culling.separateBlurImages import separate_blur_images
from fastapi.responses import JSONResponse
from config.settings import get_settings
from services.Culling.separateClosedEye import ClosedEyeDetection
from utils.S3Utils import S3Utils
from config.Database import session
from model.ImagesMetaData import ImagesMetaData
import cv2
from Celery.utils import create_celery
import requests
from celery import chain


#-----instances----
celery = create_celery()
settings = get_settings()
s3_utils = S3Utils(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_region=settings.AWS_REGION,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    bucket_name=settings.AWS_BUCKET_SMART_CULL_NAME,
                    aws_endpoint_url=settings.AWS_ENDPOINT_URL)

#----MODELS----

# Blur detection loading 
blur_detect_model = ViTForImageClassification.from_pretrained(settings.BLUR_VIT_MODEL, from_tf=True)
feature_extractor = ViTFeatureExtractor.from_pretrained(settings.FEATURE_EXTRACTOR)

#closed eye detection loading
closed_eye_detection_model = load_model(settings.CLOSED_EYE_DETECTION_MODEL)
face_cascade = cv2.CascadeClassifier(settings.FACE_CASCADE_MODEL)




#---------------------Independenst Task For Culling------------------------------------------------

#This task is used to get images from AWS server from the link which have provided as param to it 
@celery.task(name='get_images_from_aws', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':5}, queue='culling')
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



#This task is used to separate blur images and upload them to aws server and finally return non-blur images
@celery.task(name='blur_image_separation', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':3}, queue='culling')
def blur_image_separation(self, images, user_id, folder, folder_id):
    #database session
    db_session:Session = session()
    

    # # #perform blur detection on image and separate them
    output_from_blur =  asyncio.run(separate_blur_images(images=images,
                                        feature_extractor=feature_extractor,
                                        blur_detect_model=blur_detect_model, 
                                        root_folder = user_id,
                                        inside_root_main_folder = folder,
                                        folder_id=folder_id,
                                        S3_util_obj = s3_utils,
                                        session=db_session,
                                        task=self
                                    ))

    return output_from_blur



#This task is used to separate closed eye images and upload them to aws server and finally return non-closed-eye images
@celery.task(name='closed_eye_separation', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3}, queue='culling')
def closed_eye_separation(self, output_from_blur, user_id, folder, folder_id):
    if output_from_blur[1] is None or "No images were uploaded" in output_from_blur[1]:
        return {"status": "error", "detail": "error occurred in blur detection"}
    
    db_session: Session = session()
    
    closed_eye_detect_obj = ClosedEyeDetection(
        closed_eye_detection_model=closed_eye_detection_model,
        face_cascade=face_cascade,
        S3_util_obj=s3_utils,
        root_folder=user_id,
        inside_root_main_folder=folder,
        session=db_session,
    )

    result = asyncio.run(closed_eye_detect_obj.separate_closed_eye_images_and_upload_to_s3(images=output_from_blur[0], task=self, folder_id=folder_id))

    return result


#-----------------------Chaining All Above Task Here----------------------------------

@celery.task(name='culling_task', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':5}, queue='culling')
def culling_task(self, user_id, uploaded_images_url, folder, folder_id):

    self.update_state(state='STARTED', meta={'status': 'Task started'})

    task_ids=[]
    # Chain the results
    chain_result = chain(
        get_images_from_aws.s(uploaded_images_url),
        blur_image_separation.s(user_id, folder, folder_id),
        closed_eye_separation.s(user_id, folder, folder_id)
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




