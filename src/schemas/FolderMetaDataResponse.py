from pydantic import field_validator, UUID4, BaseModel
from fastapi import UploadFile
from datetime import datetime
from typing import List, Optional

class CullingFolderMetaData(BaseModel):
    id: UUID4
    name: str
    created_at: datetime
    total_size: int
    culling_done:bool
    culling_in_progress:bool
    uploading_in_progress:bool
    uploading_task_id:Optional[str] = None

class TemporaryImageURLResponse(BaseModel):
    id: UUID4
    name: str
    file_type: str
    image_download_path: str
    image_download_validity: datetime 
    
class CullingFolderMetaDataById(CullingFolderMetaData):
    temporary_images_urls:List[TemporaryImageURLResponse]

class UploadCullingImagesResponse(BaseModel):
    message: str
    data: List[TemporaryImageURLResponse]
    
class GetAllCullingFoldersResponse(BaseModel):
    total_count: int
    folders: List[CullingFolderMetaData]

class EventsMetaData(BaseModel):
    id: UUID4
    name: str
    cover_image: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    total_size: int
    status:str
    uploading_in_progress: bool
    uploading_task_id: Optional[str]


class EventsResponse(BaseModel):
    total_count: int
    events: List[EventsMetaData]

class CreateEventSchema(BaseModel):
    name:str
    cover_image:UploadFile = None
    
    @field_validator("cover_image", mode="before")
    def validate_cover_image(cls, value):
        if value is None:
            return value
        
        # Check for image MIME type
        if not value.content_type.startswith('image/'):
            raise ValueError("The uploaded file must be an image.")
        
        max_size =  2 * 1024 * 1024  # 2 MB
        if value.size < 0 or value.size >  max_size:
            raise ValueError("File size must be between 0 and 2 MB.")
        
        return value

