from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class ContactUsSchema(BaseModel):
    first_name:str = Field(..., min_length=3, max_length=20, description="enter firstname", title="First Name")
    last_name:str = Field(..., min_length=3, max_length=20, description="enter lastname", title="Last Name")
    email:EmailStr = Field(..., description="enter email", title="Email")
    phone:Optional[str] = Field(None, title="Phone Number", description="Phone number of the user.")
    description:str = Field(..., min_length=20, max_length=250, title="Description", description="Description of the problem.")