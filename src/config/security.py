from io import BytesIO
from typing import List
from fastapi import UploadFile, HTTPException
from PIL import Image
from src.config.settings import get_settings
from src.schemas.ImageMetaDataResponse import temporaryImagesMetadata

settings = get_settings()

async def validate_images_and_storage(
    files: list[UploadFile],
    db_storage_used: int,
    max_uploads: int = 10,
    min_size_kb: int = 1,
    max_size_mb: int = 10
):
    """
    Validate uploaded files and ensure they do not exceed storage limits.
    :param files: List of uploaded files.
    :param db_storage_used: Current storage used by the user (in bytes).
    :param max_uploads: Maximum number of files allowed in a single upload.
    :param min_size_kb: Minimum allowed file size in kilobytes.
    :param max_size_mb: Maximum allowed file size in megabytes.
    :return: Tuple (True, combined_size) if valid, otherwise (None, error_message).
    """
    ALLOWED_TYPES = [
        "image/jpg",
        "image/png",
        "image/jpeg",
        "image/bmp",
        "image/tiff",
    ]
    # Convert sizes to bytes
    min_size_bytes = min_size_kb * 1024
    max_size_bytes = max_size_mb * 1024 * 1024
    max_allowed_storage = settings.MAX_SMART_CULL_MODULE_STORAGE

    # Check if database storage already exceeds the allowed maximum storage
    if db_storage_used >= max_allowed_storage:
        return None, (
            "Your database storage has already exceeded the maximum allowed limit. "
            f"Current usage: {db_storage_used / (1024 * 1024):.2f} MB, "
            f"Limit: {max_allowed_storage / (1024 * 1024):.2f} MB."
        )

    # Check if the number of files exceeds the maximum allowed uploads
    if len(files) > max_uploads:
        return None, f"You can't upload more than {max_uploads} files."

    combined_image_size = 0

    for file in files:
        # Validate file type
        if file.content_type not in ALLOWED_TYPES:
            return None, f"File type '{file.content_type}' is not supported."

        # Read file content
        content = await file.read()

        # Validate file size
        file_size = len(content)
        if file_size < min_size_bytes:
            return None, f"File size is too small. Minimum allowed size is {min_size_kb} KB."
        if file_size > max_size_bytes:
            return None, f"File size is too large. Maximum allowed size is {max_size_mb} MB."

        # Validate image integrity
        try:
            img = Image.open(BytesIO(content))
            img.verify()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")

        # Add to combined size
        combined_image_size += file_size
        file.file.seek(0)  # Reset file pointer for further processing

    # Check if the total storage usage exceeds the maximum allowed
    total_storage_used = db_storage_used + combined_image_size
    print()
    print()
    print("########## total combined storage ###########")
    print(total_storage_used)
    print()
    print()
    print("########## db storage ###########")
    print(db_storage_used)

    
    if total_storage_used > max_allowed_storage:
        return None, (
            # f"Uploading these files would exceed your storage limit of "
            # f"{max_allowed_storage / (1024 * 1024)} MB. "
            # f"Current usage: {db_storage_used / (1024 * 1024)} MB, "
            # f"New files: {combined_image_size / (1024 * 1024)} MB."
            "Not enough storage"
        )

    # If all validations pass
    return True, combined_image_size


async def validate_images_and_storage_v2(
    images_metadata: List[temporaryImagesMetadata],
    combined_size:int,
    db_storage_used: int,
    max_uploads: int = 10,
    min_size_kb: int = 1,
    max_size_mb: int = 10,
):
    """
    Validate uploaded files and ensure they do not exceed storage limits.
    :param files: List of uploaded files.
    :param db_storage_used: Current storage used by the user (in bytes).
    :param max_uploads: Maximum number of files allowed in a single upload.
    :param min_size_kb: Minimum allowed file size in kilobytes.
    :param max_size_mb: Maximum allowed file size in megabytes.
    :return: Tuple (True, combined_size) if valid, otherwise (None, error_message).
    """
    ALLOWED_TYPES = [
        "image/jpg",
        "image/png",
        "image/jpeg",
        "image/bmp",
        "image/tiff",
    ]
    # Convert sizes to bytes
    min_size_bytes = min_size_kb * 1024
    max_size_bytes = max_size_mb * 1024 * 1024
    max_allowed_storage = settings.MAX_SMART_CULL_MODULE_STORAGE

    # Check if database storage already exceeds the allowed maximum storage
    if db_storage_used >= max_allowed_storage:
        return None, (
            "Your database storage has already exceeded the maximum allowed limit. "
            f"Current usage: {db_storage_used / (1024 * 1024):.2f} MB, "
            f"Limit: {max_allowed_storage / (1024 * 1024):.2f} MB."
        )

    # Check if the number of files exceeds the maximum allowed uploads
    if len(images_metadata) > max_uploads:
        return None, f"You can't upload more than {max_uploads} files."


    for file in images_metadata:
        # Validate file type
        if file.file_type not in ALLOWED_TYPES:
            return None, f"File type '{file.file_type}' is not supported."

    # Check if the total storage usage exceeds the maximum allowed
    total_storage_used = db_storage_used + combined_size
    print()
    print()
    print("########## total combined storage ###########")
    print(total_storage_used)
    print()
    print()
    print("########## db storage ###########")
    print(db_storage_used)

    
    if total_storage_used > max_allowed_storage:
        return None, (
            # f"Uploading these files would exceed your storage limit of "
            # f"{max_allowed_storage / (1024 * 1024)} MB. "
            # f"Current usage: {db_storage_used / (1024 * 1024)} MB, "
            # f"New files: {combined_image_size / (1024 * 1024)} MB."
            "Not enough storage"
        )

    # If all validations pass
    return True, combined_size