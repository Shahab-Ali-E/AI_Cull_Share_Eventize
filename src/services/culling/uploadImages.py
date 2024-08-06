import cv2
from fastapi import HTTPException,status
from config.security import images_validation
from services.culling.separateBlurImages import separate_blur_images
from transformers import ViTForImageClassification , ViTFeatureExtractor
from tensorflow.keras.models import load_model # type: ignore
from config.settings import get_settings
from services.culling.separateClosedEye import ClosedEyeDetection
from utils.S3Utils import S3Utils
from model.ImagesMetaData import ImagesMetaData


settings = get_settings()

#Blur detection loading 
blur_detect_model = ViTForImageClassification.from_pretrained(settings.BLUR_VIT_MODEL , from_tf=True)#loading model
feature_extractor = ViTFeatureExtractor.from_pretrained(settings.FEATURE_EXTRACTOR)#loading feature extractor

#Closed Eye Detection loading
closed_eye_detection_model = load_model(settings.CLOSED_EYE_DETECTION)#loading model
face_cascade = cv2.CascadeClassifier(settings.FACE_CASCADE)#loading face extractor



async def upload_image_s3_store_metadata_in_DB(request, images, folder, session):
    is_valid, validation_message = images_validation(images, max_uploads=20, max_size_mb=100)
    user_id = request.session.get("user_id")

    #raise exception if is_valid return None
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=validation_message)
    
    
    #initilizing s3 utils
    s3_utils = S3Utils(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                       aws_region=settings.AWS_REGION,
                       aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                       bucket_name=settings.AWS_BUCKET_NAME)
    

    # #perform blur detection on image and separate them
    output_from_blur = await separate_blur_images(images=images,
                                        feature_extractor=feature_extractor,
                                        blur_detect_model=blur_detect_model, 
                                        root_folder = user_id,
                                        inside_root_main_folder = folder,
                                        S3_util_obj = s3_utils,
                                        bucket_name = settings.AWS_BUCKET_NAME,
                                        DBModel= ImagesMetaData,
                                        session=session,
                                    )
    print(output_from_blur)
    if "image uploaded successfully" not in output_from_blur[1]:
        raise HTTPException(status_code=status.HTTP_417_EXPECTATION_FAILED, detail="error occur in blur detection")

    #initlizing closed eye detection
    closed_eye_detect_obj = ClosedEyeDetection(closed_eye_detection_model=closed_eye_detection_model,
                                                face_cascade=face_cascade,
                                                bucket_name=settings.AWS_BUCKET_NAME,
                                                S3_util_obj=s3_utils,
                                                root_folder = user_id,
                                                inside_root_main_folder = folder,
                                                DBModel= ImagesMetaData,
                                                session=session,
                                                )
    
    return await closed_eye_detect_obj.separate_closed_eye_images_and_uplaod_to_s3(images=output_from_blur[0])



    
    
    