from typing import List
from fastapi.responses import JSONResponse
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.config.security import validate_images_and_storage_v2
from src.model.CullingFolders import CullingFolder
from src.model.CullingImagesMetaData import TemporaryImageURL
from src.model.User import User
from src.schemas.ImageMetaDataResponse import temporaryImagesMetadata
from src.utils.UpdateUserStorage import update_user_storage_in_db
from src.utils.UpsertMetaDataToDB import insert_image_metadata_async
from src.config.settings import get_settings



settings = get_settings()

async def save_pre_cull_images_metadata(db_session:AsyncSession, folder_id:str, user_id:str, images_metadata:List[temporaryImagesMetadata], combined_size:int)->JSONResponse:
    # Validate folder
    folder_data = await db_session.execute(
        select(CullingFolder).where(
            CullingFolder.id == folder_id,
            CullingFolder.user_id == user_id
        )
    )
    
    folder_data = folder_data.scalar_one_or_none()
    if not folder_data:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=f'Folder with id {folder_id} not found!'
        )
        
    # Validate images and storage
    storage_used = await db_session.execute(
        select(User.total_culling_storage_used).where(User.id == user_id)
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
        model=TemporaryImageURL
    )

    # 2) bump the folder size
    folder_data.total_size = combined_size
    db_session.add(folder_data)

    # 3) update user’s total storage
    await update_user_storage_in_db(
        db_session=db_session,
        total_image_size=output_validated_storage,
        module=settings.APP_SMART_CULL_MODULE,
        user_id=user_id,
        increment=True
    )

    return JSONResponse(
        content={"message":"Images metadata successfully"}
    )