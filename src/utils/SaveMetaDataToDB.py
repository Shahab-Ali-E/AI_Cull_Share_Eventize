from datetime import datetime, timezone
from model import FolderInS3, ImagesMetaData
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


def save_image_metadata_to_DB(img_id, img_filename, img_content_type, user_id, bucket_folder, session, folder_id):
    try:
        save_metadata_to_db = ImagesMetaData.ImagesMetaData(
            id=img_id,
            name=img_filename,
            file_type=img_content_type,
            upload_at = datetime.now(tz=timezone.utc),
            Bucket_folder = bucket_folder,
            user_id=user_id,
            folder_id=folder_id
        )
        session.add(save_metadata_to_db)
        session.commit()
        session.refresh(save_metadata_to_db)
    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"Error saving image metadata: {str(e)}")
    
    return {"status": "success", "data": {save_metadata_to_db}}




def save_or_update_metadata_in_db(session: Session, match_criteria: dict, update_fields: dict=None, task:str='insert'):
    """
    Save or update metadata in the database.

    :param session: SQLAlchemy session for database operations.
    :param match_criteria: Dictionary specifying the fields to match for an update.
    :param update_fields: Dictionary specifying the fields to update or insert.
    :param task: Specify the task you want to perform either update or insert.
    :return: Dictionary with the status and data or error message.
    """
    try:
        if task=='update':
            # Check if the record already exists
            existing_record = session.query(FolderInS3.FoldersInS3).filter_by(**match_criteria).first()
            if not existing_record:
                raise HTTPException(status_code=404, detail="no record found")
            
            # Update only the specified fields
            for key, value in update_fields.items():
                setattr(existing_record, key, value)
            session.commit()
            session.refresh(existing_record)
            return {"status": "success", "data": existing_record}
        
        else:
            # Create a new record
            new_record_data = {**match_criteria}
            new_record = FolderInS3.FoldersInS3(**new_record_data)
            session.add(new_record)
            session.commit()
            session.refresh(new_record)
            return {"status": "success", "data": new_record}

    except SQLAlchemyError as e:
        session.rollback()
        raise Exception(f"Error saving or updating metadata: {str(e)}")