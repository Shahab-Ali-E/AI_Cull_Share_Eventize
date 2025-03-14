import os
import shutil
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from config.settings import get_settings
from fastapi import HTTPException, status

from model.SmartShareFolders import SmartShareFolder
from utils.UpdateUserStorage import update_user_storage_in_db

settings = get_settings()

async def delete_event_s3_db_collection(db_session:AsyncSession, s3_utils_obj, user_id:str, event_name:str):

    # Retrieve event metadata from the database
    event_data = (await db_session.scalars(select(SmartShareFolder).where(SmartShareFolder.name == event_name,
                                                                      SmartShareFolder.user_id == user_id))).first()

    # Raise an error if the event is not found in the database
    if not event_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with name '{event_name}' not found in database"
        )

    # Attempt to delete the event from Database
    try:        
        # Attempt to delete the event from Database
        await db_session.delete(event_data)
        
        # Decrease the user's storage usage in the database
        _,db_response_message = await update_user_storage_in_db(
            module=settings.APP_SMART_SHARE_MODULE,
            db_session=db_session,
            total_image_size=event_data.total_size,
            user_id=user_id,
            increment=False
        )

        # Attempt to delete the event from S3
        folder_path = f'{user_id}/{event_name}/' 
        s3_response, status_code = await s3_utils_obj.delete_object(folder_key=folder_path)

        # Check S3 deletion response
        if status_code == 404:
            await db_session.rollback()
            raise HTTPException(
                status_code=status_code,
                detail=s3_response
            )
        
        
        # Remove local folder of smart share event
        folder_path = os.path.join("src", "services", "SmartShare", "Smart_Share_Events_Data", f"{event_data.id}")
        shutil.rmtree(folder_path, ignore_errors=True)
    
    except HTTPException as e:
        await db_session.rollback()
        raise e
        
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error occurred: {str(e)}"
        )

    return s3_response, db_response_message
    