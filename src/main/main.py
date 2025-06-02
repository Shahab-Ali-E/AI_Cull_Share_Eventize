import asyncio
import os
import logging
import sys
import warnings


if  sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())    

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress all logs (0=all logs, 1=INFO, 2=WARNING, 3=ERROR)
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN optimizations

from fastapi.templating import Jinja2Templates
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
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from src.config.settings import get_settings
from src.routes import OAuth, Culling, SmartShare, Task, Dashboard, EventArrangment
from src.config.Database import sessionmanager
from src.Celery.utils import create_celery
from contextlib import asynccontextmanager 
from src.dependencies.mlModelsManager import ModelManager
from starlette.middleware.cors import CORSMiddleware 
from starlette.middleware import Middleware
from fastapi.staticfiles import StaticFiles

settings = get_settings()


@asynccontextmanager
async def lifeSpan(app:FastAPI):
    print('initalizations of models')
    # Initialize or load the ML models
    ModelManager.get_models(settings)
    print('Test connection to database')
    async with sessionmanager.connect() as conn:
        conn.execute('SELECT 1')

    yield
    print('closing database connection')
    if sessionmanager._engine is None:
        # Close the DB connection
        await sessionmanager.close()


# initalize and declare middlewares
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://0.0.0.0:3000"
]
middlewares = [
    Middleware(
        SessionMiddleware, 
        secret_key=settings.APP_SECRET_KEY
    ),
    Middleware( 
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
]

#init fastapi
app = FastAPI(title=settings.APP_NAME, lifespan=lifeSpan, middleware=middlewares)

#init celery
app.celery_app = create_celery()
celery = app.celery_app

# added static files director
project_root = os.path.dirname(os.path.abspath(__file__))
app.mount("/static",StaticFiles(directory="static"), name="static" )

#adding routes here
app.include_router(OAuth.router)
app.include_router(OAuth.welcome_route)
app.include_router(Dashboard.router)
app.include_router(Culling.router)
app.include_router(SmartShare.router)
app.include_router(EventArrangment.router)
app.include_router(Task.router)

# Define a global 500 error handler
@app.exception_handler(500)
async def internal_server_error_handler(request:Request, exc:Exception):
    logging.error(f"Internal server error occurred: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred. Please try again later."}
    )

@app.get('/')
async def method_name(request: Request):
    user = request.session.get('user_id')
    if user:
        return RedirectResponse(url='/welcome') 
    
    return {"Message": "sign out successfully"}