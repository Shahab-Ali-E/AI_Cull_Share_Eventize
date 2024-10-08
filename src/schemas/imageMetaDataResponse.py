from pydantic import BaseModel
from datetime import datetime

class ImageMetaDataResponse(BaseModel):
    id: str
    name: str
    Bucket_folder:str
    user_id: str
    folder_id:int

class CullingFolderMetaData(BaseModel):
    id:int
    name:str
    created_at:datetime
    total_size:int
