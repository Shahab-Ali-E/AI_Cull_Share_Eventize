from config.settings import get_settings
from fastapi import HTTPException,status
from utils.UpsertMetaDataToDB import upsert_folder_metadata_DB
from model.FolderInS3 import FoldersInS3
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

settings = get_settings()

async def create_folder_in_S3(dir_name:str, s3_utils_obj, db_session:AsyncSession, user_id:str):
    
    #checking if that folder already exsists in Database
    try:
        folder_exists = (await db_session.scalars(select(FoldersInS3).where(FoldersInS3.name == dir_name,
                                                                            FoldersInS3.module == settings.APP_SMART_CULL_MODULE,
                                                                            FoldersInS3.user_id == user_id
                                                                            ))).first()

        if folder_exists:
            raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=f'folder with name {dir_name} already exsits')
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')
    
    #creating folder in S3
    try:
        await s3_utils_obj.create_folders_for_culling(  root_folder=user_id, 
                                                        main_folder=dir_name, 
                                                        images_before_cull_folder=settings.IMAGES_BEFORE_CULLING_STARTS_Folder,
                                                        blur_img_folder=settings.BLUR_FOLDER,
                                                        closed_eye_img_folder=settings.CLOSED_EYE_FOLDER,
                                                        duplicate_img_folder=settings.DUPLICATE_FOLDER,
                                                        fine_collection_img_folder=settings.FINE_COLLECTION_FOLDER
                                                    )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'sadsdasd{str(e)}')
    
    #save metadata to DB of created folder in S3
    folder_loc_in_s3 = f'{settings.AWS_BUCKET_SMART_CULL_NAME}/{user_id}/{dir_name}'
    match_criteria = {"name": dir_name, "user_id": user_id, "module":settings.APP_SMART_CULL_MODULE, 'location_in_s3':folder_loc_in_s3}
    try:
        await upsert_folder_metadata_DB(db_session=db_session,
                                        match_criteria=match_criteria
                                        )
    except Exception as e:
        await s3_utils_obj.delete_object(folder_key=f'{user_id}/{dir_name}/')
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'343434{str(e)}')

