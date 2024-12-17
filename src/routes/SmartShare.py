from datetime import datetime, timezone
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import (APIRouter, Depends, File, HTTPException, Query, Request,
                     UploadFile, status, Form)
from fastapi.responses import JSONResponse
from sqlalchemy import asc, desc
from sqlalchemy.future import select

from config.security import validate_images_and_storage
from config.settings import get_settings
from dependencies.core import DBSessionDep
from dependencies.user import get_user
from model.SmartShareFolders import SmartShareFolder
from model.SmartShareImagesMetaData import SmartShareImagesMetaData
from model.User import User
from schemas.FolderMetaDataResponse import CreateEventSchema, EventsMetaData
from schemas.ImageMetaDataResponse import ImageMetaDataResponse
from schemas.ImageTaskData import ImageTaskData
from services.SmartShare.createEvent import create_event_in_S3_and_DB
from services.SmartShare.deleteEvent import delete_event_s3_db_collection
from services.SmartShare.getImagesByFaceRecog import get_images_by_face_recog
from services.SmartShare.imagePreProcessEmbeddings import \
    preprocess_image_before_embedding
from services.SmartShare.tasks.imageShareTask import image_share_task
from services.SmartShare.updateEvent import update_event_details
from utils.QdrantUtils import QdrantUtils
from utils.S3Utils import S3Utils
from utils.UpsertMetaDataToDB import upsert_folder_metadata_DB

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


@router.get("/get_all_events", response_model=List[EventsMetaData])
async def get_all_events(
    request:Request, 
    db_session:DBSessionDep, 
    user:User = Depends(get_user),
    limit: int = Query(10, ge=1, le=100, description="Limit number of events to retrieve"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    search: Optional[str] = Query(None, description="Search by event name"),
    sort_by: Optional[str] = Query("created_date", description="Sort by size, name, or created_date"),
    sort_order: Optional[str] = Query("asc", description="Sort order: asc or desc")

    ):
    """
    📅 **Retrieve All Events** 📅

    Fetch a list of events stored in the system for the authenticated user. The endpoint supports advanced capabilities like pagination, sorting, and filtering.

    ### Parameters:
    - **`limit`** *(int, optional)*: Maximum number of events to retrieve (default: `10`). Must be between `1` and `100`.
    - **`offset`** *(int, optional)*: Number of events to skip from the beginning of the result set (default: `0`).
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
      GET /get_all_events?limit=10&offset=0&sort_by=name&sort_order=desc
      ```

    - **Search for events with "conference" in the name:**
      ```
      GET /get_all_events?search=conference
      ```

    - **Paginate through results (retrieve the next 10 events):**
      ```
      GET /get_all_events?limit=10&offset=10
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
    query = query.limit(limit).offset(offset)

    async with db_session.begin():
        try:
            result = await db_session.scalars(query)
            events = result.all()

            return events
        
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
    - If event images have expired (based on `images_download_validity`), they will not be included in the response.
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
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Event with id {event_id} not found!')
            
            # Query to get the images of the specific event
            images_data = (await db_session.scalars(select(SmartShareImagesMetaData).where(SmartShareImagesMetaData.smart_share_folder_id == event_id))).all()
            images_urls = []
            for data in images_data:
                validity_time =data.images_download_validity
                current_time = datetime.now(timezone.utc)
                
                if current_time < validity_time:         
                        images_urls.append({"url":data.images_download_path, "validity":validity_time})
               
            return {
                "id":event.id,
                "name":event.name,
                "cover_image":event.cover_image,
                "description":event.description,
                "created_at":event.created_at,
                "total_size":event.total_size,
                "images_data":images_urls,
            }

        except HTTPException as e:
            raise HTTPException(status_code=e.status_code, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



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
            s3_response, db_response = await create_event_in_S3_and_DB(event_name=event_name.lower().strip(), event_cover_image=event_cover_image, user_id=user_id, s3_utils_obj=s3_utils, db_session=db_session)
            
            if s3_response !=None or db_response.get("status") != "COMPLETED":
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail= f"S3 response {s3_response} db_response {db_response}") 
            
            # Try to create the collection at Qdrant
            try:
                qdrant_response = qdrant_util.create_collection(collection_name=event_name.lower().strip(), vector_size=500)
            except Exception as e:
                # Rollback DB changes in case of error while creating Qdrant collection
                await db_session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error creating collection at Qdrant: {str(e)}"
                )
            
            await db_session.commit()
            return {
                's3_response': s3_response,
                'database_response': db_response,
                'collection_created': qdrant_response
            }
    
    except HTTPException as e:
        await db_session.rollback()
        raise HTTPException(status_code=e.status_code, detail=str(e))
    
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post('/upload_images/{event_id}', status_code=status.HTTP_202_ACCEPTED)
async def upload_images(request: Request, event_id: str, db_session:DBSessionDep, images: list[UploadFile] = File(...), user: User = Depends(get_user)):
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
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access')

    try:
        async with db_session.begin():
            # Checking if that folder exists in the database or not
            folder_data = (await db_session.scalars(select(SmartShareFolder).where(SmartShareFolder.id == event_id,
                                                                    SmartShareFolder.user_id == user_id
                                                                    ))).first()
            if not folder_data:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find event: {event_id}')

            # Validation if combined size of images is greater than available size and check image validation
            storage_used = (await db_session.scalar(select(User.total_image_share_storage_used).where(User.id == user_id)))#user storage
            is_valid, output = await validate_images_and_storage(
                                                                files=images, 
                                                                max_uploads=100, 
                                                                max_size_mb=10,
                                                                db_storage_used=storage_used
                                                                )
            if not is_valid:
                raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=output)
            
            try:
                #uplaoding image to s3, updating meta data in database and return presinged url
                response  = await preprocess_image_before_embedding(event_name=folder_data.name,
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


    user_id = user.get('id')
    event_id = event_data.folder_id
    urls = event_data.images_url
    try:
        async with db_session.begin():
        # Checking if that folder exists in the database or not
            folder_data = (await db_session.scalars(select(SmartShareFolder).where(SmartShareFolder.id == event_id,
                                                                    SmartShareFolder.user_id == user_id
                                                                    ))).first()
        if not folder_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Could not find event: {event_id}')
        
        if not urls:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'image url not provided !')
        
        #Sending images URL and other info to Celery task     
        task = image_share_task.apply_async(args=[user_id, urls, folder_data.name ])
        
        return JSONResponse({"task_id": task.id})
    
    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



@router.post('/get_images',status_code=status.HTTP_200_OK, response_model=List[ImageMetaDataResponse])
async def get_images(event_name:str, request:Request, db_session:DBSessionDep, image: UploadFile = File(...), user:User = Depends(get_user)):
    user_id = user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='unauthorized access')
    
    async with db_session.begin():
        folder_data = (await db_session.scalars(select(SmartShareFolder).where(SmartShareFolder.name == event_name,
                                                                    SmartShareFolder.user_id == user_id))).first()
    
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


    
@router.patch('/update_event/{event_id}', status_code=status.HTTP_202_ACCEPTED)
async def update_event(
    event_id: str, 
    db_session: DBSessionDep, 
    description:str = Form(None), 
    cover_image: UploadFile = File(None), 
):
    user_id = "user_2pqOmYikrXY1pWefuBuqzRGm3vA"  # Replace with actual user logic
    logging.info(f"Description: {description}")
    logging.info(f"Cover Image: {cover_image.filename if cover_image else None}")
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
async def delete_event(event_name:str, request:Request, db_session:DBSessionDep):
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
    user_id = "user_2pqOmYikrXY1pWefuBuqzRGm3vA"#user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access')

    try:
        async with db_session.begin():
            # Call to delete event from S3 and database
            s3_response, db_response = await delete_event_s3_db_collection(
                db_session=db_session,
                event_name=event_name,
                s3_utils_obj=s3_utils,
                user_id=user_id
            )
            
            print("####### s3 response #####")
            print()
            print(s3_response)
            print("######### db response ########")
            print()
            print(db_response)

            # Check if the deletion failed for either S3 or the database
            if db_response.get("message") != "success" or s3_response.get("message") != "Objects deleted successfully":
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"S3 Response: {s3_response}, DB Response: {db_response}"
                )

            # Try to remove the collection from Qdrant
            try:
                qdrant_response = qdrant_util.remove_collection(collection_name=event_name)
            except Exception as e:
                # Rollback DB changes in case of error while removing Qdrant collection
                await db_session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error removing collection from Qdrant: {str(e)}"
                )

            # Commit all changes if successful
            await db_session.commit()

            return {
                's3_response': s3_response,
                'database_response': db_response,
                'collection_deleted': qdrant_response
            }

    except HTTPException as e:
        # Rollback DB changes if HTTPException occurs
        await db_session.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    except Exception as e:
        # Rollback DB changes for any other exception
        await db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

