from fastapi.responses import JSONResponse
from config.settings import get_settings
from fastapi import HTTPException,status
from utils.CustomExceptions import FolderAlreadyExistsException
from utils.UpsertMetaDataToDB import upsert_folder_metadata_DB
from model.CullingFolders import CullingFolder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

settings = get_settings()

async def create_folder_in_S3(dir_name:str, s3_utils_obj, db_session:AsyncSession, user_id:str):
    
    #checking if that folder already exsists in Database
    try:
        folder_exists = (await db_session.scalars(select(CullingFolder).where(CullingFolder.name == dir_name,
                                                                            CullingFolder.user_id == user_id
                                                                            ))).first()

        if folder_exists:
            return JSONResponse(
                    status_code=status.HTTP_406_NOT_ACCEPTABLE,
                    content=f'Folder with name {dir_name} already exsits'
                )
            
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
    
    # if it already exsists in the s3 then we will delete it, for only in those case if the s3 folder metadata was not found in our database
    except FolderAlreadyExistsException as e:
        try:
            await s3_utils_obj.delete_object(folder_key=f'{user_id}/{dir_name}/')
            
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')
    
    #save metadata to DB of created folder in S3
    folder_path_in_s3 = f'{settings.AWS_BUCKET_SMART_CULL_NAME}/{user_id}/{dir_name}'
    match_criteria = {"name": dir_name, "user_id": user_id, 'path_in_s3':folder_path_in_s3}
    try:
        await upsert_folder_metadata_DB(db_session=db_session,
                                        match_criteria=match_criteria,
                                        model=CullingFolder
                                        )
    except Exception as e:
        await s3_utils_obj.delete_object(folder_key=f'{user_id}/{dir_name}/')
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')

