from sqlalchemy import insert
from model import FolderInS3, ImagesMetaData
from fastapi import HTTPException,status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


async def upsert_image_metadata_DB(db_session:AsyncSession, match_criteria:dict=None, update_fields: dict=None, bulk_insert_fields:list=None, update=False):
    """
    This function handles saving image metadata to the database. It supports both updating existing records and inserting new ones based on the provided arguments.

    Args:
        db_session (AsyncSession): The SQLAlchemy asynchronous session used to interact with the database.
        match_criteria (dict, optional): Criteria to match the record to be updated. This should include the primary key 
                                         or unique constraints necessary to locate the record. Required if `update` is True.
        update_fields (dict, optional): Fields and their new values to update in the existing record. 
                                        Only relevant if `update` is True. Required if `update` is True.
        bulk_insert_fields (list, optional): A list of dictionaries where each dictionary represents a new record's data 
                                             to be inserted into the database. Required if `update` is False.
        update (bool, optional): Flag indicating whether to update an existing record (True) or insert new records (False). 
                                 Defaults to False.

    Raises:
        Exception: 
            - If `update` is True but `match_criteria` or `update_fields` are not provided.
            - If `update` is False but `bulk_insert_fields` is empty.
            - If no matching record is found when `update` is True.
            - If a SQLAlchemy error occurs during the operation, indicating a failure to save the image metadata.

    Returns:
        dict: A dictionary containing:
            - "status": The status of the operation ("success" if the operation was successful).
            - "data": The updated record if `update` is True.
            - "message": A success message if new records were inserted when `update` is False.
    """
    try:
        if update:
            if not update_fields or not match_criteria:
                raise Exception('must provide "update_fields" and "match_criteria" to update record')
            
            condtion = [getattr(ImagesMetaData.ImagesMetaData, key) == value for key, value in match_criteria.items()]
            
            # Check if the record exists
            existing_record = (await db_session.scalars(select(ImagesMetaData.ImagesMetaData).where(*condtion))).first()
            if not existing_record:
                raise Exception("No image found to update.")
            for key, value in update_fields.items():
                setattr(existing_record, key, value)
            db_session.add(existing_record)
            await db_session.refresh(existing_record)
            return {"status": "success", "data": existing_record}
        
        else:
            if not bulk_insert_fields:
                raise Exception('no object found in "bulk_insert_feild" to insert')
            
            # Create a new record
            new_record = [ImagesMetaData.ImagesMetaData(**records) for records in bulk_insert_fields]
            db_session.add_all(new_record)
            return {"status": "success" ,
                    "message":"successfully inserted all metadata to database"
                    }
        
    except SQLAlchemyError as e:
        await db_session.rollback()
        raise Exception(f"Error saving image metadata: {str(e)}")
    

async def upsert_folder_metadata_DB(db_session: AsyncSession, match_criteria: dict, update_fields: dict = None, update=False): 
    """
    Save or update folder metadata in the database.

    This function handles saving or updating folder metadata in the database. Depending on the `update` flag, it either:
    - Updates an existing record that matches the `match_criteria` if `update` is True.
    - Inserts a new record into the database if `update` is False.

    Args:
        db_session (AsyncSession): The SQLAlchemy asynchronous session used to interact with the database.
        match_criteria (dict): Criteria to locate the record to be updated or to use for the new record. Should include the primary key 
                               or unique constraints necessary for matching or creating the record.
        update_fields (dict, optional): Fields and their new values to update in the existing record. 
                                        Only relevant if `update` is True. Required if `update` is True.
        update (bool, optional): Flag indicating whether to update an existing record (True) or insert a new record (False). 
                                 Defaults to False.

    Raises:
        HTTPException: 
            - HTTP 404 (Not Found) if `update` is True and no record matching `match_criteria` is found.
            - HTTP 409 (Conflict) if `update` is False and a record with the same name already exists.
            - HTTP 500 (Internal Server Error) if a database error occurs.

    Returns:
        dict: A dictionary containing:
            - "status": The status of the operation ("success" if the operation was successful).
            - "data": The saved or updated record.
    """

    try:
        if not match_criteria:
            raise Exception('must provide "match_criteria" to insert or update record')
        
        # Build the where clause using SQLAlchemy expressions
        conditions = [getattr(FolderInS3.FoldersInS3, key) == value for key, value in match_criteria.items()]
        existing_record = (await db_session.scalars(select(FolderInS3.FoldersInS3).where(*conditions))).first()
        
        if update:
            if not update_fields:
                raise Exception('must provide "update_fields" to update record')
            
            if not existing_record:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No record found")
            # Update only the specified fields
            for key, value in update_fields.items():
                setattr(existing_record, key, value)

        else:
            if existing_record:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Folder already with name {existing_record.name} already found")
            
            # Create a new record
            new_record = FolderInS3.FoldersInS3(**match_criteria)
            existing_record = new_record
        
        db_session.add(existing_record)
          
    except SQLAlchemyError as e:
        await db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error saving or updating metadata: {str(e)}")
    
    return {"status": "success", "data": existing_record}
