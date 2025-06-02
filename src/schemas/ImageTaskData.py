from pydantic import BaseModel
from typing import List
from uuid import UUID

class ImageTaskData(BaseModel):
    folder_id: UUID
    images_url: List[str] = []

    # @field_validator("images_url")
    # def validate_presigned_url(cls, urls: List[HttpUrl]):
    #     try:
    #         for url in urls:
    #             parse_url = urlparse(url)
    #             query_params = parse_qs(parse_url.query)

    #             required_params = {'X-Amz-Algorithm', 'X-Amz-Credential', 'X-Amz-Date', 
    #                                 'X-Amz-Expires', 'X-Amz-SignedHeaders', 'X-Amz-Signature'}
    #             if not required_params.issubset(query_params):
    #                 raise ValueError('Invalid S3 presigned URL. Missing required parameters.')

    #             # Validate that the URL is not expired
    #             amz_date = query_params.get('X-Amz-Date')[0]
    #             expires_in = int(query_params.get('X-Amz-Expires')[0])
    #             presigned_time = datetime.strptime(amz_date, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
    #             expiration_time = presigned_time + timedelta(seconds=expires_in)
    #             current_time = datetime.now(tz=timezone.utc)
                
    #             print('########### Presigned time #########')
    #             print(presigned_time)
    #             print('########### Expiration time #########')
    #             print(expiration_time)
    #             print('########### Current time #########')
    #             print(current_time)

    #             if expiration_time < current_time:  # Check if the URL is already expired
    #                 print('########### URL Expired #########')
    #                 print(expiration_time < current_time)
    #                 raise ValueError('The S3 presigned URL has expired.')

    #     except ValidationError as e:
    #         raise HTTPException(status_code=400, detail=str(e))

    #     except Exception as e:
    #         raise HTTPException(status_code=500, detail=str(e))

    #     return urls

    class Config:
        orm_mode = True
