from fastapi import APIRouter, HTTPException, Request, status, Depends
from src.config.settings import get_settings
from src.dependencies.core import DBSessionDep
from src.dependencies.user import get_user
import logging
from src.services.Auth.user_clerk_auth import delete_user_record, sign_up_user, update_user_record
from src.utils.S3Utils import S3Utils

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the authentication router
router = APIRouter(
    prefix='/Auth',
    tags=['authentication'],
    responses={404: {"detail": "route not found"}}
)

settings = get_settings()

#instance of S3
s3_utils = S3Utils(aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_region=settings.AWS_REGION,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    bucket_name=settings.AWS_BUCKET_SMART_CULL_NAME,
                    aws_endpoint_url=settings.AWS_ENDPOINT_URL)
# Define the Welcome router
welcome_route = APIRouter(
    tags=['Welcome Page']
)

# sign up route
@router.post('/sign_up', status_code=status.HTTP_201_CREATED)
async def sign_up(request: Request, db_session: DBSessionDep):
    return await sign_up_user(request, db_session)

# update user route
@router.post('/update_user', status_code=status.HTTP_204_NO_CONTENT)
async def update_user(request: Request, db_session: DBSessionDep):
    try:
        # Parse JSON payload
        payload = await request.json()
        
        # Ensure the event type is correct
        if payload.get('type') != "user.updated":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid event type."
            )
        
        user_updated_data = payload.get('data', {})
        print("##### user payload #######")
        print(user_updated_data)
        
        # Check if the `id` field is present in the data
        if not user_updated_data.get('id'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="User ID is missing from payload."
            )
        
        # Call the function to update user record
        await update_user_record(request, db_session, user_updated_data)
        
    except HTTPException as e:
        # Re-raise known HTTP exceptions
        raise e

    except KeyError as e:
        # Handle missing keys in the payload
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Missing required key: {str(e)}"
        )

    except Exception as e:
        # Catch any unexpected exceptions
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An unexpected error occurred: {str(e)}"
        )

@router.post('/delete_user', status_code=status.HTTP_202_ACCEPTED)
async def delete_user(request:Request, db_session:DBSessionDep):
    try:
        # Parse JSON payload
        payload = await request.json()
        
        # Ensure the event type is correct
        if payload.get('type') != "user.deleted":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid event type."
            )
        
        user_data = payload.get('data', {})
        # print("##### user payload #######")
        # print(user_data)
        
        # Check if the `id` field is present in the data
        if not user_data.get('id'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="User ID is missing from payload."
            )
        
        # Call the function to update user record
        await delete_user_record(request, db_session, user_data, s3_utils)
        
    except HTTPException as e:
        # Re-raise known HTTP exceptions
        raise e

    except KeyError as e:
        # Handle missing keys in the payload
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Missing required key: {str(e)}"
        )

    except Exception as e:
        # Catch any unexpected exceptions
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An unexpected error occurred: {str(e)}"
        )



# delete user route
# @router.delete('/delete_user', status_code=status.HTTP_204_NO_CONTENT)
# async def delete_user(request:Request, db_session:DBSessionDep, user = Depends(get_user)):
#     return await delete_user_record(request, db_session)

# @router.get('/login', status_code=status.HTTP_200_OK)
# async def login(request: Request, response:Response):
#     return await google_login(request, response)

# # Google auth sign with google
# @router.get('/google-auth')
# async def auth(request: Request, db_session:DBSessionDep):
#     return await google_auth(request, db_session=db_session)

# # Logout here
# @router.get('/logout',status_code=status.HTTP_200_OK)
# async def logout(request: Request):
#     user = request.session.get("user_id")
#     print(user)
#     if not user:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="you are not logged in")
#     request.session.pop("user_id")
#     request.session.clear()
    
#     response = JSONResponse({"message":"sign out successfully"})
#     response.delete_cookie(key='session')
#     response.delete_cookie(key='name')
#     response.delete_cookie(key='email')
#     response.delete_cookie(key="picture")

#     return response

# Welcome route after login
@welcome_route.get('/welcome')
async def welcome(user = Depends(get_user)):
    # if not user:
    #     return JSONResponse(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         content={
    #             'message': "Unauthorized"
    #         }
    #     )
    return {"message":"ok"}
