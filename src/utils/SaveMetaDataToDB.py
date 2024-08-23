from model import FolderInS3, ImagesMetaData
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


async def save_image_metadata_to_DB(match_criteria: dict, db_session:AsyncSession,  update_fields: dict=None, update=False):
    """
    This function handles saving image metadata to the database. Depending on the `update` flag, 
    it either updates an existing record or inserts a new record. 

    Args:
        match_criteria (dict): Criteria to match the record to be updated or inserted. 
                               Should include the primary key or unique constraints to locate the record.
        session (Session): The SQLAlchemy session used to interact with the database.
        update_fields (dict, optional): Fields and their new values to update in the existing record. 
                                         Only relevant if `update` is True.
        update (bool, optional): Flag indicating whether to update an existing record (True) or 
                                  insert a new record (False). Defaults to False.

    Raises:
        HTTPException: If a record to be updated is not found (when `update` is True) or if a database error occurs.
        
    Returns:
        dict: A dictionary containing the status of the operation and the saved record. 
              For updates, it returns the updated record; for inserts, it returns the newly created record.
    """
    try:
        if update:
            condtion = [getattr(ImagesMetaData.ImagesMetaData, key) == value for key, value in match_criteria.items()]
            # Check if the record exists
            existing_record = (await db_session.scalars(select(ImagesMetaData.ImagesMetaData).where(*condtion))).first()
            if not existing_record:
                raise Exception("No record found to update.")
            
            for key, value in update_fields.items():
                setattr(existing_record, key, value)
            
        else:
            # Create a new record
            new_record = ImagesMetaData.ImagesMetaData(**match_criteria)
            db_session.add(new_record)
            existing_record = new_record
        
        await db_session.commit()
        # Refresh the record (only if it exists)
        if existing_record:
            await db_session.refresh(existing_record)
        
    except SQLAlchemyError as e:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Error saving image metadata: {str(e)}")
    
    return {"status": "success", "data": existing_record}



async def save_or_update_metadata_in_db(db_session: AsyncSession, match_criteria: dict, update_fields: dict = None, update=False):
    """
    Save or update folder metadata in the database.

    This function handles saving or updating folder metadata in the database. If the `update` flag is set to True,
    it updates an existing record that matches the `match_criteria`. If the record does not exist, it raises an HTTP 404 error.
    If `update` is set to False, it inserts a new record into the database with the provided `match_criteria`.

    Args:
        session (Session): The SQLAlchemy session used to interact with the database.
        match_criteria (dict): Criteria to match the record to be updated or inserted. Should include the primary key or unique constraints.
        update_fields (dict, optional): Fields and their new values to update in the existing record. Only relevant if `update` is True.
        update (bool, optional): Flag indicating whether to update an existing record (True) or insert a new record (False). Defaults to False.

    Raises:
        HTTPException: 
            - HTTP 404 error if `update` is True and no record matching `match_criteria` is found.
            - HTTP 500 error if a database error occurs.

    Returns:
        dict: A dictionary containing the status of the operation and the saved or updated record. 
              For updates, it returns the updated record; for inserts, it returns the newly created record.
    """
    try:
        if update:
            # Build the where clause using SQLAlchemy expressions
            conditions = [getattr(FolderInS3.FoldersInS3, key) == value for key, value in match_criteria.items()]
            existing_record = (await db_session.scalars(select(FolderInS3.FoldersInS3).filter(*conditions))).first()
            if not existing_record:
                raise HTTPException(status_code=404, detail="No record found")
            
            # Update only the specified fields
            for key, value in update_fields.items():
                setattr(existing_record, key, value)
        else:
            # Create a new record
            new_record = FolderInS3.FoldersInS3(**match_criteria)
            db_session.add(new_record)
            existing_record = new_record

        # Commit the transaction
        await db_session.commit()
        if existing_record:
            await db_session.refresh(existing_record)

    except SQLAlchemyError as e:
        # Rollback in case of an error
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Error saving or updating metadata: {str(e)}")
    
    return {"status": "success", "data": existing_record}
