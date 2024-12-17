from datetime import datetime, timedelta
from io import BytesIO
from uuid import uuid4
from fastapi import HTTPException,status
from sqlalchemy.ext.asyncio import AsyncSession
from config.settings import get_settings
from utils.UpsertMetaDataToDB import upsert_folder_metadata_DB, insert_image_metadata
from utils.UpdateUserStorage import update_user_storage_in_db
from model.SmartShareFolders import SmartShareFolder
from model.SmartShareImagesMetaData import SmartShareImagesMetaData

settings = get_settings()

async def preprocess_image_before_embedding(event_name:str, images:list, s3_utils, db_session:AsyncSession, total_image_size:int, user_id:str, folder_id:int):
    """
    Processes a list of images before culling, uploads them to an AWS S3 bucket, 
    and updates metadata and user storage in the database.

    :param images: List of images to be uploaded.
    :param s3_utils: Utility class for S3 operations.
    :param user_id: The ID of the user uploading the images.
    :param event_name: The name of the folder in S3 where images will be stored.
    :param db_session: SQLAlchemy session for database operations.
    :param total_image_size: The combined size of the images being uploaded.
    :param folder_id: The folder id to which images are associated with.

    Returns:
    - A dictionary containing a message about the URL validity and the list of presigned URLs.
    """

    uploaded_images_url =[]
    images_metadata = []
    for image in images:
        filename = f'{uuid4()}_{image.filename}' 
        #some image validation
        try:
            image_data = await image.read()
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error reading image file: {str(e)}")
        
        try:
            await s3_utils.upload_smart_share_images(
                                                    filename=filename,
                                                    root_folder=user_id,
                                                    event_folder=event_name,
                                                    image_data=BytesIO(image_data)
                                                    )
            key = f"{user_id}/{event_name}/{filename}"
            presigned_url = await s3_utils.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)
            uploaded_images_url.append(presigned_url)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error uploading image to S3: {str(e)}")
        
        #adding images metadata in databse
        img_data = {
                        'id': filename,
                        'name': image.filename,
                        'file_type': image.content_type,
                        'images_download_path': presigned_url,
                        'images_download_validity':datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
                        'smart_share_folder_id': folder_id
                    }

        images_metadata.append(img_data)
    
    if images_metadata:
        try:
            inserting_images = [SmartShareImagesMetaData(**data) for data in images_metadata]
            db_session.add_all(inserting_images)
    
            #updating the storage of folder in database
            match_criteria = {"name": event_name, "user_id": user_id}
            folder_meta_data = await upsert_folder_metadata_DB(
                                                                db_session=db_session,
                                                                match_criteria=match_criteria,
                                                                update_fields={"total_size":total_image_size},
                                                                model=SmartShareFolder,
                                                                update=True
                                                            )
            if not folder_meta_data:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error saving folder meta data to database")

            #update the user storage in database    
            is_valid,response = await update_user_storage_in_db(db_session=db_session,
                                                                module=settings.APP_SMART_SHARE_MODULE,
                                                                total_image_size=total_image_size,
                                                                user_id=user_id,
                                                                increment=True
                                                                )
            if not is_valid:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{response}")
        
            return {
                'message': f'URLs are valid for {settings.PRESIGNED_URL_EXPIRY_SEC} seconds',
                'urls': uploaded_images_url,
            }

        except HTTPException as e:
            await db_session.rollback()
            await s3_utils.delete_object(folder_key=f'{user_id}/{event_name}/', rollback=True)
            raise HTTPException(status_code=e.status_code, detail=str(e))

        except Exception as e:
            await db_session.rollback()
            await s3_utils.delete_object(folder_key=f'{user_id}/{event_name}/', rollback=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))