from config.settings import get_settings
from fastapi import HTTPException, status
from model.FolderInS3 import FoldersInS3
from utils.SaveMetaDataToDB import save_or_update_metadata_in_db

#instance of settings
settings = get_settings()

def create_event_in_S3_store_meta_to_DB(event_name, request, s3_utils_obj, db_session):
    user_id = request.session.get('user_id')
    
    #creating folder in S3
    try:
        s3_utils_obj.create_folders_for_smart_share(root_folder=user_id, event_name=event_name)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')

    #save created folder meta data in DB
    location_in_s3 = f'{settings.AWS_BUCKET_SMART_SHARE_NAME}/{user_id}/{event_name}'
    try:
        save_or_update_metadata_in_db(DBModel=FoldersInS3,
                                             module_name='smart_share',
                                             folder_name=event_name,
                                             session=db_session,
                                             user_id=user_id,
                                             location_in_s3=location_in_s3
                                    )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')