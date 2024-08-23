from fastapi import APIRouter, HTTPException,status,Depends,UploadFile,File,Request
from fastapi.responses import JSONResponse
from config.Database import get_db
from config.security import validate_images_and_storage
from model.FolderInS3 import FoldersInS3
from model.User import User
from schemas.cullingData import cullingData
from schemas.imageMetaDataResponse import ImageMetaDataResponse
from services.Auth.google_auth import get_user
from sqlalchemy.orm import Session
from config.settings import get_settings
from services.Culling.deleteFolderFromS3 import delete_folder_in_s3_and_update_DB
from services.SmartShare.createEvent import create_event_in_S3_store_meta_to_DB
from services.SmartShare.getImagesByFaceRecog import get_images_by_face_recog
from services.SmartShare.imagePreProcessEmbeddings import preprocess_image_before_embedding
from services.SmartShare.tasks.imageShareTask import image_share_task
from utils.QdrantUtils import QdrantUtils
from utils.S3Utils import S3Utils
from typing import List

 


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
def create_event(event_name:str, request:Request, db_session:Session = Depends(get_db)):
    return create_event_in_S3_store_meta_to_DB(request=request, event_name=event_name.lower(), s3_utils_obj=s3_utils, db_session=db_session)


@router.post('/upload-images/{folder}', status_code=status.HTTP_202_ACCEPTED)
async def upload_images(request: Request, event_name: str, images: list[UploadFile] = File(...), db_session: Session = Depends(get_db), user: User = Depends(get_user)):

    user_id = request.session.get("user_id")
    event_name = event_name.lower()

    # Checking if that folder exists in the database or not
    folder_data = db_session.query(FoldersInS3).filter(FoldersInS3.name == event_name, FoldersInS3.module == settings.APP_SMART_SHARE_MODULE, FoldersInS3.user_id == user_id).first()
    if not folder_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find folder with {event_name} in smart share')


    # Validation if combined size of images is greater than available size and check image validation
    storage_used = db_session.query(User.total_culling_storage_used).filter(User.id == user_id).scalar()
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
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    
    return response
    
@router.post('/share_images',status_code=status.HTTP_102_PROCESSING)
async def share_images(culling_data:cullingData, request:Request, db_session:Session = Depends(get_db)):

    user_id = request.session.get("user_id")
    folder_data = db_session.query(FoldersInS3).filter(FoldersInS3.name == culling_data.folder_name, FoldersInS3.module == settings.APP_SMART_SHARE_MODULE, FoldersInS3.user_id == user_id).first()
    if not folder_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find folder with \'{culling_data.folder_name}\' in smart share')
    
    if len(culling_data.images_url) == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'image url not provided !')

    #Sending images URL and other info to Celery task
    try:
        task = image_share_task.apply_async(args=[user_id, culling_data.images_url, culling_data.folder_name ])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending task to Celery: {str(e)}")

    return JSONResponse({"task_id": task.id})


@router.delete('/delete_event/{event_name}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_name:str, request:Request, session:Session =  Depends(get_db)):

    user_id = request.session.get('user_id')
    folder_path = f'{user_id}/{event_name}/'
    try:
        s3_DB_response = delete_folder_in_s3_and_update_DB(del_folder_path=folder_path,
                                                            db_session=session, 
                                                            s3_obj=s3_utils,
                                                            module=settings.APP_SMART_SHARE_MODULE,
                                                            user_id=user_id
                                                        )
        
        qdrant_response = qdrant_util.remove_collection(collection_name=event_name)
        if not qdrant_response:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Collection {event_name} is not found")
        
        return s3_DB_response

    except HTTPException as e:
        # Handle specific HTTP exceptions if needed
        raise e

    except Exception as e:
        # Handle other exceptions and provide a generic error message
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    

@router.post('/get_images',status_code=status.HTTP_200_OK, response_model=List[ImageMetaDataResponse])
async def get_images(event_name:str, request:Request, image: UploadFile = File(...), session:Session =  Depends(get_db)):
    user_id = request.session.get('user_id')

    return await get_images_by_face_recog(db_session=session,
                                            event_name=event_name,
                                            image=image,
                                            qdrant_util=qdrant_util,
                                            user_id=user_id
                                        )

