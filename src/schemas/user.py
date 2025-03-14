from pydantic import BaseModel,EmailStr, Field
from typing import Optional
from  uuid import UUID 

class UserResponse(BaseModel):
    id:str
    user_name:str=Field(default="Anonymous")
    email:EmailStr
    profile_image_url:str
    total_culling_storage_used: int
    total_image_share_storage_used: int


class SignUpResponse(UserResponse):
    status:str

class AddSecondaryUserSchema(BaseModel):
    first_name:str
    last_name:str
    email:EmailStr
    phone:Optional[str]
    event_id:UUID