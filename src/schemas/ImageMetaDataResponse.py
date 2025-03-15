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

class PresingedUrlBeforeCullResponse(BaseModel):
    url: str

class CulledImagesMetadataResponse(BaseModel):
    id: str
    name: str
    file_type: str
    image_download_path: str
    image_download_validity: datetime

class SmartShareImageResponse(BaseModel):
    id: str
    name: str
    file_type: str
    upload_at: datetime
    image_download_path: str
    image_download_validity: datetime
