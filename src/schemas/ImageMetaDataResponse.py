from pydantic import BaseModel, UUID4
from datetime import datetime

# Models for returning data
# class ImageMetaDataResponse(BaseModel):
#     id: UUID4
#     name: str
#     Bucket_folder: str
#     user_id: str
#     folder_id: int

# class ImageMetaDataResponse(BaseModel):
#    image:str

class BaseImageMetaModel(BaseModel):
    name: str
    file_type: str
    image_download_path: str
    image_download_validity: datetime

class PresingedUrlBeforeCullResponse(BaseModel):
    url: str

class ImagesMetadata(BaseImageMetaModel):
    id: str

class temporaryImagesMetadata(BaseImageMetaModel):
    culling_folder_id: UUID4

class SmartShareImageResponse(BaseImageMetaModel):
    id: UUID4
    upload_at: datetime

class SmartShareEventImagesMeta(BaseImageMetaModel):
    smart_share_folder_id:str
    
