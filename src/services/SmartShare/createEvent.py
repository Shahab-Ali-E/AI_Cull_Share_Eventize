from config.settings import get_settings
from fastapi import HTTPException, status
from utils.SaveMetaDataToDB import upsert_folder_metadata_DB
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

#instance of settings
settings = get_settings()

async def create_event_in_S3_and_DB(event_name:str, user_id:str, request:Request, s3_utils_obj, qdrant_util_obj, db_session: AsyncSession):
    #creating folder in S3
    try:
        await s3_utils_obj.create_folders_for_smart_share(root_folder=user_id, event_name=event_name)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')

    #save created folder meta data in DB
    location_in_s3 = f'{settings.AWS_BUCKET_SMART_SHARE_NAME}/{user_id}/{event_name}'
    match_criteria = {'name':event_name, 'location_in_s3':location_in_s3, 'module':settings.APP_SMART_SHARE_MODULE, 'user_id':user_id}

    try:
        await upsert_folder_metadata_DB(
                                            db_session=db_session,
                                            match_criteria=match_criteria
                                        )
    except Exception as e:
        db_session.rollback()
        # Rollback S3 operation if DB operation fails
        try:
            await s3_utils_obj.delete_object(folder_key=f'{user_id}/{event_name}')
        except Exception as rollback_exception:
            # Log the rollback failure and raise an error with details
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                                detail=f"Failed to save metadata in DB and rollback S3 operation failed: {str(rollback_exception)}. "
                                       f"Original error: {str(e)}")
        
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')