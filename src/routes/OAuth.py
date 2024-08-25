from fastapi import APIRouter, Request, status, Depends, HTTPException
from starlette.responses import RedirectResponse
from dependencies.core import DBSessionDep
from dependencies.user import get_user
from schemas.user import UserResponse
from services.Auth.google_auth import google_auth, google_login
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the authentication router
router = APIRouter(
    prefix='/Auth',
    tags=['authentication'],
    responses={404: {"detail": "route not found"}}
)

# Define the Welcome router
welcome_route = APIRouter(
    tags=['Welcome Page']
)

# Login route
@router.get('/login', status_code=status.HTTP_200_OK)
async def login(request: Request):
    return await google_login(request)

# Google auth sign with google
@router.get('/google-auth')
async def auth(request: Request, db_session:DBSessionDep):
    return await google_auth(request, db_session=db_session)

# Logout here
@router.get('/logout')
async def logout(request: Request):
    user = request.session.get("user_id")
    
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="you are not logged in")
    request.session.pop("user_id")
    request.session.clear()
    
    response = RedirectResponse(url='/')
    response.delete_cookie(key='session')

    return response

# Welcome route after login
@welcome_route.get('/welcome', response_model=UserResponse)
async def welcome(user: UserResponse = Depends(get_user)):
    if not user:
        return RedirectResponse(url='/Auth/login')
    return user

