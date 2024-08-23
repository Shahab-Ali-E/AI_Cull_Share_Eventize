import os
import logging
import warnings
# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress all logs (0=all logs, 1=INFO, 2=WARNING, 3=ERROR)
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN optimizations

import tensorflow as tf
from transformers import logging as transformers_logging

tf.get_logger().setLevel('ERROR')
logging.getLogger('tensorflow').setLevel(logging.ERROR)

# Suppress specific warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Suppress all warnings as a fallback
warnings.simplefilter("ignore")

# Suppress Transformers model initialization messages
transformers_logging.set_verbosity_error()




from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from config.settings import get_settings
from routes import OAuth, Culling, SmartShare
from config.Database import sessionmanager, Base
from Celery.utils import create_celery
from contextlib import asynccontextmanager 
from dependencies.mlModelsManager import ModelManager


settings = get_settings()


@asynccontextmanager
async def lifeSpan(app:FastAPI):
    print('initalizations of models')
    # Initialize or load the ML models
    ModelManager.get_models(settings)
    print('Test connection to database')
    async with sessionmanager.connect():
        pass 
    yield
    if sessionmanager._engine is None:
        # Close the DB connection
        await sessionmanager.close()



#init fastapi
app = FastAPI(title=settings.APP_NAME, lifespan=lifeSpan)

#init celery
app.celery_app = create_celery()
celery = app.celery_app

#adding middlewares
app.add_middleware(SessionMiddleware, secret_key=settings.APP_SECRET_KEY)

#adding routes here
app.include_router(OAuth.router)
app.include_router(OAuth.welcome_route)
app.include_router(Culling.router)
app.include_router(SmartShare.router)


@app.get('/')
async def method_name(request: Request):
    user = request.session.get('user_id')
    if user:
        return RedirectResponse(url='/welcome') 
    
    return {"Message": "sign out successfully"}