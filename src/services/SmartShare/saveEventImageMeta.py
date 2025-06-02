from typing import List
from fastapi.responses import JSONResponse
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.config.security import validate_images_and_storage_v2
from src.model.SmartShareFolders import SmartShareFolder
from src.model.SmartShareImagesMetaData import SmartShareImagesMetaData
from src.model.User import User
from src.schemas.ImageMetaDataResponse import SmartShareEventImagesMeta
from src.utils.UpdateUserStorage import update_user_storage_in_db
from src.utils.UpsertMetaDataToDB import insert_image_metadata_async
from src.config.settings import get_settings

settings = get_settings()

async def save_event_images_metadata(db_session:AsyncSession, event_id:str, user_id:str, images_metadata:List[SmartShareEventImagesMeta], combined_size:int)->JSONResponse:
    # Validate event
    event = await db_session.execute(
        select(SmartShareFolder).where(
            SmartShareFolder.id == event_id,
            SmartShareFolder.user_id == user_id
        )
    )
    
    event_data = event.scalar_one_or_none()
    if not event_data:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=f'event with id {event_id} not found!'
        )
        
    # Validate images and storage
    storage_used = await db_session.execute(
        select(User.total_image_share_storage_used).where(User.id == user_id)
    )
    storage_used = storage_used.scalar_one_or_none()

    is_valid, output_validated_storage = await validate_images_and_storage_v2(
        images_metadata=images_metadata, max_uploads=1000, max_size_mb=100, db_storage_used=storage_used, combined_size=combined_size
    )

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            content=output_validated_storage
        )
    
    # 1) bulk‐insert your metadata
    bulk_data = [
        { **img.model_dump()}
        for img in images_metadata
    ]
    
    await insert_image_metadata_async(
        db_session=db_session,
        bulk_insert_fields=bulk_data,
        model=SmartShareImagesMetaData
    )

    # 2) bump the folder size
    event_data.total_size = combined_size
    db_session.add(event_data)

    # 3) update user’s total storage
    await update_user_storage_in_db(
        db_session=db_session,
        total_image_size=output_validated_storage,
        module=settings.APP_SMART_SHARE_MODULE,
        user_id=user_id,
        increment=True
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"message":"Images uploaded successfully"}
    )