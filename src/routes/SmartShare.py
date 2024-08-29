from fastapi import APIRouter, HTTPException,status,Depends,UploadFile,File,Request
from fastapi.responses import JSONResponse
from config.security import validate_images_and_storage
from model.FolderInS3 import FoldersInS3
from model.User import User
from schemas.cullingData import cullingData
from schemas.imageMetaDataResponse import ImageMetaDataResponse
from dependencies.user import get_user
from config.settings import get_settings
from services.SmartShare.createEvent import create_event_in_S3_and_DB
from services.SmartShare.deleteEvent import delete_event_s3_db_collection
from services.SmartShare.getImagesByFaceRecog import get_images_by_face_recog
from services.SmartShare.imagePreProcessEmbeddings import preprocess_image_before_embedding
from services.SmartShare.tasks.imageShareTask import image_share_task
from utils.QdrantUtils import QdrantUtils
from utils.S3Utils import S3Utils
from typing import List
from dependencies.core import DBSessionDep
from sqlalchemy.future import select
 


router = APIRouter(
    prefix='/smart-share',
    tags=['smart image share'],
)

#instance of settings
settings = get_settings()
#instance of S3
s3_utils = S3Utils(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_region=settings.AWS_REGION,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    bucket_name=settings.AWS_BUCKET_SMART_SHARE_NAME,
                    aws_endpoint_url=settings.AWS_ENDPOINT_URL)
#instance of Qdrat
qdrant_util = QdrantUtils()


@router.post('/create-event/{event_name}', status_code=status.HTTP_201_CREATED)
async def create_event(event_name:str, request:Request, db_session:DBSessionDep, user:User = Depends(get_user)):
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access')
    try:
        async with db_session.begin():
            response = await create_event_in_S3_and_DB(event_name=event_name.lower(), user_id=user_id, s3_utils_obj=s3_utils, db_session=db_session)
            await db_session.commit()
            return response
    
    except HTTPException as e:
        await db_session.rollback()
        raise HTTPException(status_code=e.status_code, detail=str(e))
    
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post('/upload-images/{folder}', status_code=status.HTTP_202_ACCEPTED)
async def upload_images(request: Request, event_name: str, db_session:DBSessionDep, images: list[UploadFile] = File(...), user: User = Depends(get_user)):

    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access')
    event_name = event_name.lower()

    try:
        async with db_session.begin():
            # Checking if that folder exists in the database or not
            folder_data = (await db_session.scalars(select(FoldersInS3).where(FoldersInS3.name == event_name,
                                                                    FoldersInS3.module == settings.APP_SMART_SHARE_MODULE,
                                                                    FoldersInS3.user_id == user_id
                                                                    ))).first()
            if not folder_data:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find folder with {event_name} in smart share')

            # Validation if combined size of images is greater than available size and check image validation
            storage_used = (await db_session.scalar(select(User.total_culling_storage_used).where(User.id == user_id)))
            is_valid, output = await validate_images_and_storage(
                                                                files=images, 
                                                                max_uploads=20, 
                                                                max_size_mb=100,
                                                                max_storage_size=settings.MAX_SMART_SHARE_MODULE_STORAGE,
                                                                db_storage_used=storage_used
                                                                )
            if not is_valid:
                raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=output)
            
            try:
                #uplaoding image to s3, updating meta data in database and return presinged url
                response  = await preprocess_image_before_embedding(event_name=event_name,
                                                                    images=images,
                                                                    s3_utils=s3_utils,
                                                                    db_session=db_session,
                                                                    total_image_size=output,
                                                                    user_id=user_id,
                                                                    folder_id=folder_data.id
                                                                    )
            except HTTPException as e:
                await db_session.rollback()
                raise HTTPException(status_code=e.status_code, detail=str(e))
            
            await db_session.commit()
            return response
    
    except HTTPException as e:
        await db_session.rollback()
        raise HTTPException(status_code=e.status_code, detail=str(e))

    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
    
@router.post('/share_images',status_code=status.HTTP_102_PROCESSING)
async def share_images(culling_data:cullingData, request:Request, db_session:DBSessionDep, user:User = Depends(get_user)):

    user_id = request.session.get("user_id")

    try:
        async with db_session.begin():
        # Checking if that folder exists in the database or not
            folder_data = (await db_session.scalars(select(FoldersInS3).where(FoldersInS3.name == culling_data.folder_name,
                                                                    FoldersInS3.module == settings.APP_SMART_SHARE_MODULE,
                                                                    FoldersInS3.user_id == user_id
                                                                    ))).first()
        if not folder_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find folder with \'{culling_data.folder_name}\' in smart share')
        
        if len(culling_data.images_url) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'image url not provided !')

        #Sending images URL and other info to Celery task     
        task = image_share_task.apply_async(args=[user_id, culling_data.images_url, culling_data.folder_name ])
        
        return JSONResponse({"task_id": task.id})
    
    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



@router.post('/get_images',status_code=status.HTTP_200_OK, response_model=List[ImageMetaDataResponse])
async def get_images(event_name:str, request:Request, db_session:DBSessionDep, image: UploadFile = File(...), user:User = Depends(get_user)):
    user_id = request.session.get('user_id')
    
    try:
        async with db_session.begin():
            response = await get_images_by_face_recog(db_session=db_session,
                                                        event_name=event_name,
                                                        image=image,
                                                        qdrant_util=qdrant_util,
                                                        user_id=user_id
                                                    )
            await db_session.commit()
            return response

    except HTTPException as e:
        await db_session.rollback()
        raise HTTPException(status_code=e.status_code, detail=str(e))

    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete('/delete_event/{event_name}', status_code=status.HTTP_200_OK)
async def delete_event(event_name:str, request:Request, db_session:DBSessionDep, user:User = Depends(get_user)):
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access')

    try:
        async with db_session.begin():
            response = await delete_event_s3_db_collection(db_session=db_session,
                                          event_name=event_name,
                                          qdrant_util_obj=qdrant_util,
                                          s3_utils_obj=s3_utils,
                                          user_id=user_id
                                          )
            await db_session.commit()
            return response
    except HTTPException as e:
        await db_session.rollback()
        raise HTTPException(status_code=e.status_code, detail=str(e))

    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
