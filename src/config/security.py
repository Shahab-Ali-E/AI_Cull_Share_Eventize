from io import BytesIO
from fastapi import UploadFile, HTTPException
from PIL import Image

async def validate_images_and_storage(
    files: list[UploadFile],
    max_storage_size: int, 
    db_storage_used: int,
    max_uploads: int = 10, 
    min_size_kb: int = 1, 
    max_size_mb: int = 10
):
    """
    Validate the uploaded files based on type, number, and size constraints,
    and check if the combined size of the uploaded files is within the allowed storage limits.

    :param files: List of files to be validated and uploaded.
    :param max_uploads: Maximum number of files allowed to upload.
    :param min_size_kb: Minimum file size in kilobytes.
    :param max_size_mb: Maximum file size in megabytes.
    :param max_storage_size: Maximum allowed storage size.
    :param db_storage_used: Storage already used by the user as recorded in the database.
    :return: A tuple where the first element is `None` if validation fails and `True` if successful, and the second element is an error message or combined image size.
    """

    ALLOWED_TYPES = [
        "image/jpg",
        "image/png",
        "image/jpeg",
        "image/bmp",
        "image/tiff",
    ]
    # Convert min_size from KB to bytes and max_size from MB to bytes
    min_size_bytes = min_size_kb * 1024
    max_size_bytes = max_size_mb * 1024 * 1024

    # Check if the number of files exceeds the maximum allowed uploads
    if len(files) > max_uploads:
        return None, f"You can't upload more than {max_uploads} files"

    combined_image_size = 0

    for file in files:
        if file.content_type not in ALLOWED_TYPES:
            return None, "File type not supported!"

        content = await file.read()

        # Validate image integrity
        try:
            img = Image.open(BytesIO(content))
            img.verify()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error opening image file: {str(e)}")

        file_size = len(content)
        if file_size < min_size_bytes or file_size > max_size_bytes:
            return None, f"File size should be between {min_size_kb} KB to {max_size_mb} MB."

        combined_image_size += file_size
        file.file.seek(0)  # Reset file pointer for further processing

    print('#### combined image size ####')
    print(combined_image_size)
    print()
    print('#### combined image size with database####')
    print(combined_image_size + db_storage_used)

    #check if you are already ran out of storage
    if db_storage_used > max_storage_size:
        return None,"ran out of storage"
    
    # Check if the combined size of the uploaded files would exceed the user's available storage
    elif combined_image_size + db_storage_used > max_storage_size:
        return None, 'Cannot upload more than the maximum allowed storage'

    return True, combined_image_size


    

    
    
