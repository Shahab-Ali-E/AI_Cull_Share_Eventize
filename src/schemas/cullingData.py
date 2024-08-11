from pydantic import BaseModel
from typing import List



class cullingData(BaseModel):
    folder_name: str
    images_url: List[str]=[]

    class Config:
        orm_mode = True