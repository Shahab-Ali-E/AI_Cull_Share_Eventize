from typing import List
from fastapi import APIRouter, HTTPException,status,Depends,UploadFile,File,Request
from fastapi.responses import JSONResponse
from dependencies.core import DBSessionDep
from config.security import validate_images_and_storage
from model.User import User
from model.FolderInS3 import FoldersInS3
from schemas.ImageTaskData import ImageTaskData
from dependencies.user import get_user
from schemas.imageMetaDataResponse import CullingFolderMetaData
from services.Culling.createFolderInS3 import create_folder_in_S3
from config.settings import get_settings
from services.Culling.deleteFolderFromS3 import delete_s3_folder_and_update_db
from services.Culling.pre_cull_img_processing import pre_cull_image_processing
from utils.S3Utils import S3Utils
from services.Culling.tasks.cullingTask import culling_task
from sqlalchemy.future import select

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
                    bucket_name=settings.AWS_BUCKET_SMART_CULL_NAME,
                    aws_endpoint_url=settings.AWS_ENDPOINT_URL)



@router.get("/get_all_folder", response_model=List[CullingFolderMetaData])
async def get_all_folders(request:Request, db_session:DBSessionDep, user:User = Depends(get_user)):
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access!')

    async with db_session.begin():
        try:
            result =  (await db_session.scalars(select(FoldersInS3).where(FoldersInS3.module==settings.APP_SMART_CULL_MODULE)))
            folders = result.all()
            return folders
        
        except HTTPException as e:
            raise HTTPException(status_code=e.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) 
     

@router.get("/folder/{folder_name}")
async def get_folder_by_name(request:Request,folder: str, user:User = Depends(get_user)):
    pass

@router.post('/create_directory/{dir_name}', status_code=status.HTTP_201_CREATED)
async def create_directory(dir_name:str, request:Request,  db_session: DBSessionDep, user:User = Depends(get_user)):
    """
    🗂️ **Create a Root Directory in S3 for Image Organization** 🗂️

    This endpoint helps you **organize your images** in S3 by creating a root directory with optional subfolders. 🌟 For instance, if you provide `Culling_Images` as the `dir_name`, it will automatically set up several useful subfolders such as:
    - **`closed_eye_images_folder`** 👁️
    - **`blur_images_folder`** 🌫️
    - **`duplicate_images_folder`** 🔄
    - **`fine_collection_folder`** 🎯
    - **`images_before_cull_folder`** 🗑️

    ### Parameters:
    - **`dir_name`** *(str)*: The name of the root directory to be created in S3. Specify the top-level directory name where your images will be organized.
    - **`request`**: Contains session details required for authentication and execution.
    - **`user`**: The user making the request, obtained through dependency injection to ensure authorized access.
    - **`session`**: The database session used to execute queries for creating directories.

    ### Responses:
    - 🎉 **201 Created**: **Success!** The root directory and its subfolders have been created successfully.
    - ⚠️ **500 Internal Server Error**: **Error!** Something went wrong during the folder creation process. This might be due to issues with S3 or database access.
    """

    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access!')   
    
    async with db_session.begin():
        try:
            response =  await create_folder_in_S3(dir_name=dir_name.lower(), s3_utils_obj=s3_utils, db_session=db_session, user_id=user_id)
            await db_session.commit()
            return response
        except HTTPException as e:
            await db_session.rollback()
            raise HTTPException(status_code=e.status_code, detail=str(e))
        except Exception as e:
            await db_session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))




@router.post('/upload-images/{folder}', status_code=status.HTTP_202_ACCEPTED)
async def upload_images(request: Request, folder: str, db_session: DBSessionDep, images: list[UploadFile] = File(...), user: User = Depends(get_user)):
    """
    📸 **Upload Images to S3 and Initiate Background Culling Task** 📸

    This endpoint efficiently **handles image uploads** to S3 and kicks off a background process for image culling. It manages the upload of images to a specified S3 folder and then generates and sends their URLs to a Celery task for further processing. This background task will handle image culling asynchronously, ensuring a smooth user experience.

    ### Parameters:
    - **`folder`** *(str)*: 🗂️ The name of the destination folder in S3 where the images will be stored.
    - **`images`** *(list[UploadFile])*: 🖼️ A collection of images to be uploaded. Ensure the images meet size and format requirements.
    - **`session`**: 🗃️ The database session used for executing queries related to image and folder validation.
    - **`user`**: 👤 The user making the request, obtained through dependency injection to ensure authorized access.
    - **`request`**: 🧾 Contains session details necessary for authentication.

    ### Workflow:
    1. **🔍 Folder Validation**: Verifies if the specified folder exists within the culling module. Ensures proper placement of images.
    2. **⚖️ Image and Storage Validation**: Checks the images for correct size and format. Confirms that storage usage remains within the user’s allowed limits.
    3. **☁️ Upload to S3**: Uploads the validated images to S3 and updates their metadata in the database.
    4. **🛠️ Task Dispatch**: Sends the URLs of the uploaded images to a Celery task for background culling. This process includes actions such as face extraction and embedding preparation.

    ### Responses:
    - 🎉 **202 Accepted**: Your images are successfully accepted for processing. The culling task has been initiated and will run in the background.
    - ❓ **404 Not Found**: The specified folder does not exist. Please check the folder name.
    - 📉 **415 Unsupported Media Type**: The images provided are invalid or exceed the allowed size/storage limits.
    - ⚠️ **500 Internal Server Error**: An unexpected error occurred during the processing. This could be due to issues with S3, the database, or the task dispatching system.
    """
    try:
        
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access !') 
        folder = folder.lower()

        async with db_session.begin(): 
            # Checking if the folder exists in the database
            folder_data = await db_session.execute(
                                                    select(FoldersInS3).where(
                                                        FoldersInS3.name == folder,
                                                        FoldersInS3.module == settings.APP_SMART_CULL_MODULE
                                                    )
                                                )
            folder_data = folder_data.scalar_one_or_none()
            if not folder_data:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find folder with {folder} in culling module')

            # Validation if combined size of images is greater than available size and check image validation
            storage_used = await db_session.execute(
                select(User.total_culling_storage_used).where(User.id == user_id)
            )
            storage_used = storage_used.scalar_one_or_none()
            
            is_valid, output = await validate_images_and_storage(
                                                                    files=images, 
                                                                    max_uploads=20, 
                                                                    max_size_mb=100,
                                                                    max_storage_size=settings.MAX_SMART_CULL_MODULE_STORAGE,
                                                                    db_storage_used=storage_used
                                                                )
            if not is_valid:
                raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=output)
            
            # Uploading image to S3, updating metadata in database, and returning presigned URL
            response = await pre_cull_image_processing(
                                                        folder=folder,
                                                        images=images,
                                                        s3_utils=s3_utils,
                                                        db_session=db_session,
                                                        total_image_size=output,
                                                        user_id=user_id
                                                    )
            
            # if isinstance(response, dict):  # Ensure response is serializable
            #     return response
            #commiting database changes if everythig is successfull
            # storage_used =  (await db_session.scalars(select(User.total_culling_storage_used).where(User.id == user_id))).first().a2b_hex('dasda')
            await db_session.commit()
            return response
    
    except HTTPException as e:
        await db_session.rollback()
        # Handle unexpected errors
        raise HTTPException(
            status_code=e.status_code,
            detail=f"{str(e)}"
        )
    
    except Exception as e:
        await db_session.rollback()
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )



@router.post('/start_culling/', status_code=status.HTTP_102_PROCESSING, response_model=None)
async def start_culling(request: Request, culling_data: ImageTaskData, db_session: DBSessionDep, user: User = Depends(get_user)):
    """
    🔄 **Initiates the Image Culling Process** 🔄

    This endpoint kicks off the **image culling process** by sending image URLs and related data to a background task managed by Celery. The task processes the images located in the specified folder for the current user.

    ### Parameters:
    - **`request`** 🧾: The request object containing session details for authentication.
    - **`culling_data`** 📂: Contains essential information for the culling task:
    - **`folder_name`** 🗂️: The name of the folder where images are located.
    - **`images_url`** 🌐: A list of image URLs to be processed.
    - **`session`** 🗃️: The database session used for querying and updating database records.
    - **`user`** 👤: The user making the request, obtained through dependency injection.

    ### Workflow:
    1. **🔍 Folder Validation**: Checks if the specified folder exists in the culling module for the current user.
    2. **🚀 Task Dispatch**: Sends image URLs and related data to a Celery task that handles image culling asynchronously.
    3. **📬 Response**: Returns a JSON response with the task ID to track the progress of the culling process.

    ### Responses:
    - 🕒 **102 Processing**: The request has been accepted and is being processed. The task is running in the background.
    - ❓ **404 Not Found**: The specified folder does not exist for the user in the culling module.
    - ⚠️ **500 Internal Server Error**: An unexpected error occurred when sending the task to Celery.
    """
    
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access !') 

    async with db_session.begin():
        #get folder data
        folder_data = (await db_session.scalars(select(FoldersInS3).where(FoldersInS3.name==culling_data.folder_name, 
                                                                        FoldersInS3.module == settings.APP_SMART_CULL_MODULE, 
                                                                        FoldersInS3.user_id == user_id))).first()
        
    if not folder_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find folder with {culling_data.folder_name} in culling module')

    #Sending images URL and other info to Celery task
    try:
        task = culling_task.apply_async(args=[user_id, culling_data.images_url, culling_data.folder_name, folder_data.id])
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error sending task to Celery: {str(e)}")

    return JSONResponse({"task_id": task.id})


@router.delete("/delete-folder/{dir_name}")
async def delete_folder(dir_name:str, request:Request, db_session: DBSessionDep, user:User = Depends(get_user)):
    """
    🗑️ **Deletes a Folder from S3 and Removes its Record from the Database** 🗑️

    This endpoint performs a clean-up operation by deleting a specified folder from the S3 bucket and removing its record from the database.

    ### Parameters:
    - **`dir_name`** 📁: The name of the directory to be deleted.
    - **`request`** 🧾: The request object containing session details for authentication.
    - **`session`** 🗃️: The database session used for executing queries.

    ### Workflow:
    1. **🔍 Folder Path Construction**: Builds the path of the folder to be deleted using the user's ID and the directory name.
    2. **🗑️ S3 Deletion**: Deletes the folder and its contents from the S3 bucket.
    3. **🗂️ Database Update**: Removes the corresponding folder's record from the database.

    ### Responses:
    - ✅ **200 OK**: The folder has been successfully deleted from S3 and its record removed from the database.
    - ❓ **404 Not Found**: The specified folder or its database record does not exist.
    - ⚠️ **500 Internal Server Error**: An unexpected error occurred during the deletion process.
    """

    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access !') 

    folder_path = f'{user_id}/{dir_name}/'
    try:
        async with db_session.begin():
            response =  await delete_s3_folder_and_update_db(del_folder_path=folder_path,
                                                        db_session=db_session, 
                                                        s3_obj=s3_utils,
                                                        module=settings.APP_SMART_CULL_MODULE,
                                                        user_id=user_id
                                                        )
            # Commit the database transaction if everything is successful
            await db_session.commit()
            return response
        
    except HTTPException as e:
        await db_session.rollback()
        raise HTTPException(status_code=e.status_code, detail=str(e))

    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

 