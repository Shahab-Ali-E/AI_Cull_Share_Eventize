from pydantic import BaseModel,EmailStr

class userResponse(BaseModel):
    id:str
    name:str
    email:EmailStr
    picture:str
    total_culling_storage_used: int
    total_image_share_storage_used: int