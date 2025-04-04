import os
from uuid import uuid4
from fastapi.responses import JSONResponse
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from config.security import validate_images_and_storage
from config.settings import get_settings
from model.CullingFolders import CullingFolder
from model.User import User
from services.Culling.tasks.cullingImagesUploadingTask import upload_preculling_images_and_insert_metadata
from utils.UpdateUserStorage import update_user_storage_in_db
from utils.UpsertMetaDataToDB import upsert_folder_metadata_DB

settings = get_settings()

async def upload_before_culling_images(db_session:AsyncSession, folder_id:str, user_id:str, images:list[str])->JSONResponse:
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

    is_valid, output_validated_storage = await validate_images_and_storage(
        files=images, max_uploads=1000, max_size_mb=100, db_storage_used=storage_used
    )

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            content=output_validated_storage
        )
    
    # before sending images to celery save them locally and we will pass the path of images, due to celery won't take.
    
    # Ensure culling_workspaces folder exists
    local_folder = os.path.join("static", "culling_workspaces")
    os.makedirs(local_folder, exist_ok=True)

    # Create a single workspace folder for the user (e.g., /user_id/workspace_id/)
    workspace_folder = os.path.join(local_folder, user_id, folder_id)
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
    updated_folder_storage = folder_data.total_size + output_validated_storage

    try:
        # Pass the folder path and image paths to Celery instead of raw image data
        task = upload_preculling_images_and_insert_metadata.apply_async(
            args=[user_id, image_paths, folder_data.name, folder_data.id, output_validated_storage]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error sending upload images task to Celery: {str(e)}"
        )
    
    # updating the workspace storage
    folder_data.uploading_in_progress = True
    folder_data.uploading_task_id = task.id
    folder_data.total_size = updated_folder_storage
    
    db_session.add(folder_data)
    # match_criteria = {"id": folder_id, "name": folder_data.name, "user_id": user_id}
    # workspace_response = await upsert_folder_metadata_DB(
    #     db_session=db_session,
    #     match_criteria=match_criteria,
    #     update_fields={"total_size": updated_folder_storage, "uploading_in_progress": True, "uploading_task_id": task.id},
    #     model=CullingFolder,
    #     update=True
    # )
    
    # updating user storage
    # if workspace_response.get('status') == 'COMPLETED':
    # updating the user storage
    await update_user_storage_in_db(
        db_session=db_session,
        total_image_size=output_validated_storage,
        module=settings.APP_SMART_CULL_MODULE,
        user_id=user_id,
        increment=True
    )
        
    return JSONResponse({"task_id": task.id})