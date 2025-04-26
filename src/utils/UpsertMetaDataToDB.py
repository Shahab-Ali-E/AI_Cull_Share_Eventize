from fastapi.responses import JSONResponse
from fastapi import HTTPException,status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from typing import Dict, List, Type
from sqlalchemy.orm import DeclarativeMeta
from sqlalchemy import insert



# ############## Syncronous Function ##############
def insert_image_metadata(db_session: Session, bulk_insert_fields: List[Dict], model:Type[DeclarativeMeta]) -> dict:
    """
    Inserts new image metadata records into the database.

    Args:
        db_session (Session): The SQLAlchemy synchronous session used to interact with the database.
        bulk_insert_fields (list of dict): A list of dictionaries, where each dictionary contains the data for a new record.

    Raises:
        Exception: If `bulk_insert_fields` is empty, or if an error occurs while inserting the records.

    Returns:
        dict: A dictionary containing:
            - "status": The status of the operation ("COMPLETED" if successful).
            - "message": A success message upon successful insertion of all records.
    """
    if not bulk_insert_fields:
        raise Exception('no object found in "bulk_insert_fields" to insert')

    try:
        new_records = [model(**record) for record in bulk_insert_fields]
        db_session.bulk_save_objects(new_records)
        return {
            "status": "COMPLETED",
            "message": "Successfully inserted all metadata to database",
            "images_metadata":new_records
        }
    except SQLAlchemyError as e:
        db_session.rollback()
        raise Exception(f"Error inserting image metadata: {str(e)}")

def sync_upsert_folder_metadata_DB(
    db_session: Session, 
    match_criteria: Dict, 
    model: Type[DeclarativeMeta], 
    update_fields: Dict = None, 
    update: bool = False
):
    """
    Save or update folder metadata in the database (synchronous version).
    
    Args:
        db_session (Session): The SQLAlchemy session used to interact with the database.
        match_criteria (dict): Criteria to locate the record to be updated or to use for the new record.
        update_fields (dict, optional): Fields and their new values to update in the existing record.
        update (bool, optional): Flag indicating whether to update an existing record (True) or insert a new record (False).

    Raises:
        HTTPException: 
            - 404 if `update` is True and no record matching `match_criteria` is found.
            - 409 if `update` is False and a record with the same name already exists.
            - 500 if a database error occurs.

    Returns:
        dict: A dictionary containing the status and the saved or updated record.
    """
    try:
        if not match_criteria:
            raise ValueError('Must provide "match_criteria" to insert or update record')
        
        # Build the where clause using SQLAlchemy expressions
        conditions = [getattr(model, key) == value for key, value in match_criteria.items()]
        existing_record = db_session.scalars(select(model).where(*conditions)).first()
        
        if update:
            if not update_fields:
                raise ValueError('Must provide "update_fields" to update record')
            
            if not existing_record:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No record found")
            
            # Update only the specified fields
            for key, value in update_fields.items():
                setattr(existing_record, key, value)
        else:
            if existing_record:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f'Folder already exists with name {existing_record.name}!'
                )
            
            # Create a new record
            new_record = model(**match_criteria)
            existing_record = new_record
        
        db_session.add(existing_record)
        return {"status": "COMPLETED", "data": existing_record}
    
    except SQLAlchemyError as e:
        db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error saving or updating metadata: {str(e)}")
    
    
    
############ Asynchronous Function ##############
async def update_image_metadata(db_session: AsyncSession, match_criteria: Dict, update_fields: Dict, model:Type[DeclarativeMeta]) -> dict:
    """
    Updates an existing image metadata record in the database.

    Args:
        db_session (AsyncSession): The SQLAlchemy asynchronous session used to interact with the database.
        match_criteria (dict): Criteria to identify the record to be updated.
                               Should include primary key or unique constraints.
        update_fields (dict): A dictionary containing fields and their new values.

    Raises:
        Exception: 
            - If `match_criteria` or `update_fields` are not provided.
            - If no matching record is found.
            - If a SQLAlchemy error occurs during the update operation.

    Returns:
        dict: A dictionary containing:
            - "status": The status of the operation ("success" if the operation was successful).
            - "data": The updated record.
    """
    if not update_fields or not match_criteria:
        raise Exception('must provide "update_fields" and "match_criteria" to update record')

    try:
        condition = [getattr(model, key) == value for key, value in match_criteria.items()]
        existing_record = (await db_session.scalars(select(model).where(*condition))).first()

        if not existing_record:
            raise Exception("No image found to update.")

        for key, value in update_fields.items():
            setattr(existing_record, key, value)
        db_session.add(existing_record)
        await db_session.refresh(existing_record)
        return {"status": "success", "data": existing_record}
    
    except SQLAlchemyError as e:
        await db_session.rollback()
        raise Exception(f"Error updating image metadata: {str(e)}")
    

async def upsert_folder_metadata_DB(db_session: AsyncSession, match_criteria: dict, model:Type[DeclarativeMeta], update_fields: dict = None, update=False): 
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
        conditions = [getattr(model, key) == value for key, value in match_criteria.items()]
        existing_record = (await db_session.scalars(select(model).where(*conditions))).first()
        
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
                return JSONResponse(
                    status_code=status.HTTP_409_CONFLICT,
                    content=f'Folder already with name {existing_record.name} already found !'
                )
               
            # Create a new record
            new_record = model(**match_criteria)
            existing_record = new_record
        
        db_session.add(existing_record)
          
    except SQLAlchemyError as e:
        await db_session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error saving or updating metadata: {str(e)}")
    
    return {"status": "COMPLETED", "data": existing_record}

async def insert_image_metadata_async(
    db_session: AsyncSession,
    bulk_insert_fields: List[Dict],
    model: Type[DeclarativeMeta]
) -> dict:
    """
    Asynchronously bulk-inserts new image metadata records into the database.

    Args:
        db_session (AsyncSession): The SQLAlchemy async session.
        bulk_insert_fields (List[Dict]): A list of dicts, each with the kwargs for one model instance.
        model (DeclarativeMeta): The SQLAlchemy model class.

    Raises:
        Exception: If bulk_insert_fields is empty or if the insert fails.

    Returns:
        dict: { "status": "COMPLETED", "message": ..., "images_metadata": [model instances] }
    """
    if not bulk_insert_fields:
        raise Exception('no object found in "bulk_insert_fields" to insert')

    # Pre‐build instances for returning (they won’t be in the session, but carry your data)
    new_records = [model(**data) for data in bulk_insert_fields]

    try:
        stmt = insert(model)
        # this issues a single multi‐row INSERT
        await db_session.execute(stmt, bulk_insert_fields)
        return {
            "status": "COMPLETED",
            "message": "Successfully inserted all metadata to database",
            "images_metadata": new_records
        }
    except SQLAlchemyError as e:
        await db_session.rollback()
        raise Exception(f"Error inserting image metadata: {str(e)}")
