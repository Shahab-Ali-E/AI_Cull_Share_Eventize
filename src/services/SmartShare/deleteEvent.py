from services.Culling.deleteFolderFromS3 import delete_s3_folder_and_update_db
from sqlalchemy.ext.asyncio import AsyncSession
from config.settings import get_settings
from fastapi import HTTPException, status

settings = get_settings()

async def delete_event_s3_db_collection(db_session:AsyncSession, s3_utils_obj, qdrant_util_obj, user_id:str, event_name:str):
    folder_path = f'{user_id}/{event_name}/'   
    try:
        s3_res, db_res = await delete_s3_folder_and_update_db(
            del_folder_path=folder_path,
            db_session=db_session, 
            s3_obj=s3_utils_obj,
            module=settings.APP_SMART_SHARE_MODULE,
            user_id=user_id
        )
    except HTTPException as e:
        await db_session.rollback()
        raise e
    except Exception as e:
        await db_session.rollback()
        # Handle any other exceptions
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error occurred: {str(e)}"
        )
    
    try:
        qdrant_response = qdrant_util_obj.remove_collection(collection_name=event_name)
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing collection from Qdrant: {str(e)}"
        )
    
    return {'s3 response':s3_res,'Database response':db_res,'collection_deleted':qdrant_response}