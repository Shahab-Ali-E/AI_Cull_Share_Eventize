from fastapi import HTTPException, status, UploadFile, File
import os
import uuid
from src.config.settings import get_settings
from src.model.SmartShareFolders import SmartShareFolder
from src.utils.UpsertMetaDataToDB import upsert_folder_metadata_DB
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()

async def update_event_details(db_session:AsyncSession, event_id: str, user_id: str, cover_image:UploadFile = File(None), description:str=None):
    update_fields = {}
    print("###############")
    print()
    print()
    print()
    print()
    print()
    print(f"des {description}")
    print(f"cover {cover_image.filename if cover_image else None}")

    # Handle cover image if available
    if cover_image:
        if not cover_image.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an image"
            )
        if cover_image.size < 0 or cover_image.size > 2 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image size must be between 0 and 2 MB",
            )
        
        # Ensure event_cover_images folder exists
        local_folder = os.path.join("static", "event_cover_images")
        os.makedirs(local_folder, exist_ok=True)

        # Generate unique filename
        file_extension = cover_image.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        local_file_path = os.path.join(local_folder, unique_filename)

        # Write file to the local folder
        with open(local_file_path, "wb") as file:
            file.write(await cover_image.read())

        # Simulate a publicly accessible URL
        cover_image_url = f"{settings.APP_HOSTED_URL}/{local_folder}/{unique_filename}"
        
        # Add cover_image_url to update_fields
        update_fields["cover_image"] = cover_image_url

    # Handle description if available
    if description != "string" and description is not None:
        update_fields["description"] = description

    # Check if there are any fields to update
    if not update_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    match_criteria = {"id": event_id, "user_id": user_id}
    
    # Perform the update in the database using upsert
    db_response = await upsert_folder_metadata_DB(
        db_session=db_session,
        match_criteria=match_criteria,
        update=True,
        update_fields=update_fields,
        model=SmartShareFolder
    )

    return db_response
