from fastapi.responses import JSONResponse
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.model.AssociationTable import SmartShareFoldersSecondaryUsersAssociation
from src.model.User import User
from uuid import UUID

async def associate_user_with_folder(user_id: UUID, event_id:UUID, db_session: AsyncSession):
    """
    Associates user with a smart share folder in the database.

    Args:
        user_id (UUID): The unique identifier of the user to be associated with the folder.
        event_id (UUID): The unique identifier of the smart share folder.
        db_session (AsyncSession): The asynchronous database session for executing queries.

    Returns:
        dict: A response dictionary containing a success message and user details if the association is created.
        JSONResponse: A response with status 302 if the user is already associated with the folder.

    Raises:
        HTTPException (401): If the user does not exist (unauthorized access).
        HTTPException (400): If a foreign key constraint fails.
        HTTPException (500): If a general database error occurs.
    """
    
    try:
        async with db_session.begin():
            # Check if a user with the given email already exists
            user_record_query = select(User).where(
                User.id == user_id
            )
            user_record = await db_session.scalar(user_record_query)
            
            if not user_record:
                raise HTTPException(detail="unauthorized", status_code=status.HTTP_401_UNAUTHORIZED)
            
            # Check if the event is already associated with this user
            existing_association_query = select(SmartShareFoldersSecondaryUsersAssociation).where(
                SmartShareFoldersSecondaryUsersAssociation.smart_share_folder_id == event_id,
                SmartShareFoldersSecondaryUsersAssociation.user_id == user_id
            )
            existing_association = await db_session.scalar(existing_association_query)

            if not existing_association:
                # If the event is not associated, add a new association
                new_association = SmartShareFoldersSecondaryUsersAssociation(
                    user_id=user_id,
                    smart_share_folder_id=event_id
                )
                db_session.add(new_association)
                
            else:
                return JSONResponse(
                    status_code=status.HTTP_302_FOUND,
                    content="User already exists and is associated with this event!"
                )

            # Commit the changes to the database
            await db_session.flush()
            await db_session.refresh(new_association)

            return {
                "message": "User associated successfully!",
                "user": {
                    "user_id": new_association.user_id,
                    "event_id": new_association.smart_share_folder_id
                },
            }
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Foreign key constraint failed.")
    
    except SQLAlchemyError as e:
        raise HTTPException(detail=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    