from fastapi import APIRouter, HTTPException,status,Depends,UploadFile,File,Request
from fastapi.responses import JSONResponse
from config.Database import get_db
from config.security import validate_images_and_storage
from model.FolderInS3 import FoldersInS3
from model.User import User
from services.Auth.google_auth import get_user
from sqlalchemy.orm import Session
from config.settings import get_settings
from services.Smart_Share.createEvent import create_event_in_S3_store_meta_to_DB
from services.Smart_Share.imagePreProcessEmbeddings import preprocess_image_before_embedding
from utils.S3Utils import S3Utils



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
                    bucket_name=settings.AWS_BUCKET_SMART_SHARE_NAME)


@router.post('/create-event/{event_name}', status_code=status.HTTP_201_CREATED)
def create_event(event_name:str, request:Request, db_session:Session = Depends(get_db)):
    return create_event_in_S3_store_meta_to_DB(request=request, event_name=event_name.lower(), s3_utils_obj=s3_utils, db_session=db_session)


@router.post('/upload-images/{folder}', status_code=status.HTTP_202_ACCEPTED)
async def upload_images(request: Request, event_name: str, images: list[UploadFile] = File(...), session: Session = Depends(get_db), user: User = Depends(get_user)):

    user_id = request.session.get("user_id")
    event_name = event_name.lower()

    # Checking if that folder exists in the database or not
    folder_data = session.query(FoldersInS3).filter(FoldersInS3.name == event_name, FoldersInS3.module == settings.APP_SMART_SHARE_MODULE).first()
    if not folder_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find folder with {event_name} in culling module')


    # Validation if combined size of images is greater than available size and check image validation
    storage_used = session.query(User.total_culling_storage_used).filter(User.id == user_id).scalar()
    is_valid, output = await validate_images_and_storage(
                                                        files=images, 
                                                        max_uploads=20, 
                                                        max_size_mb=100,
                                                        max_storage_size=settings.MAX_SMART_SHARE_MODULE_STORAGE,
                                                        db_storage_used=storage_used
                                                        )
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=output)
    
    #uplaoding image to s3, updating meta data in database and return presinged url
    response  = await preprocess_image_before_embedding(event_name=event_name,
                                                        images=images,
                                                        s3_utils=s3_utils,
                                                        session=session,
                                                        total_image_size=output,
                                                        user_id=user_id,
                                                        folder_id=folder_data.id
                                                        )
    
    if isinstance(response, dict):  # Ensure response is serializable
        return JSONResponse(content=response)
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )