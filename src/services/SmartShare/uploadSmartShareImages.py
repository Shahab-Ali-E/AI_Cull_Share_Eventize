import os
from uuid import uuid4
from fastapi import HTTPException, status, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.future import select
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from src.config.security import validate_images_and_storage
from src.config.settings import get_settings
from src.model.SmartShareFolders import SmartShareFolder
from src.model.User import User
from src.services.SmartShare.tasks.smartShareImagesUploadingTask import upload_event_images_and_insert_metadata
from src.utils.UpdateUserStorage import update_user_storage_in_db

settings = get_settings()

async def upload_smart_share_event_images(
    event_id: int,
    user_id: int,
    images: List[UploadFile],
    db_session: AsyncSession,
) -> JSONResponse:
    # Check if the folder exists in the database
    event_data = (
        await db_session.scalars(
            select(SmartShareFolder)
            .where(
                SmartShareFolder.id == event_id,
                SmartShareFolder.user_id == user_id
            )
        )
    ).first()
    
    if not event_data:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=f'Event with id {event_id} not found!'
        )

    # Validate combined image size and perform image validations
    storage_used = await db_session.scalar(
        select(User.total_image_share_storage_used)
        .where(User.id == user_id)
    )
    
    is_valid, output_validated_storage = await validate_images_and_storage(
        files=images, 
        max_uploads=1000, 
        max_size_mb=10,
        db_storage_used=storage_used
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, 
            detail=output_validated_storage
        )
    
        
    try:
        # before sending images to celery save them locally and we will pass the path of images, due to celery won't take large size of payload
        # Ensure culling_workspaces folder exists
        local_folder = os.path.join("static", "smart_share_events")
        os.makedirs(local_folder, exist_ok=True)

        # Create a single workspace folder for the user (e.g., /user_id/workspace_id/)
        workspace_folder = os.path.join(local_folder, user_id, event_id)
        os.makedirs(workspace_folder, exist_ok=True)

        image_paths = []  # List to store saved image file paths

        for image in images:
            filename = f"{uuid4()}_{image.filename}"  # Generate unique filename to avoid conflicts
            file_path = os.path.join(workspace_folder, filename)

            # Save image to workspace folder
            content = await image.read()  # Read file as bytes
            with open(file_path, "wb") as f:
                f.write(content)

            image_paths.append(file_path)  # Store file path

        # Calculate updated storage
        updated_folder_storage = event_data.total_size + output_validated_storage
        task = upload_event_images_and_insert_metadata.apply_async(
            args=[
                user_id,
                image_paths,
                event_data.name,
                event_data.id,
                output_validated_storage
            ]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error sending upload images task to Celery: {str(e)}"
        )

    # Update event data in the database
    event_data.uploading_in_progress = True
    event_data.uploading_task_id = task.id
    event_data.total_size = updated_folder_storage
    db_session.add(event_data)
    
    await update_user_storage_in_db(
        db_session=db_session,
        total_image_size=output_validated_storage,
        module=settings.APP_SMART_SHARE_MODULE,
        user_id=user_id,
        increment=True
    )
    
    return JSONResponse({"task_id": task.id})
