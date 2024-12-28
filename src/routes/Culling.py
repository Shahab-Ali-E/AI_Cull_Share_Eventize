from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import (APIRouter, Depends, File, HTTPException, Query, Request,
                     UploadFile, status)
from fastapi.responses import JSONResponse
from sqlalchemy import asc, desc
from sqlalchemy.future import select

from config.security import validate_images_and_storage
from config.settings import get_settings
from dependencies.core import DBSessionDep
from dependencies.user import get_user
from model.CullingFolders import CullingFolder
from model.CullingImagesMetaData import ImagesMetaData, TemporaryImageURL
from model.User import User
from schemas.FolderMetaDataResponse import CullingFolderMetaData
from schemas.ImageMetaDataResponse import CulledImagesMetadataResponse
from schemas.ImageTaskData import ImageTaskData
from services.Culling.createFolderInS3 import create_folder_in_S3
from services.Culling.deleteFolderFromS3 import delete_s3_folder_and_update_db
from services.Culling.pre_cull_img_processing import pre_cull_image_processing
from services.Culling.tasks.cullingTask import culling_task
from utils.S3Utils import S3Utils
from utils.UpdateUserStorage import update_user_storage_in_db
from utils.UpsertMetaDataToDB import upsert_folder_metadata_DB

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
async def get_all_folders(
    db_session:DBSessionDep, 
    user:User = Depends(get_user),
    limit: int = Query(10, ge=1, le=100, description="Limit number of folders to retrieve"),
    offset: int = Query(0, ge=0, description="Number of folders to skip"),
    search: Optional[str] = Query(None, description="Search by folder name"),
    sort_by: Optional[str] = Query("created_date", description="Sort by size, name, or created_date"),
    sort_order: Optional[str] = Query("asc", description="Sort order: asc or desc")

    ):
    """
        📂 **Retrieve All Folders in S3** 📂

        This endpoint allows you to **fetch a list of folders** stored in S3 associated with the authenticated user. You can customize your results with pagination, sorting, and searching capabilities. For example, you can retrieve folders by their name or sort them by size, name, or creation date. 

        ### Parameters:
        - **`limit`** *(int, optional)*: The maximum number of folders to retrieve. Defaults to `10`. Specify a value between `1` and `100`.
        - **`offset`** *(int, optional)*: The number of folders to skip in the result set. Defaults to `0`.
        - **`search`** *(str, optional)*: A string to filter folders by name. Returns only those folders whose names contain the specified substring.
        - **`sort_by`** *(str, optional)*: The field by which to sort the results. Acceptable values are `size`, `name`, and `created_date`. Defaults to `created_date`.
        - **`sort_order`** *(str, optional)*: The order in which to sort the results. Specify `asc` for ascending or `desc` for descending order. Defaults to `asc`.
        - **`user`**: The user making the request, obtained through dependency injection to ensure authorized access.
        - **`db_session`**: The database session used to execute queries for fetching folders.

        ### Responses:
        - 📃 **200 OK**: **Success!** A list of folders is returned based on the provided parameters.
        - ⚠️ **401 Unauthorized or 403 Forbidden**: **Error!** The user is not authorized to access this resource.
        - ⚠️ **500 Internal Server Error**: **Error!** An unexpected error occurred while fetching folders.
    """

    user_id = user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access!')

    # Base query to fetch all folders
    query = select(CullingFolder).where(
        CullingFolder.user_id == user_id
    )

    # Apply search filter if provided
    if search:
        query = query.where(CullingFolder.name.ilike(f"%{search}%"))

    # Sorting logic
    if sort_by == "size":
        order_by_column = CullingFolder.total_size
    elif sort_by == "name":
        order_by_column = CullingFolder.name
    else:
        order_by_column = CullingFolder.created_at

    # Sorting direction
    query = query.order_by(desc(order_by_column) if sort_order == "desc" else asc(order_by_column))

    # Apply pagination
    query = query.limit(limit).offset(offset)

    async with db_session.begin():
        try:
            result = await db_session.scalars(query)
            folders = result.all()

            return folders
        
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
     

@router.get("/get_folder_id/{folder_id}")
async def get_folder_by_id(
    request: Request,
    db_session: DBSessionDep,
    folder_id: UUID,
    user: User = Depends(get_user)
):
    """
        📁 **Retrieve a Specific Folder by ID** 📁

        This endpoint allows you to **fetch details of a specific folder** stored in S3 using its unique identifier. You can only access folders associated with your user account, ensuring that sensitive data remains secure.

        ### Parameters:
        - **`folder_id`** *(UUID)*: The unique identifier of the folder you wish to retrieve.
        - **`request`**: Contains session details required for authentication and execution.
        - **`user`**: The user making the request, obtained through dependency injection to ensure authorized access.
        - **`session`**: The database session used to execute queries for fetching the folder.

        ### Responses:
        - 📃 **200 OK**: **Success!** The folder details are returned.
        - ⚠️ **401 Unauthorized**: **Error!** The user is not authorized to access this resource.
        - ⚠️ **404 Not Found**: **Error!** The specified folder does not exist.
        - ⚠️ **500 Internal Server Error**: **Error!** An unexpected error occurred while fetching the folder.
    """

    user_id = user.get('id') #"user_2pqOmYikrXY1pWefuBuqzRGm3vA"
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access!')

    async with db_session.begin():
        try:
            # Query to get the folder by ID and user ID
            folder = await db_session.scalar(
                select(CullingFolder).where(
                    CullingFolder.id == folder_id,
                    CullingFolder.user_id == user_id,
                )
            )

            # Check if folder exists
            if folder is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Folder not found!')
            
            # Query to get the temporary images urls
            temp_urls = (await db_session.scalars(select(TemporaryImageURL).where(TemporaryImageURL.culling_folder_id == folder_id))).all()
            updated_urls = []
            
            for data in temp_urls:
                validity_time =data.validity
                current_time = datetime.now(timezone.utc)
                
                if current_time < validity_time:         
                        updated_urls.append({"url":data.url, "validity":validity_time})# Keep only valid URLs
                else:
                    await db_session.delete(data)  # Remove invalid URLs

            await db_session.commit()
            
            return {
                "id":folder.id,
                "name":folder.name,
                "created_at":folder.created_at,
                "total_size":folder.total_size,
                "culling_done":folder.culling_done,
                "culling_in_progress":folder.culling_in_progress,
                "temporary_images_urls":updated_urls,
            }

        except HTTPException as e:
            raise HTTPException(status_code=e.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
        

@router.get('/culled_images_metadata/{folder_id}/{detection_status}', response_model=List[CulledImagesMetadataResponse])
async def get_culled_images_metadata(
    folder_id: UUID,
    request: Request,
    db_session: DBSessionDep,
    user: User = Depends(get_user),
    detection_status: Optional[str] = None
):
    """
    **Retrieve Culled Images Metadata**

    This endpoint retrieves **Culled Images Metadata** for images within a specific folder, optionally filtered by their `detection_status`.
    You can use this endpoint to access images temporarily for culling purposes. Only images that are valid and not expired will be returned, ensuring efficient access without issues.

    ### Parameters:
    - **`folder_id`** *(UUID)*: The unique identifier of the folder from which to retrieve metadata.
    - **`detection_status`** *(Optional[str])*: The status of the image detection to filter by. Options are:
      - `Blur`
      - `Duplicate`
      - `Closed Eye`
      - `Fine`
      If omitted, all images within the folder are returned.
    - **`request`**: Contains session details required for authentication and execution.
    - **`user`**: The user making the request, obtained through dependency injection to ensure authorized access.
    - **`session`**: The database session used to execute queries for fetching presigned URLs.

    ### Responses:
    - 📃 **200 OK**: **Success!** A list of valid presigned URLs for the images is returned.
    - ⚠️ **401 Unauthorized**: **Error!** The user is not authorized to access this resource.
    - ⚠️ **404 Not Found**: **Error!** The specified folder does not exist.
    - ⚠️ **500 Internal Server Error**: **Error!** An unexpected error occurred while fetching presigned URLs.
    """
    # Check for user authentication
    user_id = user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access!')

    # Find the folder if it exists
    async with db_session.begin():
        try:
            # Query to get the folder by ID and user ID to check whether the folder exists
            folder = await db_session.scalar(
                select(CullingFolder).where(
                    CullingFolder.id == folder_id,
                    CullingFolder.user_id == user_id,
                )
            )

            # Check if folder exists
            if folder is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Folder not found!')

            # Construct base query for images metadata
            query = select(ImagesMetaData).where(
                ImagesMetaData.culling_folder_id == folder.id,
                ImagesMetaData.detection_status == detection_status
            )

            # Execute query to get culled images metadata
            culled_images_metadata = (await db_session.scalars(query)).all()

            print('$$$$$$$$$$$$$$$$$$$$$$$$$$$$ Culled Images Metadata $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$')
            print(culled_images_metadata)

            return culled_images_metadata

        except HTTPException as e:
            raise HTTPException(status_code=e.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

   
@router.get('/download_images/{folder_id}')
async def download_folder(folder_id:UUID, request:Request, db_session: DBSessionDep, user:User = Depends(get_user)):
    user_id = user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access!')   
    
    async with db_session.begin():
        try:
            folder_data = (await db_session.execute(select(CullingFolder).where(
                                                                                CullingFolder.id == folder_id,
                                                                                CullingFolder.user_id == user_id
                                                                                )))
            folder_data = folder_data.scalar_one_or_none()
            if not folder_data:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find folder with {folder_id} in culling module')
            
            # path where all culling folder data 
            folder_path = f"{user_id}/{folder_data.name}"
            s3 = await s3_utils.download_s3_folder(prefix=folder_path)

            return s3

        except HTTPException as e:
            await db_session.rollback()
            raise HTTPException(status_code=e.status_code, detail=str(e))
        except Exception as e:
            await db_session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


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

    user_id = user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access!')  
    
    storage_used = user.get('total_culling_storage_used')
    
    # validate user storage
    if storage_used == settings.MAX_SMART_CULL_MODULE_STORAGE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='storage full!')
    
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


@router.post('/upload_images/{folder_id}', status_code=status.HTTP_202_ACCEPTED)
async def upload_images(request: Request, folder_id: str, db_session: DBSessionDep,user: User = Depends(get_user), images: list[UploadFile] = File(...)):
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
        # user_id = user.get('id')
        user_id='asdasda'
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized access!")

        # Begin a single transaction for the entire process
        async with db_session.begin():
            # Validate folder
            folder_data = await db_session.execute(
                select(CullingFolder).where(
                    CullingFolder.id == folder_id,
                    CullingFolder.user_id == user_id
                )
            )
            folder_data = folder_data.scalar_one_or_none()
            if not folder_data:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Folder {folder_id} not found")

            # Validate images and storage
            storage_used = await db_session.execute(
                select(User.total_culling_storage_used).where(User.id == user_id)
            )
            storage_used = storage_used.scalar_one_or_none()

            is_valid, output_validated_storage = await validate_images_and_storage(
                files=images, max_uploads=1000, max_size_mb=100, db_storage_used=storage_used
            )

            if not is_valid:
                raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=output_validated_storage)

            # Process batches
            batch_size = 50
            all_presigned_urls = []
            for i in range(0, len(images), batch_size):
                batch = images[i:i + batch_size]
                try:
                    # Process the batch and append presigned URLs
                    presigned_urls = await pre_cull_image_processing(
                        folder=folder_data.name,
                        images=batch,
                        s3_utils=s3_utils,
                        user_id=user_id,
                        db_session=db_session,
                        culling_folder_id=folder_id
                    )
                    all_presigned_urls.extend(presigned_urls)
                except Exception as e:
                    print(f"Error processing batch {i}: {str(e)}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Error processing batch {i}: {str(e)}"
                    )

            # Update folder metadata and user storage in the database
            updated_folder_storage = folder_data.total_size + output_validated_storage
            match_criteria = {"id": folder_id, "name": folder_data.name, "user_id": user_id}

            # Update folder metadata
            await upsert_folder_metadata_DB(
                db_session=db_session,
                match_criteria=match_criteria,
                update_fields={"total_size": updated_folder_storage},
                model=CullingFolder,
                update=True
            )

            # Update user storage
            is_valid, response = await update_user_storage_in_db(
                db_session=db_session,
                total_image_size=output_validated_storage,
                module=settings.APP_SMART_CULL_MODULE,
                user_id=user_id,
                increment=True
            )

            if not is_valid:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{response}")

        return {"message": "Images uploaded successfully", "data": all_presigned_urls}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

# user: User = Depends(get_user)
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
    
    user_id = "user_2pqOmYikrXY1pWefuBuqzRGm3vA"#user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access !') 

    async with db_session.begin():
        #get folder data
        folder_data = (await db_session.scalars(select(CullingFolder).where(CullingFolder.id==culling_data.folder_id, 
                                                                        CullingFolder.user_id == user_id))).first()
        
        if not folder_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Folder {culling_data.folder_id} not found")
        
        folder_data.culling_in_progress = True
        db_session.add(folder_data)
        await db_session.commit()
        
    if not folder_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find folder with {culling_data.folder_id} in culling module')

    #Sending images URL and other info to Celery task
    try:
        task = culling_task.apply_async(args=[user_id, culling_data.images_url, folder_data.name, folder_data.id])
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

    user_id = user.get('id')
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

 