from pydantic import BaseModel, UUID4
from datetime import datetime

# Models for returning data
class ImageMetaDataResponse(BaseModel):
    id: UUID4
    name: str
    Bucket_folder: str
    user_id: str
    folder_id: int

class PresingedUrlBeforeCullResponse(BaseModel):
    url: str

class CulledImagesMetadataResponse(BaseModel):
    id: str
    name: str
    file_type: str
    download_path: str
    link_validity: datetime
