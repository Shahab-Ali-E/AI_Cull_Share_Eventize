from datetime import datetime, timezone
import os
from urllib.parse import unquote
from typing import List, Optional
from uuid import UUID

from fastapi import (APIRouter, Depends, File, HTTPException, Query, Request,
                     UploadFile, status, Form)
from fastapi.responses import JSONResponse
from sqlalchemy import asc, desc, func
from sqlalchemy.future import select

from src.config.settings import get_settings
from src.dependencies.core import DBSessionDep
from src.dependencies.user import get_user
from src.model.SmartShareFolders import PublishStatus, SmartShareFolder
from src.model.SmartShareImagesMetaData import SmartShareImagesMetaData
from src.model.User import User
from src.schemas.FolderMetaDataResponse import  EventsResponse
from src.schemas.ImageMetaDataResponse import SmartShareEventImagesMeta, SmartShareImageResponse
from src.schemas.ImageTaskData import ImageTaskData
from src.services.SmartShare.createEvent import create_event_in_S3_and_DB
from src.services.SmartShare.deleteEvent import delete_event_s3_db
from src.services.SmartShare.saveEventImageMeta import save_event_images_metadata
from src.services.SmartShare.secondary_user_service import associate_user_with_folder
from src.services.SmartShare.similaritySearch import get_similar_images
from src.services.SmartShare.tasks.imageShareTask import download_and_process_images
from src.services.SmartShare.updateEvent import update_event_details
from src.services.SmartShare.uploadSmartShareImages import upload_smart_share_event_images
from src.utils.QdrantUtils import QdrantUtils
from src.utils.S3Utils import S3Utils

router = APIRouter(
    prefix='/smart_share',
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


@router.get("/get_all_events", response_model=EventsResponse)
async def get_all_events(
    db_session:DBSessionDep, 
    user:User = Depends(get_user),
    limit: int = Query(10, ge=1, le=100, description="Limit number of events to retrieve"),
    page: int = Query(1, ge=1, description="Page number (starting from 1)"),
    search: Optional[str] = Query(None, description="Search by event name"),
    sort_by: Optional[str] = Query("created_date", description="Sort by size, name, or created_date"),
    sort_order: Optional[str] = Query("asc", description="Sort order: asc or desc")

    ):
    """
    📅 **Retrieve All Events** 📅

    Fetch a list of events stored in the system for the authenticated user. The endpoint supports advanced capabilities like pagination, sorting, and filtering.

    ### Parameters:
    - **`limit`** *(int, optional)*: Maximum number of events to retrieve (default: `10`). Must be between `1` and `100`.
    - **`page`** *(int, optional)*: Number of events to skip from the beginning of the result set (default: `1`).
    - **`search`** *(str, optional)*: Filter events by name. Returns events containing the specified substring in their name.
    - **`sort_by`** *(str, optional)*: Sort events by a specific field. Supported values:
      - `size`: Sort by event size.
      - `name`: Sort by event name.
      - `created_date` (default): Sort by event creation date.
    - **`sort_order`** *(str, optional)*: Sort order. Supported values:
      - `asc`: Ascending (default).
      - `desc`: Descending.

    ### Authentication:
    - Requires the user to be authenticated. The `user` parameter ensures authorized access.

    ### Responses:
    - 📃 **200 OK**: Returns a list of events based on the provided parameters.
      ```json
      [
          {
              "id": 1,
              "name": "Event 1",
              "size": 12345,
              "created_date": "2024-12-01T12:00:00Z"
          },
          ...
      ]
      ```
    - ⚠️ **401 Unauthorized**: The user is not authorized to access this resource.
      ```json
      {
          "detail": "Unauthorized access!"
      }
      ```
    - ⚠️ **500 Internal Server Error**: An unexpected error occurred.
      ```json
      {
          "detail": "An error message describing the issue."
      }
      ```

    ### Example Usage:
    - **Retrieve the first 10 events sorted by name in descending order:**
      ```
      GET /get_all_events?limit=10&page=0&sort_by=name&sort_order=desc
      ```

    - **Search for events with "conference" in the name:**
      ```
      GET /get_all_events?search=conference
      ```

    - **Paginate through results (retrieve the next 10 events):**
      ```
      GET /get_all_events?limit=10&page=10
      ```
    """

    user_id = user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access!')

    # Base query
    query = select(SmartShareFolder).where(
        SmartShareFolder.user_id == user_id
    )

    # Apply search filter if provided
    if search:
        query = query.where(SmartShareFolder.name.ilike(f"%{search}%"))

    # Sorting logic
    if sort_by == "size":
        order_by_column = SmartShareFolder.total_size
    elif sort_by == "name":
        order_by_column = SmartShareFolder.name
    else:
        order_by_column = SmartShareFolder.created_at

    # Sorting direction
    query = query.order_by(desc(order_by_column) if sort_order == "desc" else asc(order_by_column))

    # Apply pagination
    offset_value = limit * (page-1)
    paginated_query = query.limit(limit).offset(offset_value)
    
    # Count query
    count_query = select(func.count()).select_from(query.subquery())

    async with db_session.begin():
        try:
            # Execute paginated query
            paginated_result = await db_session.scalars(paginated_query)
            events = paginated_result.all()

            # Execute count query
            total_count_result = await db_session.scalar(count_query)
            total_count = total_count_result or 0

            return {
                "total_count": total_count,
                "events": events,
            }

        
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
        


@router.get("/get_event_by_id/{event_id}")
async def get_event_by_id(
    request: Request,
    db_session: DBSessionDep,
    event_id: UUID,
    user: User = Depends(get_user)
):
    """
    📁 **Retrieve a Specific Event by ID** 📁

    This endpoint allows you to **fetch details of a specific event** using its unique identifier (`event_id`). It returns event data associated with the authenticated user, ensuring secure access to event details and their associated images.

    ### Parameters:
    - **`event_id`** *(UUID)*: The unique identifier of the event you wish to retrieve.
    - **`request`**: Contains session details required for authentication and execution.
    - **`user`**: The user making the request, obtained through dependency injection to ensure authorized access.
    - **`db_session`**: The database session used to execute queries for fetching event and image data.

    ### Responses:
    - 📃 **200 OK**: **Success!** Event details and associated images (if valid) are returned.
      ```json
      {
          "id": "uuid",
          "name": "Event Name",
          "created_at": "2024-12-08T12:00:00Z",
          "total_size": 102400,
          "images_data": [
              {
                  "url": "image_url_1",
                  "validity": "2024-12-09T12:00:00Z"
              },
              ...
          ]
      }
      ```
    - ⚠️ **401 Unauthorized**: The user is not authorized to access this event.
      ```json
      {
          "detail": "Unauthorized access!"
      }
      ```
    - ⚠️ **404 Not Found**: The event with the specified ID does not exist.
      ```json
      {
          "detail": "Event with id {event_id} not found!"
      }
      ```
    - ⚠️ **500 Internal Server Error**: An unexpected error occurred while fetching the event.
      ```json
      {
          "detail": "An error message describing the issue."
      }
      ```

    ### Example Usage:
    - **Get Event by ID:**
      ```
      GET /get_event_id/{event_id}
      ```

    ### Notes:
    - The user can only access events associated with their own account, ensuring data security.
    - If event images have expired (based on `image_download_validity`), they will not be included in the response.
    """

    user_id = user.get('id') #"user_2pqOmYikrXY1pWefuBuqzRGm3vA"
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access!')

    async with db_session.begin():
        try:
            # Query to get the folder by ID and user ID
            event = await db_session.scalar(
                select(SmartShareFolder).where(
                    SmartShareFolder.id == event_id,
                    SmartShareFolder.user_id == user_id,
                )
            )

            # Check if event exists
            if event is None:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content=f'Event with id {event_id} not found!'
                )
            
            # Query to get the images of the specific event
            images_data = (await db_session.scalars(select(SmartShareImagesMetaData).where(SmartShareImagesMetaData.smart_share_folder_id == event_id))).all()
            images_urls = []
            for data in images_data:
                validity_time =data.image_download_validity
                current_time = datetime.now(timezone.utc)
                
                if current_time < validity_time:         
                    images_urls.append({"id":data.id, "name":data.name , "file_type": data.file_type, "image_download_path":data.image_download_path, "image_download_validity":validity_time})
               
            return {
                "id":event.id,
                "name":event.name,
                "cover_image":event.cover_image,
                "description":event.description,
                "created_at":event.created_at,
                "total_size":event.total_size,
                "images_data":images_urls,
                "status":event.status
            }

        except HTTPException as e:
            raise HTTPException(status_code=e.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/public_event_data/{event_id}")
async def get_public_event(
    db_session: DBSessionDep,
    event_id: UUID,
    user: User = Depends(get_user)
):
    """
    Retrieve public event details by event ID.

    This endpoint returns details of a public event **only if the event is published**.
    If the event is not found or is not published, an appropriate error response is returned.

    **Args:**
        db_session (DBSessionDep): Database session dependency for querying the database.
        event_id (UUID): The unique identifier of the event to retrieve.

    **Returns:**
        dict: A dictionary containing event details (ID, name, cover image, and status).

    **Raises:**
        HTTPException 404: If the event does not exist or is not published.
        HTTPException 500: For any internal server errors.
    """
    try:
        # Fetch the event from the database
        event = await db_session.scalar(
            select(SmartShareFolder).where(SmartShareFolder.id == event_id)
        )
        
        # If the event does not exist, return a 404 error
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with ID {event_id} not found!"
            )
        
        # If the event exists but is not published, return a 403 error
        if event.status.value != PublishStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail=f"Event is not published yet!"
            )
        
        # Return event details
        return {
            "id": event.id,
            "name": event.name,
            "cover_image": event.cover_image,
            "status": event.status
        }
    
    except HTTPException as e:
        raise e  # Re-raise known HTTP errors
    
    except Exception as e:
        # Log the error for debugging (optional)
        print(f"Internal Server Error: {e}")
        
        # Return a generic 500 error message
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later."
        )


@router.post('/create_event/{event_name}', status_code=status.HTTP_201_CREATED)
async def create_event(event_name:str, request:Request, db_session:DBSessionDep, user: User = Depends(get_user), event_cover_image: UploadFile = File(None)):
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

    user_id = user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access')
    
    # Validate image file
    if event_cover_image:
        if not event_cover_image.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an image"
            )
        if event_cover_image.size < 0 or event_cover_image.size > 2 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image size must be between 0 and 2 MB",
            )
    try:
        async with db_session.begin():
            db_response = await create_event_in_S3_and_DB(event_name=event_name.lower().strip(), event_cover_image=event_cover_image, user_id=user_id, s3_utils_obj=s3_utils, db_session=db_session)
            
            if db_response.get("status") != "COMPLETED":
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail= f"db_response {db_response}") 

            
            await db_session.commit()
            # Define the path where you want to create the folder
            path_where_to_create_folder =  os.path.join("src","services","SmartShare","Smart_Share_Events_Data" )
            # Create the complete folder path
            folder = os.path.join(path_where_to_create_folder,str(db_response.get('data').id))
            os.mkdir(folder)
            
            return {
                'database_response': db_response
                }
    
    except HTTPException as e:
        await db_session.rollback()
        raise HTTPException(status_code=e.status_code, detail=str(e))
    
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post('/upload_images/{event_id}', status_code=status.HTTP_202_ACCEPTED)
async def upload_images(event_id: str, db_session:DBSessionDep, images: list[UploadFile] = File(...), user: User = Depends(get_user)):
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
    user_id = user.get('id')
    
    try:
        # Begin a single transaction for the entire process
        async with db_session.begin():
           return await upload_smart_share_event_images(db_session=db_session, event_id=event_id, images=images, user_id=user_id)

    except HTTPException as e:
        raise e

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            content=str(e)
        )


@router.post('/save_event_images_meta/{event_id}')
async def save_event_images_meta(event_id: str, db_session:DBSessionDep, images_metadata: list[SmartShareEventImagesMeta], combined_size:int, user: User = Depends(get_user)):
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
    user_id = user.get('id')
    
    try:
        # Begin a single transaction for the entire process
        async with db_session.begin():
           return await save_event_images_metadata(db_session=db_session, event_id=event_id, images_metadata=images_metadata, user_id=user_id, combined_size=combined_size)

    except HTTPException as e:
        raise e

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            content=str(e)
        )


@router.post('/share_images', status_code=status.HTTP_102_PROCESSING)
async def share_images(event_data: ImageTaskData, db_session: DBSessionDep, user: dict = Depends(get_user)):
    """
    🔗 **Share Images from an Event 🎉** 🔗

    This endpoint enables an **authenticated user** to kick off the process of sharing images from a folder within the **Smart Share** module. 🌟

    **How It Works**:
    - Validates the event/folder.
    - Downloads images from S3 and saves them in a folder named after the event.
    - Returns a processing response while continuing in the background.

    ### Request Body:
    - `folder_id` (str): The event/folder name.
    - `images_url` (list[str]): A list of image URLs.

    ### Responses:
    - **102 Processing**: Images are being downloaded.
    - **404 Not Found**: Event not found or no image URLs provided.
    - **500 Internal Server Error**: Unexpected error.
    """

    user_id = user.get('id')
    event_id = event_data.folder_id
    urls = event_data.images_url

    try:
        
        # Check if event folder exists
        folder_data = (await db_session.execute(
            select(SmartShareFolder).where(
                SmartShareFolder.id == event_id,
                SmartShareFolder.user_id == user_id
            )
        )).scalar_one_or_none()
      
        if not folder_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Event "{event_id}" not found.')

        if not urls:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No image URLs provided!')

        # check if the local folder of the event exsist or not, if not then create one
        event_folder_path = os.path.join("src","services","SmartShare","Smart_Share_Events_Data", f"{folder_data.id}")
        if not os.path.exists(event_folder_path):
            os.makedirs(event_folder_path, exist_ok=True)


        try:
            share_image_task = download_and_process_images.apply_async(args=[user_id, user.get('username'), event_id, folder_data.name, event_folder_path, urls, f"{folder_data.name}.bin", f"{folder_data.name}.pkl", [user.get('email')]])
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error sending task to Celery: {str(e)}")

        
        folder_data.status = PublishStatus.PENDING.value
        
        await db_session.commit()        
        
        return JSONResponse({"task_id": share_image_task.id}) 
        

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
  

@router.post('/associate-user/{event_id}')
async def associate_user_with_smart_folder(
    event_id: UUID, 
    db_session: DBSessionDep, 
    user: User = Depends(get_user)
):
    """
    👤 **Associate a User with a Smart Share Folder** 📂

    This endpoint associates an **existing user** with a **Smart Share Folder**. 
    If the user is already linked to the folder, a `409 Conflict` response is returned.

    ### Process:
    1. **User Verification**: Ensures the requesting user exists in the system.
    2. **Association Check**: Confirms whether the user is already linked to the folder.
    3. **Association Creation**:
       - If the user **is not associated**, they are linked to the folder.
       - If the user **is already associated**, the request is rejected.

    ### Parameters:
    - **`event_id`** *(UUID, required)*: The unique identifier of the Smart Share Folder.
    
    ### Responses:
    - ✅ **200 OK**: **Success!** The user was successfully associated with the folder.
    - 🔄 **409 Conflict**: The user is already linked to this folder.
    - ❌ **400 Bad Request**: Invalid folder ID or database constraint violation.
    - ⚠️ **500 Internal Server Error**: Unexpected server error.

    """
    user_id = user.get('id')
    return await associate_user_with_folder(db_session=db_session, user_id=user_id, event_id=event_id)


@router.post('/get_images/{event_id}', status_code=status.HTTP_200_OK, response_model=List[SmartShareImageResponse])
async def get_images(event_id: UUID, db_session: DBSessionDep, image: UploadFile = File(...), user: User = Depends(get_user)):
    """Fetches images similar to the uploaded image for the given event_id."""
    
    user_id = user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access')

    # Fetch event folder
    folder_data = await db_session.scalar(
        select(SmartShareFolder).where(
            SmartShareFolder.id == event_id,
        )
    )

    if not folder_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Event with id {event_id} not found!')

    try:
        event_folder_path = os.path.join("src", "services", "SmartShare", "Smart_Share_Events_Data", f"{folder_data.id}")
        hnswlib_index_path = os.path.join(event_folder_path, f'{folder_data.name}.bin')
        image_map_path = os.path.join(event_folder_path, f'{folder_data.name}.pkl')

        # Perform face search
        matches_arr = await get_similar_images(query_image=image, image_map_picklefilepath=image_map_path, index_hnsw_filepath=hnswlib_index_path, threshold=0.90)
        
        found_images = []
        
        print("\n\n\ matche arr", matches_arr)
        
        for record in matches_arr:
            decoded_record = unquote(record)  # Decode URL-encoded characters for coverting %20 back to 'space' so we can get images 
            print("\n\n\n\n decoded record", decoded_record)
            result = await db_session.execute(
                select(SmartShareImagesMetaData).where(
                    SmartShareImagesMetaData.smart_share_folder_id == folder_data.id,
                    SmartShareImagesMetaData.name == decoded_record
                )
            )
            found_result = result.scalar_one_or_none()
            print("\n\n\n\n found result", found_result)
            
            if found_result:
                found_images.append(found_result)

        print("\n\n\ found_images", found_images)
        print("\n\n\n")

        return found_images

    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    
@router.patch('/update_event/{event_id}', status_code=status.HTTP_202_ACCEPTED)
async def update_event(
    event_id: str, 
    db_session: DBSessionDep, 
    description:str = Form(None), 
    cover_image: UploadFile = File(None), 
    user:User = Depends(get_user)
):
    # user_id = "user_2pqOmYikrXY1pWefuBuqzRGm3vA"  # Replace with actual user logic
    user_id = user.get('id')
    try:
        async with db_session.begin():
            # Update event details
            response = await update_event_details(
                db_session=db_session, 
                description=description, 
                cover_image=cover_image, 
                event_id=event_id, 
                user_id=user_id
            )
            await db_session.commit()

        return {"update_event_data": response}

    except HTTPException as e:
        await db_session.rollback()
        raise e

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
    user_id = user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access')

    try:
        async with db_session.begin():
            # Call to delete event from S3 and database
            s3_response, db_response = await delete_event_s3_db(
                db_session=db_session,
                event_name=event_name,
                s3_utils_obj=s3_utils,
                user_id=user_id
            )
        
            # Check if the deletion failed for either S3 or the database
            if db_response.get("message") != "success" or s3_response.get("message") != "Objects deleted successfully":
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content=f"S3 Response: {s3_response}, DB Response: {db_response}"
                )
                
            # Commit all changes if successful
            await db_session.commit()

            return {
                's3_response': s3_response,
                'database_response': db_response,
            }

    except HTTPException as e:
        # Rollback DB changes if HTTPException occurs
        await db_session.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    except Exception as e:
        # Rollback DB changes for any other exception
        await db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

