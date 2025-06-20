from pydantic_settings import BaseSettings
from functools import lru_cache
from urllib.parse import quote_plus
from dotenv import load_dotenv
from pathlib import Path
import os
from urllib.parse import quote_plus

env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    HF_HOME: str = os.environ.get("HF_HOME", "/app/.cache/huggingface")
    # App
    APP_NAME:  str = os.environ.get("APP_NAME", "")
    APP_HOSTED_URL:  str = os.environ.get("APP_HOSTED_URL", "")
    DEBUG: bool = bool(os.environ.get("DEBUG", False))
    
    APP_SMART_CULL_MODULE:str = os.environ.get('APP_SMART_CULL_MODULE',None)
    APP_SMART_SHARE_MODULE:str = os.environ.get('APP_SMART_SHARE_MODULE',None)
    MAX_SMART_CULL_MODULE_STORAGE:int = os.environ.get('MAX_SMART_CULL_MODULE_STORAGE',100000000)
    MAX_SMART_SHARE_MODULE_STORAGE:int = os.environ.get('MAX_SMART_SHARE_MODULE_STORAGE',100000000)
    
    # Mail configuration
    MAIL_USERNAME:str = os.environ.get('MAIL_USERNAME',None)
    MAIL_PASSWORD:str = os.environ.get('MAIL_PASSWORD',None)
    MAIL_SERVER:str = os.environ.get('MAIL_SERVER',None)
    MAIL_PORT:int = os.environ.get('MAIL_PORT',None)
    MAIL_FROM:str = os.environ.get('MAIL_FROM',None)
    MAIL_FROM_NAME:str = os.environ.get('MAIL_FROM_NAME',None)
    
    # FrontEnd and Backend hosted Application
    FRONTEND_HOST: str = os.environ.get("FRONTEND_HOST", "http://localhost:3000")
    HOSTED_BACKEND_URL: str = os.environ.get("HOSTED_BACKEND_URL", "http://127.0.0.1")

    # MySql Database Config
    POSTGRES_HOST: str = os.environ.get("POSTGRES_HOST", 'localhost')
    POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "")
    POSTGRES_PASS: str = os.environ.get("POSTGRES_PASSWORD", "")
    POSTGRES_PORT: int = int(os.environ.get("POSTGRES_PORT", 5432))
    POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "")
    
    # Neon Database Config
    POSTGRES_HOST: str = os.environ.get("POSTGRES_HOST", 'localhost')
    NEON_DB_USER: str = os.environ.get("NEON_DB_USER", "")
    NEON_DB_PASSWORD: str = os.environ.get("NEON_DB_PASSWORD", "")
    POSTGRES_PORT: int = int(os.environ.get("POSTGRES_PORT", 5432))
    Neon_DB_DATABASE: str = os.environ.get("Neon_DB_DATABASE", "")
    
    if not POSTGRES_PASS:
        raise ValueError("POSTGRES_PASSWORD environment variable is not set or is empty.")
    # Async URI for standard async operations
    # DATABASE_URI: str = f"postgresql+asyncpg://{POSTGRES_USER}:{quote_plus(POSTGRES_PASS)}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    
    DATABASE_URI: str = f"postgresql+asyncpg://{NEON_DB_USER}:{quote_plus(NEON_DB_PASSWORD)}@ep-odd-wave-a1fkqowx-pooler.ap-southeast-1.aws.neon.tech/{Neon_DB_DATABASE}"
    
    # DATABASE_URL= postgres://user:password@your-neon-hostname.neon.tech/neondb?sslmode=require


    # Sync URI specifically for Celery synchronous tasks
    # SYNC_DATABASE_URI: str = f"postgresql://{POSTGRES_USER}:{quote_plus(POSTGRES_PASS)}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    SYNC_DATABASE_URI: str = f"postgresql://{NEON_DB_USER}:{quote_plus(NEON_DB_PASSWORD)}@ep-odd-wave-a1fkqowx-pooler.ap-southeast-1.aws.neon.tech/{Neon_DB_DATABASE}?sslmode=require"
    
    #QDRANT Database Config
    QDRANT_API_KEY:str = os.environ.get('QDRANT_API_KEY',None)
    QDRANT_ENDPOINT_URL:str = os.environ.get('QDRANT_ENDPOINT_URL',None)

    # Clerk secret key
    CLERK_SECRET_KEY:str = os.environ.get('CLERK_SECRET_KEY',None)
    CLERK_JWKS_URL:str = os.environ.get('CLERK_JWKS_URL',None)
    CLERK_ISSUER:str = os.environ.get('CLERK_ISSUER',None)
    # encoded_password:str = quote_plus(POSTGRES_PASS)#Propely encode password due @ is a special symbol symbol
    # DATABASE_URI: str = f"postgresql://{POSTGRES_USER}:{encoded_password}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

    #JWT Secret Key
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "ad5780b8bd3b2540ef87839b5bb7f617322d9efcb248d7e026d98605780255d6")
    JWT_ALGORITHM: str = os.environ.get("ACCESS_TOKEN_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 3))
    REFRESH_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("REFRESH_TOKEN_EXPIRE_MINUTES", 1440))

    # App Secret Key
    APP_SECRET_KEY: str = os.environ.get("SECRET_KEY", None)

    #AWS CREDENTIALS
    AWS_SECRET_ACCESS_KEY: str = os.environ.get("AWS_SECRET_ACCESS_KEY",None)
    AWS_ACCESS_KEY_ID: str =os.environ.get("AWS_ACCESS_KEY_ID",None)
    AWS_REGION: str = os.environ.get("AWS_REGION",None)
    AWS_BUCKET_SMART_CULL_NAME :str = os.environ.get("AWS_BUCKET_SMART_CULL_NAME",None)
    AWS_BUCKET_SMART_SHARE_NAME: str = os.environ.get('AWS_BUCKET_SMART_SHARE_NAME',None)
    PRESIGNED_URL_EXPIRY_SEC:int = os.environ.get('PRESIGNED_URL_EXPIRY_SEC',1800)
    AWS_ENDPOINT_URL:str = os.environ.get('AWS_ENDPOINT_URL',None)
  
    #AWS FOLDERS
    IMAGES_BEFORE_CULLING_STARTS_Folder:str = os.environ.get("IMAGES_BEFORE_CULLING_STARTS_Folder",None)
    BLUR_FOLDER:str = os.environ.get("BLUR_FOLDER",None)
    CLOSED_EYE_FOLDER:str = os.environ.get("CLOSED_EYE_FOLDER",None)
    DUPLICATE_FOLDER:str = os.environ.get("DUPLICATE_FOLDER",None)
    FINE_COLLECTION_FOLDER: str = os.environ.get("FINE_COLLECTION_FOLDER",None) 

    #Google OAuth CREDENTIALS
    CLIENT_ID: str = os.environ.get("CLIENT_ID",None)
    CLIENT_SECRET: str = os.environ.get("CLIENT_SECRET",None)
    SERVER_METADATA_URL: str = os.environ.get("SERVER_METADATA_URL",None)

    #MAX SESSION DURATION IN DAYS
    MAX_SESSION_DURATION: int = os.environ.get("MAX_SESSION_DURATION",2)

    #AI MODELS CONFIG
    # Hugging Face Token
    HUGGINGFACE_TOKEN: str = os.environ.get("HUGGINGFACE_TOKEN",None)
    # Feature Extractor
    FEATURE_EXTRACTOR : str = os.environ.get("FEATURE_EXTRACTOR",None)
    #BLUR IMAGE DETECTION MODEL
    BLUR_IMAGE_DETECTION_MODEL: str = os.environ.get("BLUR_IMAGE_DETECTION_MODEL",None)
    #CLOSED EYE DETECTIO MODEL
    CLOSED_EYE_DETECTION_MODEL : str = os.environ.get("CLOSED_EYE_DETECTION_MODEL",None)
    # FACE_CASCADE_MODEL: str = os.environ.get("FACE_CASCADE_MODEL",None)
    #FACE_EMBEDDING_GENERATOR_MODEL
    FACE_EMBEDDING_GENERATOR_MODEL:str = os.environ.get('FACE_EMBEDDING_GENERATOR_MODEL',None)
    #Threshold values for face comparision
    FACE_COMPARE_THRESHOLD:float = os.environ.get('FACE_COMPARE_THRESHOLD',None)
    # Face net weights
    FACE_NET_MODEL_WEIGHTS:str = os.environ.get('FACE_NET_MODEL_WEIGHTS',None)
    #Threshold value for duplicate image detection
    BLUR_IMAGE_THRESHOLD:float = os.environ.get('BLUR_IMAGE_THRESHOLD',None)

    #CELERY VARIABLES
    CELERY_BROKER_URL:str = os.environ.get("CELERY_BROKER_URL",None)
    CELERY_RESULT_BACKEND_URL:str = f"db+{SYNC_DATABASE_URI}"
    CELERY_WORKER_CONCURRENCY :int = os.environ.get("WORKER_CONCURRENCY",1)
    CELERY_WORKING_ENV_CONFIG:str = os.environ.get("CELERY_WORKING_ENV_CONFIG","development")


@lru_cache()
def get_settings() -> Settings:
    return Settings()