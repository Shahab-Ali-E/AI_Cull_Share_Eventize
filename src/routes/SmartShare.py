from fastapi import APIRouter, HTTPException,status,Depends,UploadFile,File,Request
from fastapi.responses import JSONResponse
from config.Database import get_db
from services.Auth.google_auth import get_user
from sqlalchemy.orm import Session
from config.settings import get_settings
from services.Smart_Share.createEvent import create_event_in_S3_store_meta_to_DB
from utils.S3Utils import S3Utils



router = APIRouter(
    prefix='/smart-share',
    tags=['smart image share'],
)

#instance of settings
settings = get_settings()

#instance of S3
S3_utils = S3Utils(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_region=settings.AWS_REGION,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    bucket_name=settings.AWS_BUCKET_SMART_SHARE_NAME)


@router.post('/create-event/{event_name}', status_code=status.HTTP_201_CREATED)
def create_event(event_name:str, request:Request, db_session:Session = Depends(get_db)):
    return create_event_in_S3_store_meta_to_DB(request=request, event_name=event_name.lower(), s3_utils_obj=S3_utils, db_session=db_session)


