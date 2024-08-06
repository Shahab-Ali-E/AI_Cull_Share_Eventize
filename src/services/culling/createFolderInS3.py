from config.settings import get_settings
from utils.S3Utils import S3Utils
from fastapi import HTTPException,status


settings = get_settings()

async def create_folder_in_S3(dir_name, request):
    user_id = request.session.get('user_id')
    
    s3_utils = S3Utils(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                       aws_region=settings.AWS_REGION,
                       aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                       bucket_name=settings.AWS_BUCKET_NAME)
    
    #creating folder in S3
    try:
        s3_utils.create_folders_for_culling(root_folder=user_id, 
                                            main_folder=dir_name, 
                                            images_before_cull_folder=settings.IMAGES_BEFORE_CULLING_STARTS_Folder,
                                            blur_img_folder=settings.BLUR_FOLDER,
                                            closed_eye_img_folder=settings.CLOSED_EYE_FOLDER,
                                            duplicate_img_folder=settings.DUPLICATE_FOLDER,
                                            fine_collection_img_folder=settings.FINE_COLLECTION_FOLDER)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')