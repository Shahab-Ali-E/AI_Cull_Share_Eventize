from config.settings import get_settings
from fastapi import HTTPException, status
from model.FolderInS3 import FoldersInS3
from utils.SaveMetaDataToDB import save_or_update_metadata_in_db

#instance of settings
settings = get_settings()

def create_event_in_S3_store_meta_to_DB(event_name, request, s3_utils_obj, db_session):
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access')
    
    #creating folder in S3
    try:
        s3_utils_obj.create_folders_for_smart_share(root_folder=user_id, event_name=event_name)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')

    #save created folder meta data in DB
    location_in_s3 = f'{settings.AWS_BUCKET_SMART_SHARE_NAME}/{user_id}/{event_name}'
    match_criteria = {'name':event_name, 'location_in_s3':location_in_s3, 'module':settings.APP_SMART_SHARE_MODULE, 'user_id':user_id}
    try:
        save_or_update_metadata_in_db(
                                        session=db_session,
                                       match_criteria=match_criteria
                                    )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')