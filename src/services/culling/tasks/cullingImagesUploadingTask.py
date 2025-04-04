from datetime import datetime, timedelta, timezone
from io import BytesIO
import os
import shutil
from config.settings import get_settings
from Celery.utils import create_celery
import asyncio

from config.syncDatabase import celery_sync_session
from model.CullingFolders import CullingFolder
from model.CullingImagesMetaData import TemporaryImageURL
from utils.S3Utils import S3Utils
from tqdm import tqdm

from utils.UpdateUserStorage import sync_update_user_storage_in_db
from utils.UpsertMetaDataToDB import insert_image_metadata, sync_upsert_folder_metadata_DB


#-----instances----
celery = create_celery()
settings = get_settings()
s3_utils = S3Utils(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_region=settings.AWS_REGION,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    bucket_name=settings.AWS_BUCKET_SMART_CULL_NAME,
                    aws_endpoint_url=settings.AWS_ENDPOINT_URL)


############## Function to upload images to S3 bucket ##############
async def upload_image(image_path, user_id, folder_name):
    filename = os.path.basename(image_path)

    # Read file content
    with open(image_path, "rb") as file:
        image_data = file.read()

    # Upload to S3
    await s3_utils.upload_smart_cull_images(
        filename=filename,
        root_folder=user_id,
        main_folder=folder_name,
        upload_image_folder=settings.IMAGES_BEFORE_CULLING_STARTS_Folder,
        image_data=BytesIO(image_data)
    )

    key = f"{user_id}/{folder_name}/{settings.IMAGES_BEFORE_CULLING_STARTS_Folder}/{filename}"
    presigned_url = await s3_utils.generate_presigned_url(key, expiration=settings.PRESIGNED_URL_EXPIRY_SEC)
    validity = datetime.now(tz=timezone.utc) + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC)

    return {"name": filename, "file_type": "image/jpeg", "url": presigned_url, "validity": validity}


def rollback_changes(user_id, workspace_id, folder_name, output_validated_storage):
    with celery_sync_session() as db_session:
        match_criteria = {"id": workspace_id, "name": folder_name, "user_id": user_id}
        workspace_response = sync_upsert_folder_metadata_DB(
            db_session=db_session,
            match_criteria=match_criteria,
            update_fields={"total_size": 0, "uploading_in_progress": False, "uploading_task_id": None},
            model=CullingFolder,
            update=True
        )
        if workspace_response.get('status') == 'COMPLETED':
            sync_update_user_storage_in_db(
                db_session=db_session,
                total_image_size=output_validated_storage,
                module=settings.APP_SMART_CULL_MODULE,
                user_id=user_id,
                increment=False
            )


######################################### Uploading images before culling and inserting metadata #########################################
@celery.task(
    name='upload_preculling_images_and_insert_metadata', 
    bind=True,  
    acks_late=True,  # Ensures failure aborts the task
    queue="culling"
)
def upload_preculling_images_and_insert_metadata(self, user_id, image_paths, folder_name, workspace_id, output_validated_storage):
    self.update_state(state='STARTED', meta={'status': 'Task started'})
    
    presigned_image_record = []
    total_images = len(image_paths)

    with tqdm(total=total_images, desc="Uploading images", bar_format="{l_bar}{bar} [ time left: {remaining}, time spent: {elapsed}]", unit="image") as progress_bar:
        for index, image in enumerate(image_paths):
            try:
                response = asyncio.run(upload_image(image_path=image, folder_name=folder_name, user_id=user_id))
                response = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in response.items()}
                presigned_image_record.append(response)
                progress_bar.update(1)
                elapsed_time = progress_bar.format_dict.get("elapsed", 0)
                remaining_time = ((total_images - progress_bar.n) / (progress_bar.n / elapsed_time)) if elapsed_time > 0 and progress_bar.n > 0 else 0
                
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": index + 1,
                        "total": total_images,
                        "progress": f"{progress_bar.n / total_images * 100:.2f}%",
                        "elapsed_time": elapsed_time,
                        "remaining_time": remaining_time,
                    }
                )
            except Exception as e:
                rollback_changes(user_id, workspace_id, folder_name, output_validated_storage)
                asyncio.run(s3_utils.delete_object(folder_key=f"{user_id}/{folder_name}/{settings.IMAGES_BEFORE_CULLING_STARTS_Folder}", rollback=True))

                self.update_state(state="FAILURE", meta={"status": "Failed to upload images", "error": str(e)})
                raise e  # Explicitly raise an exception

    progress_bar.close()
    valid_records = [{**record, "culling_folder_id": workspace_id} for record in presigned_image_record if isinstance(record, dict)]
    
    try:
        with celery_sync_session() as db_session:
            valid_records = [{k: v.isoformat() if isinstance(v, datetime) else v for k, v in record.items()} for record in valid_records]
            insert_image_metadata(db_session=db_session, bulk_insert_fields=valid_records, model=TemporaryImageURL)
            
            match_criteria = {"id": workspace_id, "name": folder_name, "user_id": user_id}
            sync_upsert_folder_metadata_DB(
                db_session=db_session,
                match_criteria=match_criteria,
                update_fields={"uploading_in_progress": False, "uploading_task_id": None},
                model=CullingFolder,
                update=True
            )
    except Exception as e:
        rollback_changes(user_id, workspace_id, folder_name, output_validated_storage)
        asyncio.run(s3_utils.delete_object(folder_key=f"{user_id}/{folder_name}/{settings.IMAGES_BEFORE_CULLING_STARTS_Folder}", rollback=True))

        self.update_state(state="FAILURE", meta={"status": "Database error", "error": str(e)})
        raise e # Ensure Celery knows it failed
        
    self.update_state(
        state="SUCCESS",
        meta={
            "status": "Uploaded images successfully",
            "totalImages": len(presigned_image_record),
            "urls": [record.get("url") for record in presigned_image_record if "url" in record]
        }
    )
    
    # Cleanup: Remove the folder containing the images if workspace_folder is provided
    try:
        # If workspace_folder was passed in explicitly, use it; otherwise, derive from the first image path.
        folder_to_remove = os.path.join("static", "culling_workspaces", str(user_id), str(workspace_id))
        shutil.rmtree(folder_to_remove)
    except Exception as cleanup_error:
        # Log the error; you might want to use proper logging in production instead of print.
        print(f"Error cleaning up folder {folder_to_remove}: {cleanup_error}")
    
    return presigned_image_record

