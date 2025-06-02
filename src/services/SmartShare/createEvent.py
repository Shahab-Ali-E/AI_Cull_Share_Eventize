from src.config.settings import get_settings
from fastapi import HTTPException, status
from src.utils.CustomExceptions import FolderAlreadyExistsException
from src.utils.UpsertMetaDataToDB import upsert_folder_metadata_DB
from sqlalchemy.ext.asyncio import AsyncSession
from src.model.SmartShareFolders import SmartShareFolder       
from fastapi import UploadFile
import os
import uuid
from sqlalchemy import select

#instance of settings
settings = get_settings()

async def create_event_in_S3_and_DB(event_name:str, user_id:str, s3_utils_obj, db_session: AsyncSession,  event_cover_image:UploadFile=None):
    #creating folder in S3
    try:
        event_data = (await db_session.execute(select(SmartShareFolder).where(SmartShareFolder.name == event_name, SmartShareFolder.user_id == user_id))).scalar_one_or_none()
        
        if event_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"event with name {event_name} already exists !")
        
        try:
            await s3_utils_obj.create_folders_for_smart_share(root_folder=user_id, event_name=event_name)
        
        except FolderAlreadyExistsException as e:
            try:
                await s3_utils_obj.delete_object(folder_key=f'{user_id}/{event_name}/')
                await s3_utils_obj.create_folders_for_smart_share(root_folder=user_id, event_name=event_name)
                
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')
        
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')
        
        # Save cover image locally
        cover_image_url = ""
        if event_cover_image:
            # Ensure event_cover_images folder exists
            local_folder = os.path.join("static","event_cover_images") 
            os.makedirs(local_folder, exist_ok=True)

            # Generate unique filename
            file_extension = event_cover_image.filename.split(".")[-1]
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            local_file_path = os.path.join(local_folder, unique_filename)

            # Write file to the local folder
            with open(local_file_path, "wb") as file:
                file.write(await event_cover_image.read())

            # Simulate a publicly accessible URL
            cover_image_url = f"https://api.aicullshareeventizebackend.online/{local_folder}/{unique_filename}"
                
        #save created folder meta data in DB
        path_in_s3 = f'{settings.AWS_BUCKET_SMART_SHARE_NAME}/{user_id}/{event_name}'
        match_criteria = {'name':event_name, 'path_in_s3':path_in_s3, 'user_id':user_id, 'cover_image':cover_image_url}

        db_response = await upsert_folder_metadata_DB(
                                            db_session=db_session,
                                            match_criteria=match_criteria,
                                            model=SmartShareFolder
                                        )
        
        return db_response
    
    except HTTPException as e:
        await db_session.rollback()
        raise e
    
    except Exception as e:
        await db_session.rollback()
        await s3_utils_obj.delete_object(folder_key=f'{user_id}/{event_name}/')
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'{str(e)}')