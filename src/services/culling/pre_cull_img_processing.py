from io import BytesIO
from fastapi import UploadFile, HTTPException,status
from uuid import uuid4
from config.settings import get_settings
from sqlalchemy.orm import Session
from utils.SaveMetaDataToDB import save_or_update_metadata_in_db
from utils.UpdateUserStorage import update_user_storage_in_db

settings = get_settings()

async def pre_cull_image_processing(images:list[UploadFile], s3_utils, user_id:int, folder:str,session:Session, total_image_size:int):
    """
    Processes a list of images before culling, uploads them to an AWS S3 bucket, 
    and updates metadata and user storage in the database.

    :param images: List of images to be uploaded.
    :param s3_utils: Utility class for S3 operations.
    :param user_id: The ID of the user uploading the images.
    :param folder: The name of the folder in S3 where images will be stored.
    :param session: SQLAlchemy session for database operations.
    :param total_image_size: The combined size of the images being uploaded.

    Returns:
    - A dictionary containing a message about the URL validity and the list of presigned URLs.
    """

    uploaded_images_url =[]

    for image in images:
        filename = f'{uuid4()}_{image.filename}'
        
        #some image validation
        try:
            image_data = await image.read()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading image file: {str(e)}")
        
        try:
            s3_utils.upload_image(
                filename=filename,
                root_folder=user_id,
                main_folder=folder,
                upload_image_folder=settings.IMAGES_BEFORE_CULLING_STARTS_Folder,
                image_data=BytesIO(image_data)
            )
            key = f"{user_id}/{folder}/{settings.IMAGES_BEFORE_CULLING_STARTS_Folder}/{filename}"
            presigned_url = s3_utils.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)
            uploaded_images_url.append(presigned_url)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error uploading image to S3: {str(e)}")

    #updating the storage of folder in database
    match_criteria = {"name": folder, "user_id": user_id, "module":settings.APP_SMART_CULL_MODULE}

    save_or_update_metadata_in_db(session=session,
                                    match_criteria=match_criteria,
                                    update_fields={"total_size":total_image_size},
                                    task='update')

    #update the storage in database    
    is_valid,response = update_user_storage_in_db(db_session=session,
                                            module=settings.APP_SMART_CULL_MODULE,
                                            total_image_size=total_image_size,
                                            user_id=user_id,
                                            operation='increment')
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{response}")
    
    return {
        'message': f'URLs are valid for {settings.PRESIGNED_URL_EXPIRY_SEC} seconds',
        'urls': uploaded_images_url
    }