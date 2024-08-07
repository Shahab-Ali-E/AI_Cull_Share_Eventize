import asyncio
from io import BytesIO
from uuid import uuid4
from fastapi import APIRouter, HTTPException,status,Depends,UploadFile,File,Request
from fastapi.responses import JSONResponse
from config.Database import get_db
from config.security import images_validation
from model.User import User
from services.Auth.google_auth import get_user
from sqlalchemy.orm import Session
from services.culling.createFolderInS3 import create_folder_in_S3
from config.settings import get_settings
from utils.S3Utils import S3Utils
from PIL import Image
from services.culling.tasks.cullingTask import culling_task
from Celery.utils import get_task_info
from sse_starlette.sse import EventSourceResponse


router = APIRouter(
    prefix='/culling',
    tags=['culling'],
)

# celery = create_celery()


#instance of settings
settings = get_settings()


#instance of S3
S3_utils = S3Utils(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_region=settings.AWS_REGION,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    bucket_name=settings.AWS_BUCKET_NAME)

@router.post('/create_directory/{dir_name}', status_code=status.HTTP_201_CREATED)
async def create_directory_in_cloud(dir_name:str, request:Request, user:User = Depends(get_user)):
    return await create_folder_in_S3(dir_name=dir_name.lower(), request=request)



@router.post('/upload_images/{folder}', status_code=status.HTTP_202_ACCEPTED)
async def upload_images(request: Request, folder: str, images: list[UploadFile] = File(...), session: Session = Depends(get_db), user:User = Depends(get_user)):

    """

    this function will take list of images and process them after it will upload these images to
    AWS S3 bucket and generate all those image url and add them into a list after that pass that
    list to cullingTask which will get those images from bucket via URL and perform culling on them 
    at celery

    """
    user_id = request.session.get("user_id")
    uploaded_images_url = []
    folder=folder.lower()

    is_valid, validation_message = images_validation(images, max_uploads=20, max_size_mb=100)

    if not is_valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=validation_message)


    for image in images:
        filename = f'{uuid4()}_{image.filename}'
        
        #some image validation
        try:
            image_data = await image.read()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading image file: {str(e)}")
        
        try:
            img = Image.open(BytesIO(image_data))
            img.verify()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error opening image file: {str(e)}")

        #uplaoding image to s3 before sending it to celery task
        try:
            S3_utils.upload_image(
                filename=filename,
                root_folder=user_id,
                main_folder=folder,
                upload_image_folder=settings.IMAGES_BEFORE_CULLING_STARTS_Folder,
                image_data=BytesIO(image_data)
            )
            key = f"{user_id}/{folder}/{settings.IMAGES_BEFORE_CULLING_STARTS_Folder}/{filename}"
            presigned_url = S3_utils.generate_presigned_url(key)
            uploaded_images_url.append(presigned_url)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error uploading image to S3: {str(e)}")
    
    #sending images url and other info to celery task
    try:
        task = culling_task.apply_async(args=[user_id, uploaded_images_url, folder])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending task to Celery: {str(e)}")

    return JSONResponse({"task_id": task.id})




@router.get("/task/{task_id}")
async def get_task_status(request:Request,task_id: str, user:User = Depends(get_user)):
    """
    Return the status of the submitted culling task
    """
    async def event_generator(task_id):
        while True:
            if await request.is_disconnected():
                break
            task_info = get_task_info(task_id=task_id)
            yield {
                "event": "message",
                "data": task_info,
            }

            if task_info['state'] in ['FAILURE','SUCCESS']:
                break
            await asyncio.sleep(1)  # Adjust the sleep time as needed

    return EventSourceResponse(event_generator(task_id))


 