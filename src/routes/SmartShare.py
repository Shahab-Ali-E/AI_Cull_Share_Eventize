from fastapi import APIRouter, HTTPException,status,Depends,UploadFile,File,Request
from fastapi.responses import JSONResponse
from config.security import validate_images_and_storage
from model.FolderInS3 import FoldersInS3
from model.User import User
from schemas.ImageTaskData import ImageTaskData
from schemas.ImageMetaDataResponse import ImageMetaDataResponse
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
    """
    🎉 **Create a New Event** 🎉

    This endpoint allows an **authenticated user** to create a brand-new event. 🚀 The event name is specified directly in the URL path, and you must be logged in with a valid session for this to work. 🌐 Once created, the event will be securely stored in both the **database** and **S3**. 

    🔒 **Authentication Required**: If you're not logged in, you won't be able to create an event—make sure you're authenticated!

    ### Path Parameters:
    - **`event_name`** *(str)*: The unique name of the event you wish to create.

    ### Responses:
    - 🟢 **201 Created**: **Success!** The event was successfully created and is now stored in the system.
    - 🔴 **401 Unauthorized**: **Oops!** You must be logged in to create an event.
    - 🟠 **500 Internal Server Error**: **Uh-oh!** Something went wrong on our end. Please try again later.
    """

    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access')
    try:
        async with db_session.begin():
            response = await create_event_in_S3_and_DB(event_name=event_name.lower().strip(), user_id=user_id, s3_utils_obj=s3_utils, db_session=db_session)
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
    """
    📸 **Upload Images to a Specified Folder** 📸

    This endpoint allows an **authenticated user** to upload images into a designated folder within the **Smart Share** module. 📁 Make sure the folder already exists in the database before uploading your images. The uploaded images are validated for size and storage limits to ensure smooth processing. ✅ Once validated, they are uploaded to **S3**, and metadata is updated in the database. You'll receive a **presigned URL** for each image, which includes the expiration time.

    🔒 **Authentication Required**: You must be logged in to upload images.

    ### Path Parameters:
    - **`folder`** *(str)*: The name of the folder where you want to upload your images.

    ### Request Body:
    - **`images`** *(list[UploadFile], required)*: A list of images to upload. You can upload up to 20 images with a total size not exceeding 100 MB.

    ### Responses:
    - 🟢 **202 Accepted**: **Success!** Images were uploaded, metadata updated, and presigned URLs with expiration times were returned.
    - 🔴 **401 Unauthorized**: **Oops!** You need to be logged in to upload images.
    - 🔍 **404 Not Found**: **Not Found!** The specified folder could not be found in the Smart Share module.
    - 🚫 **415 Unsupported Media Type**: **Invalid Images!** The images are either invalid or exceed the allowed size/storage limits.
    - 🟠 **500 Internal Server Error**: **Something went wrong!** An unexpected error occurred during the upload process.
    """

    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access')
    event_name = event_name.lower().strip()

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
            storage_used = (await db_session.scalar(select(User.total_image_share_storage_used).where(User.id == user_id)))#user storage
            is_valid, output = await validate_images_and_storage(
                                                                files=images, 
                                                                max_uploads=100, 
                                                                max_size_mb=10,
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
async def share_images(event_data:ImageTaskData, request:Request, db_session:DBSessionDep, user:User = Depends(get_user)):
    """
    🔗 **Share Images from a event 🎉** 🔗

    This endpoint enables an **authenticated user** to kick off the process of sharing images from a folder within the **Smart Share** module. 🌟 To get started, provide the folder name and a list of image URLs. 

    **What Happens Under the Hood**:
    1. **Folder Validation**: The provided folder name is checked against the database to ensure it exists under the user's account. 📂
    2. **Image Sharing**: If the folder is valid and at least one image URL is provided, these URLs are sent to a **Celery task** for asynchronous processing. 🚀 This background task will handle actions like:
    - Extracting faces from each image 👤
    - Preparing image embeddings 🔍
    - Uploading to a vector database with metadata 📊

    This approach ensures that the request returns immediately while the sharing process continues seamlessly in the background.

    ### Request Body:
    - **`image_data`** *(imageData, required)*: An object containing:
    - **`folder_name`** *(str)*: The name of the folder where images are located. Must exist in the Smart Share module.
    - **`images_url`** *(list[str])*: A list of URLs for the images to be shared. At least one URL is required.

    ### Responses:
    - 🔄 **102 Processing**: **Accepted!** Your request is being processed. The response includes a Celery task ID for tracking the progress of the image-sharing operation.
    - 🔍 **404 Not Found**: **Not Found!** The specified folder does not exist or no image URLs were provided.
    - 🟠 **500 Internal Server Error**: **Oops!** An unexpected error occurred. This might be due to issues with the database, Celery task, or other internal errors.
    """


    user_id = request.session.get("user_id")
    event_name = event_data.folder_name.lower().strip()
    urls = event_data.images_url
    try:
        async with db_session.begin():
        # Checking if that folder exists in the database or not
            folder_data = (await db_session.scalars(select(FoldersInS3).where(FoldersInS3.name == event_name,
                                                                    FoldersInS3.module == settings.APP_SMART_SHARE_MODULE,
                                                                    FoldersInS3.user_id == user_id
                                                                    ))).first()
        if not folder_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find event with {event_name} in smart share')
        
        if not urls:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'image url not provided !')
        
        #Sending images URL and other info to Celery task     
        task = image_share_task.apply_async(args=[user_id, urls, event_name ])
        
        return JSONResponse({"task_id": task.id})
    
    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



@router.post('/get_images',status_code=status.HTTP_200_OK, response_model=List[ImageMetaDataResponse])
async def get_images(event_name:str, request:Request, db_session:DBSessionDep, image: UploadFile = File(...), user:User = Depends(get_user)):
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access')
    
    async with db_session.begin():
        folder_data = (await db_session.scalars(select(FoldersInS3).where(FoldersInS3.name == event_name,
                                                                    FoldersInS3.module == settings.APP_SMART_SHARE_MODULE,
                                                                    FoldersInS3.user_id == user_id))).first()
    
    if not folder_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find event with {event_name} in smart share')
    
    try:
        response = await get_images_by_face_recog(db_session=db_session,
                                                    event_name=event_name,
                                                    image=image,
                                                    qdrant_util=qdrant_util,
                                                    user_id=user_id,
                                                    event_id=folder_data.id
                                                )
        return response

    except HTTPException as e:
        await db_session.rollback()
        raise HTTPException(status_code=e.status_code, detail=str(e))

    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete('/delete_event/{event_name}', status_code=status.HTTP_200_OK)
async def delete_event(event_name:str, request:Request, db_session:DBSessionDep, user:User = Depends(get_user)):
    """
    🗑️ **Delete an Event and Its Associated Data** 🗑️

    This endpoint allows an **authenticated user** to completely remove an event and all related data. 🌟 The event is identified by its name, provided as a path parameter. This includes:
    - **Database records** 📂
    - **Files stored in S3** ☁️
    - **Collections in Qdrant** 📊

    Upon receiving the request:
    1. **Authentication Check**: Ensure the user is logged in with a valid session. 🚪 If not, the request is rejected with a **401 Unauthorized** status.
    2. **Deletion Process**: If authenticated, the event's data is removed from S3 storage, Qdrant, and the database. All deletions are performed within a database transaction to ensure atomicity. 🔄 If any deletion fails, the transaction is rolled back to maintain data integrity.

    ### Request Parameters:
    - **`event_name`** *(str, required)*: The name of the event you want to delete.

    ### Responses:
    - 🟢 **200 OK**: **Success!** The event and all associated data were successfully deleted.
    - 🔴 **401 Unauthorized**: **Access Denied!** You need to be authenticated to perform this operation.
    - 🟠 **500 Internal Server Error**: **Oops!** An unexpected error occurred. This could be due to issues with the database, S3, or Qdrant.
    """
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
