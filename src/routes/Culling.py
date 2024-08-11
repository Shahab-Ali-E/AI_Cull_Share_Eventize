import asyncio
from fastapi import APIRouter, HTTPException, Response,status,Depends,UploadFile,File,Request
from fastapi.responses import JSONResponse
from config.Database import get_db
from config.security import validate_images_and_storage
from model.User import User
from model.FolderInS3 import FoldersInS3
from schemas.cullingData import cullingData
from services.Auth.google_auth import get_user
from sqlalchemy.orm import Session
from services.culling.createFolderInS3 import create_folder_in_S3
from config.settings import get_settings
from services.culling.deleteFolderFromS3 import delete_folder_in_s3_and_update_DB
from services.culling.pre_cull_img_processing import pre_cull_image_processing
from utils.S3Utils import S3Utils
from PIL import Image
from services.culling.tasks.cullingTask import culling_task
from Celery.utils import get_task_info
from sse_starlette.sse import EventSourceResponse


router = APIRouter(
    prefix='/culling',
    tags=['culling'],
)


#instance of settings
settings = get_settings()


#instance of S3
s3_utils = S3Utils(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_region=settings.AWS_REGION,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    bucket_name=settings.AWS_BUCKET_SMART_CULL_NAME)


@router.post('/create_directory/{dir_name}', status_code=status.HTTP_201_CREATED)
def create_directory(dir_name:str, request:Request, user:User = Depends(get_user), session: Session = Depends(get_db)):
    """
    Creates a Root Directory in S3 for Image Organization

    This endpoint creates a root directory in the S3 bucket under the specified directory name. If 'Culling_Images' is passed as `dir_name`, additional subfolders such as `closed_eye_images_folder`, `blur_images_folder`, `duplicate_images_folder`, `fine_collection_folder`, and `images_before_cull_folder` will be created within it.

    ### Parameters:
    - **dir_name**: The name of the root directory to be created in S3.
    - **request**: The request object containing session details.
    - **user**: The user making the request, obtained through dependency injection.
    - **session**: The database session for executing queries.

    ### Responses:
    - **201 Created**: The root directory and subfolders have been successfully created.
    - **500 Internal Server Error**: If there is an error during the folder creation process.

    ### Example Usage:
    Send a POST request with the desired directory name to organize images within S3.
    """
        
    return create_folder_in_S3(dir_name=dir_name.lower(), request=request, s3_utils_obj=s3_utils, db_session=session)



@router.post('/upload-images/{folder}', status_code=status.HTTP_202_ACCEPTED)
async def upload_images(request: Request, folder: str, images: list[UploadFile] = File(...), session: Session = Depends(get_db), user: User = Depends(get_user)):
    """
    Uploads Images to S3 and Initiates Background Culling Task

    This endpoint processes a list of images, uploads them to the specified folder in the AWS S3 bucket, and generates their URLs. The URLs are then sent to a Celery task that performs image culling in the background.

    ### Parameters:
    - **folder**: The name of the folder in S3 where the images will be uploaded.
    - **images**: A list of images to be uploaded.
    - **session**: The database session for executing queries.
    - **user**: The user making the request, obtained through dependency injection.
    - **request**: The request object containing session details.

    ### Workflow:
    1. **Folder Validation**: The specified folder is verified to ensure it exists in the culling module.
    2. **Image and Storage Validation**: The images are validated for size and format, and the storage usage is checked to ensure it does not exceed the user's limit.
    3. **Upload to S3**: Valid images are uploaded to S3, and metadata is updated in the database.
    4. **Task Dispatch**: The images' URLs are passed to a Celery task for background culling.

    ### Responses:
    - **202 Accepted**: The images have been accepted for processing, and a culling task has been initiated.
    - **404 Not Found**: If the specified folder is not found.
    - **415 Unsupported Media Type**: If the images are invalid or exceed the storage limit.
    - **500 Internal Server Error**: If an unexpected error occurs during processing.

    ### Example Usage:
    Send a POST request with a list of images to upload them to the specified folder and initiate the culling task.
    """

    user_id = request.session.get("user_id")
    folder = folder.lower()

    # Checking if that folder exists in the database or not
    folder_data = session.query(FoldersInS3).filter(FoldersInS3.name == folder, FoldersInS3.module == settings.APP_SMART_CULL_MODULE).first()
    print(folder_data)
    if not folder_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find folder with {folder} in culling module')


    # Validation if combined size of images is greater than available size and check image validation
    storage_used = session.query(User.total_culling_storage_used).filter(User.id == user_id).scalar()
    is_valid, output = await validate_images_and_storage(files=images, 
                                                                     max_uploads=20, 
                                                                     max_size_mb=100,
                                                                     max_storage_size=settings.MAX_SMART_CULL_MODULE_STORAGE,
                                                                     db_storage_used=storage_used)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=output)
    
    #uplaoding image to s3, updating meta data in database and return presinged url
    response  = await pre_cull_image_processing(folder=folder,
                                          images=images,
                                          s3_utils=s3_utils,
                                          session=session,
                                          total_image_size=output,
                                          user_id=user_id)
    
    if isinstance(response, dict):  # Ensure response is serializable
        return JSONResponse(content=response)
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )



@router.post('/start_culling/', status_code=status.HTTP_102_PROCESSING, response_model=None)
async def start_culling(request: Request, culling_data: cullingData, session: Session = Depends(get_db), user: User = Depends(get_user)):
    """
    Initiates the Image Culling Process

    This endpoint starts the image culling process by sending image URLs and related information to a background task managed by Celery. The culling task processes images in the specified folder for the current user.

    ### Parameters:
    - **request**: The request object containing session details.
    - **culling_data**: The data required for culling, including the folder name and a list of image URLs to process.
    - **session**: The database session used for querying and updating the database.
    - **user**: The user making the request, obtained through dependency injection.

    ### Workflow:
    1. **Folder Validation**: The specified folder is verified to ensure it exists in the culling module for the current user.
    2. **Task Dispatch**: The images and other information are sent to a Celery task that handles the image culling process in the background.
    3. **Response**: Returns a JSON response containing the task ID, which can be used to track the progress of the culling task.

    ### Responses:
    - **102 Processing**: The request has been accepted for processing, but the processing has not been completed.
    - **404 Not Found**: If the specified folder is not found for the user in the culling module.
    - **500 Internal Server Error**: If there is an error in sending the task to Celery.

    ### Example Usage:
    Send a POST request with the folder name and image URLs to start the culling process.
    """
    user_id = request.session.get("user_id")

    #get folder data
    folder_data = session.query(FoldersInS3).filter(FoldersInS3.name==culling_data.folder_name, FoldersInS3.module == settings.APP_SMART_CULL_MODULE, FoldersInS3.user_id == user_id).first()
    if not folder_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find folder with {culling_data.folder_name} in culling module')

    #Sending images URL and other info to Celery task
    try:
        task = culling_task.apply_async(args=[user_id, culling_data.images_url, culling_data.folder_name, folder_data.id])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending task to Celery: {str(e)}")

    return JSONResponse({"task_id": task.id})



@router.get("/task/{task_id}")
async def get_task_status(request:Request,task_id: str, user:User = Depends(get_user)):
    """
    Retrieve the Status of a Background Culling Task

    This endpoint returns the current status of a background culling task, identified by its task ID. The task status is streamed to the client in real-time using Server-Sent Events (SSE).

    ### Parameters:
    - **task_id**: The ID of the task whose status is being queried.
    - **request**: The request object for checking connection status.
    - **user**: The user making the request, obtained through dependency injection.

    ### Responses:
    - **200 OK**: The task status is streamed to the client in real-time.
    - **404 Not Found**: If the task ID does not exist.
    - **500 Internal Server Error**: If an error occurs while retrieving the task status.

    ### Example Usage:
    Send a GET request with the task ID to receive real-time updates on the task's progress.
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


@router.get("/folder/{folder_name}")
async def get_folder_by_name(request:Request,folder: str, user:User = Depends(get_user)):
    pass

@router.delete("/delete-folder/{dir_name}")
def delete_folder(dir_name:str, request:Request, Session = Depends(get_db)):
    """
    Deletes a Folder from S3 and Removes its Record from the Database

    This endpoint deletes a folder from the S3 bucket and removes its corresponding record from the database.

    ### Parameters:
    - **dir_name**: The name of the directory to be deleted.
    - **request**: The request object containing session details.
    - **session**: The database session for executing queries.

    ### Workflow:
    1. **Folder Path Construction**: Constructs the path of the folder to be deleted based on the user's ID and directory name.
    2. **S3 Deletion**: Deletes the folder from S3.
    3. **Database Update**: Removes the folder's record from the database.

    ### Responses:
    - **200 OK**: The folder has been successfully deleted from S3 and removed from the database.
    - **404 Not Found**: If the folder or its record does not exist.
    - **500 Internal Server Error**: If an error occurs during deletion.

    ### Example Usage:
    Send a DELETE request with the directory name to remove the folder and its metadata.
    """

    user_id = request.session.get('user_id')

    folder_path = f'{user_id}/{dir_name}/'

    return delete_folder_in_s3_and_update_DB(del_folder_path=folder_path,
                                             db_session=Session, 
                                             s3_obj=s3_utils,
                                             module=settings.APP_SMART_CULL_MODULE,
                                             user_id=user_id)

 