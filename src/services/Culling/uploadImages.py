# from datetime import datetime, timedelta, timezone
# import os
# import shutil
# from uuid import uuid4
# from fastapi.responses import JSONResponse
# from fastapi import status
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.future import select
# from config.security import validate_images_and_storage
# from config.settings import get_settings
# from model.CullingFolders import CullingFolder
# from model.CullingImagesMetaData import TemporaryImageURL
# from model.User import User
# from utils.UpdateUserStorage import update_user_storage_in_db
# from utils.UpsertMetaDataToDB import insert_image_metadata_async

# settings = get_settings()

# async def upload_before_culling_images(db_session:AsyncSession, folder_id:str, user_id:str, images:list[str])->JSONResponse:
#     # Validate folder
#     folder_data = await db_session.execute(
#         select(CullingFolder).where(
#             CullingFolder.id == folder_id,
#             CullingFolder.user_id == user_id
#         )
#     )
    
#     folder_data = folder_data.scalar_one_or_none()
#     if not folder_data:
#         return JSONResponse(
#             status_code=status.HTTP_404_NOT_FOUND,
#             content=f'Folder with id {folder_id} not found!'
#         )
        
#     # Validate images and storage
#     storage_used = await db_session.execute(
#         select(User.total_culling_storage_used).where(User.id == user_id)
#     )
#     storage_used = storage_used.scalar_one_or_none()

#     is_valid, output_validated_storage = await validate_images_and_storage(
#         files=images, max_uploads=1000, max_size_mb=100, db_storage_used=storage_used
#     )

#     if not is_valid:
#         return JSONResponse(
#             status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
#             content=output_validated_storage
#         )
    
#     # Save the images locally before culling.
    
#     # Ensure culling_workspaces folder exists
#     base = os.path.join("static", "culling_workspaces")
#     workspace = os.path.join(base, user_id, folder_id)
#     os.makedirs(workspace, exist_ok=True)

#     images_metadata = []
#     for image in images:
#         filename = f"{uuid4()}_{image.filename}"
#         file_path = os.path.join(workspace, filename)

#         content = await image.read()
#         with open(file_path, "wb") as f:
#             f.write(content)

#         validity = datetime.now(timezone.utc) + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC)
#         images_metadata.append({
#             "name": filename,
#             "file_type": image.content_type,
#             "url": f"{settings.APP_HOSTED_URL}/{file_path}",
#             "validity": validity,
#             "culling_folder_id": folder_id,
#         })

#     updated_folder_storage = folder_data.total_size + output_validated_storage

#     try:
#         # 1) bulk‐insert your metadata
#         await insert_image_metadata_async(
#             db_session=db_session,
#             bulk_insert_fields=images_metadata,
#             model=TemporaryImageURL
#         )

#         # 2) bump the folder size
#         folder_data.total_size = updated_folder_storage
#         db_session.add(folder_data)

#         # 3) update user’s total storage
#         await update_user_storage_in_db(
#             db_session=db_session,
#             total_image_size=output_validated_storage,
#             module=settings.APP_SMART_CULL_MODULE,
#             user_id=user_id,
#             increment=True
#         )

#         return JSONResponse(
#             content={"message":"Images uploaded successfully"}
#         )


#     except Exception as e:
#         # Roll back DB work
#         await db_session.rollback()

#         # Delete any files we wrote
#         # for meta in images_metadata:
#         try:
#             shutil.rmtree(workspace)
#         except OSError:
#             pass

#         # Return the error to the client
#         return JSONResponse(
#             status_code=getattr(e, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR),
#             content={"detail": str(e)}
#         )

#     # try:
#     #     # Pass the folder path and image paths to Celery instead of raw image data
#         # task = upload_preculling_images_and_insert_metadata.apply_async(
#     #         args=[user_id, image_paths, folder_data.name, folder_data.id, output_validated_storage]
#     #     )
        
#     # except Exception as e:
#     #     raise HTTPException(
#     #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
#     #         detail=f"Error sending upload images task to Celery: {str(e)}"
#     #     )
    
    
#     # updating the workspace storage
#     # folder_data.total_size = updated_folder_storage
    
#     # db_session.add(folder_data)
#     # match_criteria = {"id": folder_id, "name": folder_data.name, "user_id": user_id}
#     # workspace_response = await upsert_folder_metadata_DB(
#     #     db_session=db_session,
#     #     match_criteria=match_criteria,
#     #     update_fields={"total_size": updated_folder_storage, "uploading_in_progress": True, "uploading_task_id": task.id},
#     #     model=CullingFolder,
#     #     update=True
#     # )
    
#     # updating user storage
#     # if workspace_response.get('status') == 'COMPLETED':
#     # updating the user storage
#     # await update_user_storage_in_db(
#     #     db_session=db_session,
#     #     total_image_size=output_validated_storage,
#     #     module=settings.APP_SMART_CULL_MODULE,
#     #     user_id=user_id,
#     #     increment=True
#     # )
        
#     # return JSONResponse({"": })