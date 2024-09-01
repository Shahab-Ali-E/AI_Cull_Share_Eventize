from fastapi import HTTPException, status
from model.User import User
from config.settings import get_settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError

settings = get_settings()

async def update_user_storage_in_db(db_session:AsyncSession, total_image_size:int, user_id:str, module:str, increment:bool=True):
    """
    Updates the storage usage for a user in the database based on the operation performed (increment or decrement) 
    and the specified module (culling or smart share).

    :param db_session: The database session for executing queries.
    :param total_image_size: The size of the images to be added or removed from the user's storage.
    :param user_id: The ID of the user whose storage is being updated.
    :param module: The module name, either 'APP_SMART_CULL_MODULE' or 'APP_SMART_SHARE_MODULE'.
    :param operation: The operation type, either 'increment' (default) to increase the storage or False to decrease it.

    Returns:
    - A tuple containing a boolean indicating success, and a dictionary with a message or detail.

    :Raise: HTTPException: If the user is not found or if there is an error updating the storage in the database. 
    """

    user = (await db_session.scalars(select(User).where(User.id == user_id))).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try: 
        if module == settings.APP_SMART_CULL_MODULE:
            if increment:
                user.total_culling_storage_used += total_image_size
            else:
                user.total_culling_storage_used -= total_image_size
                user.total_culling_storage_used = max(user.total_culling_storage_used, 0)
        elif module == settings.APP_SMART_SHARE_MODULE:
            if increment:
                user.total_image_share_storage_used += total_image_size
            else:
                user.total_image_share_storage_used -= total_image_size
                user.total_image_share_storage_used = max(user.total_image_share_storage_used, 0)
        else:
            return False, {'message':'faild', 'detail': 'No module with this name'}

        db_session.add(user)

        return True, {'message': 'success', 'data': user}

    except SQLAlchemyError as e:
        await db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error updating storage usage in database: {str(e)}")

