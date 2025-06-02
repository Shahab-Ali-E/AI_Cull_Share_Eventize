import httpx
from src.config.settings import get_settings

settings = get_settings()

async def refresh_google_token(refresh_token: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url='https://oauth2.googleapis.com/token',
            data={
                'client_id': settings.CLIENT_ID,
                'client_secret': settings.CLIENT_SECRET,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
    return response.json()
