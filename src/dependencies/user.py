# from utils.RefreshToken import refresh_google_token
# from datetime import timedelta,timezone,datetime
# from fastapi import HTTPException,status,Request
# from fastapi.responses import JSONResponse
# from dependencies.core import DBSessionDep
# from config.settings import get_settings
# from model.User import User , Token
# from sqlalchemy.future import select
# from fastapi import Response
# from sqlalchemy.exc import SQLAlchemyError


# settings = get_settings()
# MAX_SESSION_DURATION = timedelta(hours=settings.MAX_SESSION_DURATION)

# #----------------DEPENDENCY----------------
# # Dependency to get the current user and check if the session expires or if they are unauthorized
# async def get_user(request: Request, db_session: DBSessionDep, response: Response) :

#     user_id = request.session.get('user_id')
#     if not user_id:
#         print("executing 1st")
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized access")
        
#     try:
#         async with db_session as session:
#             # Check if user_id exists in the database
#             user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
#             if not user:
#                 request.session.clear()
#                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized access")

#             # Retrieve the token for the user
#             token = (await session.scalars(select(Token)
#                                            .where(Token.user_id == user_id)
#                                            .order_by(Token.created_at.desc()))).first()

#             if not token:
#                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized access")

#             current_time = datetime.now(tz=timezone.utc)
#             # print("###########################")
#             # print("##########current time######")
#             # print(current_time)
#             # print()
#             # print(MAX_SESSION_DURATION)
#             # print()
#             # print()
#             # print("token created at")
#             # print()
#             # print(token.created_at)
#             # print()
            
#             if token.updated_at is None:
#                 token.updated_at = token.created_at or current_time
            
#             session_duration = current_time - token.updated_at
#             # print(session_duration > MAX_SESSION_DURATION)
            
#             # If session has expired, clear the session and all cookies then redirect to login
#             if session_duration > MAX_SESSION_DURATION:
#                 # print("Condition is True. Attempting to pop session and redirect.")
#                 request.session.pop('user_id', None)
#                 request.session.clear()
#                 response.delete_cookie(key="name")
#                 response.delete_cookie(key="picture")
#                 response.delete_cookie(key="email")
#                 response.delete_cookie(key="session")
#                 return JSONResponse({"message":"unautorized"})

#             # If the token has expired, refresh the token
#             if current_time > token.expires_at:
#                 new_token_data = await refresh_google_token(refresh_token=token.refresh_token)
#                 if 'error' in new_token_data:
#                     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

#                 # Update the token in the database
#                 token.access_token = new_token_data['access_token']
#                 token.refresh_token = new_token_data.get('refresh_token', token.refresh_token)
#                 token.expires_at = current_time + timedelta(seconds=new_token_data['expires_in'])
#                 token.updated_at = current_time
#                 await session.commit()

#             # Set cookies if session is still valid
#             if session_duration <= MAX_SESSION_DURATION:
#                 cookies_expire = MAX_SESSION_DURATION.total_seconds()
#                 response.set_cookie(key='email', value=user.email, httponly=False, samesite="none", secure=True, max_age=int(cookies_expire))
#                 response.set_cookie(key='name', value=user.name, httponly=False, samesite="none", secure=True, max_age=int(cookies_expire))
#                 response.set_cookie(key='picture', value=user.picture, httponly=False, samesite="none", secure=True, max_age=int(cookies_expire))

#     except SQLAlchemyError as e:
#         await db_session.rollback()
#         raise HTTPException(status_code=e.status_code, detail=str(e))
    
#     except Exception as e:
#         await db_session.rollback()
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
    
#     return user

from jose import jwt, jwk
from jose.exceptions import JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from clerk_backend_api import Clerk
from sqlalchemy.future import select
from config.settings import get_settings
from dependencies.core import DBSessionDep
from model.User import User
from sqlalchemy.exc import NoResultFound
import requests


security = HTTPBearer()
settings = get_settings()

# Load Clerk settings
CLERK_ISSUER = settings.CLERK_ISSUER
CLERK_JWKS_URL = settings.CLERK_JWKS_URL
CLERK_SECRECT_KEY = settings.CLERK_SECRET_KEY

# Fetch JWKS (JSON Web Key Set)
def get_jwks():
    response = requests.get(CLERK_JWKS_URL)
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch JWKS")
    return response.json()

# Get public key from JWKS
def get_public_key(kid: str):
    jwks = get_jwks()
    for key in jwks['keys']:
        if key['kid'] == kid:
            return jwk.construct(key)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# Decode and validate Clerk JWT
def decode_token(token: str):
    headers = jwt.get_unverified_headers(token)
    kid = headers['kid']
    public_key = get_public_key(kid)
    try:
        payload = jwt.decode(token, public_key.to_pem().decode('utf-8'), algorithms=['RS256'], audience="your_audience", issuer=CLERK_ISSUER)
        return payload
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e

# Dependency to authenticate user
async def get_user( db_session: DBSessionDep, credentials: HTTPAuthorizationCredentials = Depends(security)):

    token = credentials.credentials
    payload = decode_token(token)
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User ID not found in token")
    
    # Now that we have verified the Bearer token and extracted the 
    # user ID, we can proceed to access protected resources. Note that # # using the Bearer token is more secure than passing a session ID in # the query parameter.
    # We retrieve user details from Clerk directly using the user ID.
    # clerk_sdk = Clerk(bearer_auth=CLERK_SECRECT_KEY)
    # user_details = clerk_sdk.users.list(user_id=[user_id])[0]
    # user = {
    #     "status": "success",
    #     "data": {
    #         "id":user_details.id,
    #         "user_name":user_details.username,
    #         "first_name": user_details.first_name,
    #         "last_name": user_details.last_name,
    #         "profile_image_url":user_details.profile_image_url,
    #         "email": user_details.email_addresses[0].email_address,
    #         "email_verified": user_details.email_addresses[0].verification.status,
    #         "phone": user_details.phone_numbers,
    #         "session_created_at": user_details.created_at,
    #         "session_last_active_at": user_details.last_active_at,
    #     }
    # }

    # print("############# USER DETAILS ##############")
    # print()
    # print()
    # print(user)
    try:
    
        async with db_session as session:
            user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            
            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not registered in the system")
            
    except NoResultFound as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=str(e)
        )
    
    return user.__dict__



# async def get_user(request: Request, db_session: DBSessionDep) :
    # try:
    #     user_id = request.session.get('user_id')
    #     if not user_id:
    #         print("1st")
    #         return None;
    #     async with db_session as session:
    #         # Check if user_id exists in the database
    #         user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    #         if not user:
    #             print("2nd")
    #             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized access")

    #         # Retrieve the token for the user from the database or raise Unauthorized.     
    #         token = (await session.scalars(select(Token).
    #                                         where(Token.user_id == user_id).
    #                                         order_by(Token.created_at.desc()))).first()

    #         if not token:
    #             print("3rd")
    #             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized access")

    #         # Convert current time to naive datetime for comparison
    #         current_time = datetime.now(tz=timezone.utc)
           
    #         if token.updated_at is None:
    #             # Set updated_at to created_at or the current time if it's the user's first session
    #             token.updated_at = token.created_at or current_time
            
    #         session_duration = current_time - token.updated_at
            

    #         if session_duration > MAX_SESSION_DURATION:
                
    #             request.session.pop('user_id', None)  # Using .pop with a default value to avoid KeyError
    #             return RedirectResponse('/Auth/login')
            
    #         else:
    #             print("Condition is False.")
    #         print()
    #         print("#######token expires at##########")
    #         print(token.expires_at)
    #         if current_time > token.expires_at:
    #             print('### your token expires ###')
    #             # Refresh the token by getting it from Google
    #             new_token_data = await refresh_google_token(refresh_token=token.refresh_token)
    #             if 'error' in new_token_data:
    #                 print('4th')
    #                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    #             # Update the existing token with new values
    #             token.access_token=new_token_data['access_token']
    #             token.refresh_token=new_token_data.get('refresh_token', token.refresh_token)
    #             token.expires_at=datetime.now(tz=timezone.utc) + timedelta(seconds=new_token_data['expires_in'])
    #             token.updated_at = datetime.now(tz=timezone.utc)
    #             # Commit the changes
    #             await session.commit()
    #             # try:
                    
    #             # except Exception as e:
    #             #     await db_session.rollback()
    #             #     raise HTTPException(
    #             #                         status_code=status.HTTP_400_BAD_REQUEST,
    #             #                         detail=f"Error updating token in database: {str(e)}"
    #             #                         )
    
    # except Exception as e:
    #     await db_session.rollback()
    #     print(f"Unexpected error: {e}")
    #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
    # return user