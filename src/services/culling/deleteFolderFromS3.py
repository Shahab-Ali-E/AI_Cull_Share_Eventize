from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from model.FolderInS3 import FoldersInS3
from utils.UpdateUserStorage import update_user_storage_in_db
from sqlalchemy.future import select


async def delete_folder_in_s3_and_update_DB(del_folder_path: str, db_session: AsyncSession, s3_obj, module: str, user_id: str):
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
    folder_data = (await db_session.scalars(select(FoldersInS3).where(FoldersInS3.name == folder_name,
                                                                      FoldersInS3.module == module,
                                                                      FoldersInS3.user_id == user_id))).first()
    
    print(folder_data)

    # Raise an error if the folder is not found in the database
    if not folder_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder with name '{folder_name}' not found in database"
        )

    total_folder_size = folder_data.total_size

    # Attempt to delete the folder from S3
    try:
        s3_response = await s3_obj.delete_object(folder_key=del_folder_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting folder from S3: {str(e)}"
        )

    # If the deletion was successful, delete the record from the database
    if s3_response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
        print('executing if')
        try:
            await db_session.delete(folder_data)
            await db_session.commit()
        except Exception as e:
            await db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error deleting folder record from database: {str(e)}"
            )

        # Decrease the user's storage usage in the database
        db_response = await update_user_storage_in_db(
            module=module,
            db_session=db_session,
            total_image_size=total_folder_size,
            user_id=user_id,
            increment=False
        )

        return s3_response, db_response

    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete folder from S3"
        )
