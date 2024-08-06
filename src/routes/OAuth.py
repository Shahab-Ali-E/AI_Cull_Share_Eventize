from fastapi import APIRouter, Request, status, Depends, HTTPException
from starlette.responses import RedirectResponse
from sqlalchemy.orm import Session
from config.Database import get_db
from model.User import User
from services.Auth.google_auth import get_user, google_auth, google_login
from schemas.UserResponse import UserResponse
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
async def auth(request: Request, session: Session = Depends(get_db)):
    return await google_auth(request, session=session)

# Logout here
@router.get('/logout')
async def logout(request: Request):
    user = request.session.get("user_id")
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="you are not logged in")
    request.session.pop("user_id")
    return RedirectResponse(url='/')


# Welcome route after login
@welcome_route.get('/welcome')
async def welcome(User: User = Depends(get_user)):
    print("#########################")
    print(User)
    if not User:
        return RedirectResponse(url='/Auth/login')

    return {
        "data": {
            "id": User['id'],
            "name": User['name'],
            "email": User['email'],
            "picture": User['picture']
        } 
    }
