from typing import Dict, List, Optional
from pydantic import BaseModel, UUID4
from datetime import datetime


class CullingFolderMetaData(BaseModel):
    id: UUID4
    name: str
    created_at: datetime
    total_size: int
    temporary_images_urls:Optional[List[Dict[str, Optional[str]]]]
    culling_done:bool
    culling_in_progress:bool
