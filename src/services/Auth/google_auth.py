from datetime import datetime, timedelta, timezone
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi.responses import RedirectResponse
from fastapi import Request, HTTPException, status
from sqlalchemy.ext.asyncio.session import AsyncSession
from config.settings import get_settings
from dependencies.core import DBSessionDep
from model.User import User , Token
from schemas.user import UserResponse
from utils.RefreshToken import refresh_google_token
import logging
from sqlalchemy.future import select

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Oauth = OAuth()
settings = get_settings()

Oauth.register(
    name='google',
    server_metadata_url=settings.SERVER_METADATA_URL,
    client_id=settings.CLIENT_ID,
    client_secret=settings.CLIENT_SECRET,
    client_kwargs={
        'scope': 'openid email profile',
        "access_type": "offline",
        'prompt': 'consent',
        'redirect_uri': 'https://localhost:8000/Auth/google-auth'
    }
)

MAX_SESSION_DURATION = timedelta(days=settings.MAX_SESSION_DURATION)

# Login
async def google_login(request):
    user = request.session.get("user_id")
    if not user:
        url = request.url_for('auth')
        return await Oauth.google.authorize_redirect(request, url, access_type="offline")

    return RedirectResponse(url='/welcome')

# Redirect here for authentication and save the credential in DB
async def google_auth(request: Request, db_session:AsyncSession):
    try:
        token = await Oauth.google.authorize_access_token(request)
    except OAuthError as e:
        logger.error(f"OAuthError: {e}")
        return {"error": str(e)}

    # Extracting userinfo from token
    user_info = token.get('userinfo')

    if user_info:
        # Check if the user exists
        user = (await db_session.scalars(select(User).where(User.email == user_info['email']))).first()

        # If there is no user, create one
        if not user:
            new_user = User(
                id=user_info['sub'],
                email=user_info['email'],
                name=user_info['name'],
                email_verified=user_info['email_verified'],
                picture=user_info['picture']
            )
            db_session.add(new_user)
            await db_session.commit()
            await db_session.refresh(new_user)

            # New token for user
            new_token = Token(
                access_token=token['access_token'],
                refresh_token=token['refresh_token'],
                expires_at=datetime.now(tz=timezone.utc) + timedelta(seconds=token['expires_in']),
                user_id=user_info['sub']
            )
            db_session.add(new_token)
            await db_session.commit()
            await db_session.refresh(new_token)
        else:
            # Update the token for existing user
            update_token = (await db_session.execute(select(Token).where(Token.user_id == user.id))).scalar_one_or_none()
            print()
            print('###########token################')
            print(update_token)

            if update_token:
                update_token.access_token = token['access_token']
                update_token.refresh_token = token['refresh_token']
                update_token.expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=token['expires_in'])
                update_token.updated_at = datetime.now(tz=timezone.utc)
                db_session.add(update_token)
                await db_session.commit()
                await db_session.refresh(update_token)

    # Save the user_id in the session for token validation
    request.session['user_id'] = user_info['sub']
    return RedirectResponse(url='/welcome')

#----------------DEPENDENCY----------------
# Dependency to get the current user and check if the session expires or if they are unauthorized
async def get_user(request: Request, db_session: DBSessionDep) :
    try:
        user_id = request.session.get('user_id')
        # Check if user_id exists in the session
        if not user_id:
            print("1st")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized access")

        # Check if user_id exists in the database
        user = (await db_session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            print("2nd")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized access")

        # Retrieve the latest token for the user from the database or raise Unauthorized.     
        token = (await db_session.scalars(select(Token).
                                          where(Token.user_id == user_id).
                                          order_by(Token.created_at.desc()))).first()

        if not token:
            print("3rd")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized access")

        # Convert current time to naive datetime for comparison
        current_time = datetime.now(tz=timezone.utc)
        print("###########################")
        print("##########current time######")
        print(current_time)
        print()
        print(MAX_SESSION_DURATION)
        print()
        print()
        print("token created at")
        print()
        print(token.created_at)
        print()
        session_duration = current_time - token.created_at
        print(session_duration > MAX_SESSION_DURATION)

        if session_duration > MAX_SESSION_DURATION:
            print("Condition is True. Attempting to pop session and redirect.")
            request.session.pop('user_id', None)  # Using .pop with a default value to avoid KeyError
            print("Session popped. Redirecting to login.")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please log in again.")
        else:
            print("Condition is False.")
        print()
        print("#######token expires at##########")
        print(token.expires_at)
        if current_time > token.expires_at:
            print('### your token expires ###')
            # Refresh the token by getting it from Google
            new_token_data = await refresh_google_token(refresh_token=token.refresh_token)
            if 'error' in new_token_data:
                print('4th')
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

            # Update the existing token with new values
            token.access_token=new_token_data['access_token']
            token.refresh_token=new_token_data.get('refresh_token', token.refresh_token)
            token.expires_at=datetime.now(tz=timezone.utc) + timedelta(seconds=new_token_data['expires_in'])
            token.updated_at = datetime.now(tz=timezone.utc)
            # Commit the changes
            try:
                await db_session.commit()
                await db_session.refresh(token)
            except Exception as e:
                await db_session.rollback()
                raise HTTPException(
                                    status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"Error updating token in database: {str(e)}"
                                    )
 
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
    return user