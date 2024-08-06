from datetime import datetime, timezone


async def save_image_metadata_to_DB(DBModel, img_id, img_filename, img_content_type, user_id, bucket_folder, session):
    try:
        save_metadata_to_db = DBModel(
            id=img_id,
            name=img_filename,
            file_type=img_content_type,
            upload_at = datetime.now(tz=timezone.utc),
            Bucket_folder = bucket_folder,
            user_id=user_id
        )
        session.add(save_metadata_to_db)
        session.commit()
        session.refresh(save_metadata_to_db)
    except Exception as e:
        raise Exception(f"Error saving image metadata: {str(e)}")
    
    return {"status": "success", "data": {"id": img_id, "name": img_filename}}