from datetime import datetime, timedelta, timezone
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi.responses import RedirectResponse
from fastapi import Request
from sqlalchemy.ext.asyncio.session import AsyncSession
from config.settings import get_settings
from model.User import User , Token

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

