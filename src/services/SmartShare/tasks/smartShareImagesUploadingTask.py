from datetime import datetime, timedelta
from io import BytesIO
import os
import shutil
from src.config.settings import get_settings
from src.Celery.utils import create_celery
import asyncio
from src.config.syncDatabase import celery_sync_session
from src.model.SmartShareFolders import SmartShareFolder
from src.model.SmartShareImagesMetaData import SmartShareImagesMetaData
from src.utils.S3Utils import S3Utils
from src.utils.UpdateUserStorage import sync_update_user_storage_in_db
from src.utils.UpsertMetaDataToDB import insert_image_metadata, sync_upsert_folder_metadata_DB
from tqdm import tqdm

#-----instances----
celery = create_celery()
settings = get_settings()
s3_utils = S3Utils(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_region=settings.AWS_REGION,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    bucket_name=settings.AWS_BUCKET_SMART_SHARE_NAME,
                    aws_endpoint_url=settings.AWS_ENDPOINT_URL)

############## Function to upload images to S3 bucket ##############
async def upload_image(image_path, user_id, event_name):
    filename = os.path.basename(image_path)
    
    print("\n\n\n image_path", image_path)
    print("\n file_name", filename)

    # Read file content
    with open(image_path, "rb") as file:
        image_data = file.read()
    
    key = f"{user_id}/{event_name}/{filename}"
    try:
        # Upload the image to S3
        await s3_utils.upload_smart_share_images(
            filename=filename,
            root_folder=user_id,
            event_folder=event_name,
            image_data=BytesIO(image_data)
        )
        # Generate a presigned URL for the uploaded image
        presigned_url = await s3_utils.generate_presigned_url(
            key, 
            expiration=settings.PRESIGNED_URL_EXPIRY_SEC
        )
    except Exception as e:
        raise Exception(f"Error uploading image to S3: {str(e)}")
    
    # Prepare metadata for this image as a dictionary
    return {
            'id': filename,
            'name': filename.split("_")[1],
            'file_type': filename.split(".")[1],
            'image_download_path': presigned_url,
            'image_download_validity': datetime.now() + timedelta(seconds=settings.PRESIGNED_URL_EXPIRY_SEC),
        }


def rollback_changes(user_id, event_id, event_name, output_validated_storage):
    """Rollback the event metadata like, size, upload_in_progress attribute to previous state"""
    with celery_sync_session() as db_session:
        match_criteria = {"id": event_id, "name": event_name, "user_id": user_id}
        workspace_response = sync_upsert_folder_metadata_DB(
            db_session=db_session,
            match_criteria=match_criteria,
            update_fields={"total_size": 0, "uploading_in_progress": False, "uploading_task_id": None},
            model=SmartShareFolder,
            update=True
        )
        if workspace_response.get('status') == 'COMPLETED':
            sync_update_user_storage_in_db(
                db_session=db_session,
                total_image_size=output_validated_storage,
                module=settings.APP_SMART_SHARE_MODULE,
                user_id=user_id,
                increment=False
            )


######################################### Uploading images before culling and inserting metadata #########################################
@celery.task(name='upload_event_images_and_insert_metadata', bind=True, acks_late=True, queue='smart_sharing', )
def upload_event_images_and_insert_metadata(self, user_id, image_paths, event_name, event_id, output_validated_storage):
    self.update_state(state='STARTED', meta={'status': 'Task started'})
    
    presigned_image_record = []
    total_images = len(image_paths)

    # Uploading Images
    with tqdm(total=total_images, desc="Uploading images", bar_format="{l_bar}{bar} [ time left: {remaining}, time spent: {elapsed}]", unit="image") as progress_bar:
        for index, image in enumerate(image_paths):
            try:
                response = asyncio.run(upload_image(image_path=image, event_name=event_name, user_id=user_id))

                # Convert datetime fields to strings
                for key, value in response.items():
                    if isinstance(value, datetime):
                        response[key] = value.isoformat()

                presigned_image_record.append(response)
                
                progress_bar.update(1)
                elapsed_time = progress_bar.format_dict.get("elapsed", 0)
                # Calculate remaining time manually since it's not directly accessible
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
                rollback_changes(user_id, event_id, event_name, output_validated_storage)
                asyncio.run(s3_utils.delete_object(folder_key=f"{user_id}/{event_name}", rollback=True))

                self.update_state(state="FAILURE", meta={"status": "Failed to upload images", "error": str(e)})
                raise e  # Explicitly raise an exception

    progress_bar.close()

    # Inserting valid metadata record to database
    valid_records = [
        {**record, "smart_share_folder_id": event_id}
        for record in presigned_image_record if isinstance(record, dict)
    ]

    try:
        with celery_sync_session() as db_session:
            # Convert datetime fields in metadata before inserting into DB
            for record in valid_records:
                for key, value in record.items():
                    if isinstance(value, datetime):
                        record[key] = value.isoformat()

            # insert images metadata to database
            metadata_response = insert_image_metadata(
                db_session=db_session,
                bulk_insert_fields=valid_records,
                model=SmartShareImagesMetaData
            )
            if(metadata_response.get("status")=="COMPLETED"):
                match_criteria = {"id": event_id, "name": event_name, "user_id": user_id}
                sync_upsert_folder_metadata_DB(
                    db_session=db_session,
                    match_criteria=match_criteria,
                    update_fields={"uploading_in_progress": False, "uploading_task_id": None},
                    model=SmartShareFolder,
                    update=True
                )
            
    except Exception as e:
        rollback_changes(user_id, event_id, event_name, output_validated_storage)
        asyncio.run(s3_utils.delete_object(folder_key=f"{user_id}/{event_name}", rollback=True))

        self.update_state(state="FAILURE", meta={"status": "Database error", "error": str(e)})
        raise e # Ensure Celery knows it failed
    
    # Task Completion State (Fix datetime serialization)
    self.update_state(
        state="SUCCESS",
        meta={
            "status": "Uploaded image successfully",
            "totalImages": len(presigned_image_record),
            "urls": [record.get("image_download_path") for record in presigned_image_record if "image_download_path" in record]
        }
    )
    
    # Cleanup: Remove the folder containing the images if event_folder is provided
    try:
        # If event_folder was passed in explicitly, use it; otherwise, derive from the first image path.
        folder_to_remove = os.path.join("static", "smart_share_events", str(user_id), str(event_id))
        shutil.rmtree(folder_to_remove)
    except Exception as cleanup_error:
        # Log the error; you might want to use proper logging in production instead of print.
        print(f"Error cleaning up folder {folder_to_remove}: {cleanup_error}")
    
    
    return presigned_image_record