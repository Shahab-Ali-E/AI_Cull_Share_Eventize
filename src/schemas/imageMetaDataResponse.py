from pydantic import BaseModel

class ImageMetaDataResponse(BaseModel):
    id: str
    name: str
    Bucket_folder:str
    user_id: str
    folder_id:int