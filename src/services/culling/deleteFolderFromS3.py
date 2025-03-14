from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from model.CullingFolders import CullingFolder
from utils.UpdateUserStorage import update_user_storage_in_db
from sqlalchemy.future import select


async def delete_s3_folder_and_update_db(del_folder_path: str, db_session: AsyncSession, s3_obj, module: str, user_id: str):
    """
    Deletes a folder from AWS S3 and updates the corresponding record in the database.
    The function performs the following steps:
    
    1. Extracts the folder name from the provided S3 path.
    2. Retrieves the folder's metadata from the database.
    3. Deletes the folder from S3.
    4. Removes the corresponding database record if the S3 deletion is successful.
    5. Decrements the user's storage usage in the database based on the size of the deleted folder.

    :param del_folder_path: The full path of the folder in S3 to be deleted.
    :param db_session: The SQLAlchemy database session for executing queries.
    :param s3_obj: The S3 client or resource object to perform S3 operations.
    :param module: The module name associated with the folder (e.g., culling, smart share).
    :param user_id: The ID of the user who owns the folder.

    Returns:
    - A tuple containing the response from S3 and the response from updating the database.

    Raises:
    - HTTPException: If the folder is not found in the database or if there are errors in deleting the folder from S3 or updating the database.
    """

    # Extract folder name from the S3 path
    folder_name = del_folder_path.split('/')[-2]
    # Retrieve folder metadata from the database
    folder_data = (await db_session.scalars(select(CullingFolder).where(CullingFolder.name == folder_name,
                                                                      CullingFolder.user_id == user_id))).first()

    # Raise an error if the folder is not found in the database
    if not folder_data:
        return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content=f'Folder with name {folder_name} not found!'
                )
    
    if folder_data.culling_in_progress is True:
        return JSONResponse(
                    status_code=status.HTTP_423_LOCKED,
                    content=f'Unable to Delete Folder While Culling is In Progress'
                )

    # Attempt to delete the folder from Database
    try:        
        # Attempt to delete the folder from Database
        await db_session.delete(folder_data)
        
        # Decrease the user's storage usage in the database
        db_response = await update_user_storage_in_db(
            module=module,
            db_session=db_session,
            total_image_size=folder_data.total_size,
            user_id=user_id,
            increment=False
        )

        # Attempt to delete the folder from S3
        s3_response, status_code = await s3_obj.delete_object(folder_key=del_folder_path)

        # Check S3 deletion response
        if status_code == 404:
            await db_session.rollback()
            raise HTTPException(
                status_code=status_code,
                detail=s3_response
            )
        
    except HTTPException as e:
        await db_session.rollback()
        raise e
        
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error occurred: {str(e)}"
        )

    return s3_response, db_response
    