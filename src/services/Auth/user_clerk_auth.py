from fastapi import HTTPException, status, Request
from sqlalchemy import select
from src.model.User import User
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime


#  sign up user
async def sign_up_user(request:Request, db_session:AsyncSession):
    payload = await request.json()
    print("######### payload #########")
    print(payload)

    if payload.get("type") == "user.created":
        user_data = payload["data"]

        try:
            # Extract timestamps safely with default values
            created_at = user_data.get("created_at")
            last_sign_in_at = user_data.get("last_sign_in_at")

            # Convert timestamps if they exist
            session_created_at = (
                datetime.fromtimestamp(created_at / 1000) if created_at else None
            )
            session_last_active_at = (
                datetime.fromtimestamp(last_sign_in_at / 1000) if last_sign_in_at else None
            )

            async with db_session as session:
                new_user = User(
                    id=user_data["id"],
                    username=user_data.get("username", None),
                    first_name=user_data.get("first_name", None),
                    last_name=user_data.get("last_name", None),
                    profile_image_url=user_data.get("image_url", None),
                    email=user_data["email_addresses"][0]["email_address"],
                    email_verified=user_data["email_addresses"][0]["verification"]["status"] == "verified",
                    phone_numbers=[phone["phone_number"] for phone in user_data.get("phone_numbers", [])],
                    session_created_at=session_created_at,
                    session_last_active_at=session_last_active_at
                )
                session.add(new_user)
                await session.commit()  # Commit changes first
                await session.refresh(new_user)  # Refresh the instance
                
        except KeyError as ke:
            print(f"KeyError: Missing required key: {ke}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Missing key: {ke}")

        except ValueError as ve:
            print(f"ValueError: {ve}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

        except Exception as e:
            print(f"Unexpected Error: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred.")

    return {"success":"successfully user data to database"}


# update user
async def update_user_record(request: Request, db_session: AsyncSession, user_updated_data: dict):
    try:
        # Check if the user record exists in the database
        query = select(User).where(User.id == user_updated_data['id'])
        result = await db_session.execute(query)
        user_record = result.scalar_one_or_none()
        
        if not user_record:
            # Raise a 404 exception if the user is not found
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found in the database."
            )
        
        # Update user fields dynamically
        for key, value in user_updated_data.items():
            if value is not None:
                setattr(user_record, key, value)
        
        # Commit the transaction
        await db_session.commit()
    
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e

    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to update user record: {str(e)}"
        )

# delete user
async def delete_user_record(request:Request, db_session:AsyncSession, user_data, s3_utils):
    try:
        # Check if the user exists in the database
        query = select(User).where(User.id == user_data['id'])
        result = await db_session.execute(query)
        user_record = result.scalar_one_or_none()
        
        if not user_record:
            # Raise a 404 exception if the user is not found
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found in the database."
            )
        
        # delete user folder from s3 also
        try:
            
            s3_response = await s3_utils.delete_object(folder_key=user_data['id'])

        except HTTPException as http_exc:
            # Handle HTTP-specific exceptions (e.g., S3-specific errors)
            await db_session.rollback()
            raise http_exc

        
        await db_session.delete(user_record)
        await db_session.commit()

    except HTTPException as e:
        raise e