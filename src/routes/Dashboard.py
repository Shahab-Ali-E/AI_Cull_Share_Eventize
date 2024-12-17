from fastapi import APIRouter, HTTPException,status,Depends,Request,Query
from config.settings import get_settings
from dependencies.user import get_user
from dependencies.core import DBSessionDep


router = APIRouter(
    prefix='/User',
    tags=['Dashboard'],
)

settings = get_settings()

@router.get('/get_user_storage_used')
async def get_user_storage(user = Depends(get_user)):
    try:

        user_id = user.get('id')
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access!')
        
        # get user data from database
        return {
            "message":"success",
            "total_smart_culling_storage":settings.MAX_SMART_CULL_MODULE_STORAGE,
            "total_smart_culling_storage_used":user.get("total_culling_storage_used"),
            "total_smart_share_storage":settings.MAX_SMART_SHARE_MODULE_STORAGE,
            "total_smart_share_storage_used":user.get("total_image_share_storage_used")
        }
    except Exception as e:
        raise e
    

