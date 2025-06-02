import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
from fastapi import UploadFile, HTTPException,status
from uuid import uuid4
from src.config.settings import get_settings
from src.model.CullingImagesMetaData import TemporaryImageURL
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()

async def pre_cull_image_processing(images:list[UploadFile], s3_utils, user_id:int, folder:str, culling_folder_id, db_session:AsyncSession):
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
    presigned_image_record = []

    async def upload_image(image):
        filename = f'{uuid4()}_{image.filename}'
        image_data = await image.read()
        await s3_utils.upload_smart_cull_images(
            filename=filename,
            root_folder=user_id,
            main_folder=folder,
            upload_image_folder=settings.IMAGES_BEFORE_CULLING_STARTS_Folder,
            image_data=BytesIO(image_data)
        )
        key = f"{user_id}/{folder}/{settings.IMAGES_BEFORE_CULLING_STARTS_Folder}/{filename}"
        presigned_url = await s3_utils.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)
        validity = datetime.now(tz=timezone.utc) + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC)
        
        return {"name":filename, "file_type":image.content_type , "url": presigned_url, "validity": validity}

    # Upload images concurrently
    upload_tasks = [upload_image(image) for image in images]
    presigned_image_record.extend(await asyncio.gather(*upload_tasks, return_exceptions=True))

    # inserting valid record to database
    valid_records = [
        TemporaryImageURL(
            name=record["name"],
            file_type=record["file_type"],
            url=record["url"],
            validity=record["validity"],
            culling_folder_id=culling_folder_id,
        )
        for record in presigned_image_record
        if isinstance(record, dict)  # Exclude failed uploads
    ]
    try:
        db_session.add_all(valid_records)

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  detail=str(e))
    
    return presigned_image_record
    # presigned_image_record = []

    # for image in images:
    #     filename = f'{uuid4()}_{image.filename}'
        
    #     #some image validation
    #     try:
    #         image_data = await image.read()
    #     except Exception as e:
    #         raise HTTPException(status_code=400, detail=f"Error reading image file: {str(e)}")
        

    #     #------S3 OPERATION-----
    #     try:
    #         await s3_utils.upload_smart_cull_images(
    #                                                     filename=filename,
    #                                                     root_folder=user_id,
    #                                                     main_folder=folder,
    #                                                     upload_image_folder=settings.IMAGES_BEFORE_CULLING_STARTS_Folder,
    #                                                     image_data=BytesIO(image_data)
    #                                                 )
    #         key = f"{user_id}/{folder}/{settings.IMAGES_BEFORE_CULLING_STARTS_Folder}/{filename}"
    #         presigned_url = await s3_utils.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)

    #         validity = (datetime.now(tz=timezone.utc) + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC)).isoformat()
    #         # Append the URL object to the list
    #         presigned_image_record.append({"url": presigned_url, "validity":validity})
           
    #     except Exception as e:
    #         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error uploading image to S3: {str(e)}")
        
    # #-----DATABASE OPERATION-----
    # try:
    #     # updating folder storage
    #     updated_folder_storage = storage_used_by_folder + total_image_size
        
    #     # Update the storage of the folder in the database
    #     match_criteria = {"id":folder_id, "name": folder, "user_id": user_id, "module": settings.APP_SMART_CULL_MODULE}
    #     await upsert_folder_metadata_DB(
    #         db_session=db_session,
    #         match_criteria=match_criteria,
    #         update_fields={"total_size": updated_folder_storage, "temporary_images_urls":presigned_image_record},
    #         update=True
    #     )

    #     # Update the user's storage in the database    
    #     is_valid, response = await update_user_storage_in_db(
    #         db_session=db_session,
    #         module=settings.APP_SMART_CULL_MODULE,
    #         total_image_size=total_image_size,
    #         user_id=user_id,
    #         increment=True
    #     )
    #     if not is_valid:
    #         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{response}")

    # except Exception as e:
    #     await db_session.rollback()
    #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {str(e)}")
   
    # return {
    #     'message': f'URLs are valid for {settings.PRESIGNED_URL_EXPIRY_SEC} seconds',
    #     'data': presigned_image_record
    # }