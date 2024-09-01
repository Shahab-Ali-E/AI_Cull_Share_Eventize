from pydantic import BaseModel, field_validator, HttpUrl, ValidationError
from typing import List
from urllib.parse import urlparse, parse_qs
from datetime import timedelta,datetime,timezone
from fastapi import HTTPException


class ImageTaskData(BaseModel):
    folder_name: str
    images_url: List[str]=[]
    
    @field_validator("images_url")
    def validate_presigned_url(cls, urls: HttpUrl):
        try:
            for url in urls:
                parse_url = urlparse(url)
                query_params = parse_qs(parse_url.query)
                
                required_params = {'X-Amz-Algorithm', 'X-Amz-Credential', 'X-Amz-Date', 
                                    'X-Amz-Expires', 'X-Amz-SignedHeaders', 'X-Amz-Signature'
                                    }
                if not required_params.issubset(query_params):
                    raise ValueError('Invalid S3 presigned URL. Missing required parameters.')
                
                # Validate that the URL is not expired
                amz_date = query_params.get('X-Amz-Date')[0]
                expires_in  = int(query_params.get('X-Amz-Expires')[0])
                presigned_time = datetime.strptime(amz_date, f'%Y%m%dT%H%M%SZ')# Convert amz_date to datetime
                expiration_time = presigned_time + timedelta(seconds=expires_in)# Calculate expiration time
                if expiration_time.astimezone(tz=timezone.utc) < datetime.now(tz=timezone.utc): # Check if the URL is already expired
                    raise ValueError('The S3 presigned URL has expired.')
                
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
        return urls
    
    class Config:
        orm_mode = True
            
