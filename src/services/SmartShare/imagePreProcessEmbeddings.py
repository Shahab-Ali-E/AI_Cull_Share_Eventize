import asyncio
from datetime import datetime, timedelta
from io import BytesIO
from uuid import uuid4
from fastapi import HTTPException,status
from sqlalchemy.ext.asyncio import AsyncSession
from config.settings import get_settings
from model.SmartShareImagesMetaData import SmartShareImagesMetaData

settings = get_settings()

async def preprocess_image_before_embedding(
    event_name: str,
    images: list,
    s3_utils,
    db_session: AsyncSession,
    user_id: str,
    folder_id: int
):
    """
    Processes a list of images before embedding, uploads them to an AWS S3 bucket, 
    and updates metadata and user storage in the database.

    :param images: List of images to be uploaded.
    :param s3_utils: Utility class for S3 operations.
    :param user_id: The ID of the user uploading the images.
    :param event_name: The name of the folder in S3 where images will be stored.
    :param db_session: SQLAlchemy session for database operations.
    :param folder_id: The folder id to which images are associated with.

    Returns:
    - A list containing the presigned URL metadata for each successfully uploaded image.
    """

    async def upload_image(image):
        # Generate a unique filename
        filename = f'{uuid4()}_{image.filename}'
        try:
            # Read image data
            image_data = await image.read()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Error reading image file: {str(e)}"
            )

        try:
            # Upload the image to S3
            await s3_utils.upload_smart_share_images(
                filename=filename,
                root_folder=user_id,
                event_folder=event_name,
                image_data=BytesIO(image_data)
            )
            # Construct the S3 key
            key = f"{user_id}/{event_name}/{filename}"
            # Generate a presigned URL for the uploaded image
            presigned_url = await s3_utils.generate_presigned_url(
                key, 
                expiration=settings.PRESIGNED_URL_EXPIRY_SEC
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=f"Error uploading image to S3: {str(e)}"
            )

        # Prepare metadata for this image as a dictionary
        img_data = {
            'id': filename,
            'name': image.filename,
            'file_type': image.content_type,
            'image_download_path': presigned_url,
            'image_download_validity': datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
            'smart_share_folder_id': folder_id
        }
        return img_data

    # Process image uploads concurrently
    upload_tasks = [upload_image(image) for image in images]
    results = await asyncio.gather(*upload_tasks, return_exceptions=True)

    valid_records = []
    presigned_image_record = []
    for result in results:
        if isinstance(result, Exception):
            # Optionally log or handle the error for the failed image upload
            continue
        presigned_image_record.append(result)
        # Convert dictionary to ORM model instance
        record_instance = SmartShareImagesMetaData(
            id=result['id'],
            name=result['name'],
            file_type=result['file_type'],
            image_download_path=result['image_download_path'],
            image_download_validity=result['image_download_validity'],
            smart_share_folder_id=result['smart_share_folder_id']
        )
        valid_records.append(record_instance)

    try:
        # Add all ORM model instances to the session
        db_session.add_all(valid_records)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  
            detail=str(e)
        )

    return presigned_image_record
    
    