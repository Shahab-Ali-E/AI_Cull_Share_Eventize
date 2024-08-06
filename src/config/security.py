from fastapi import UploadFile


#--------for file validation when uploading images-----------
def images_validation(files:list[UploadFile], max_uploads:int = 10, min_size_kb:int = 1, max_size_mb:int = 10):
    ALLOWED_TYPES=[
        "image/jpg",
        "image/png",
        "image/jpeg",
        "image/bmp",
        "image/tiff",
    ]
    # Convert min_size from KB to bytes and max_size from MB to bytes
    min_size_bytes = min_size_kb * 1024
    max_size_bytes = max_size_mb * 1024 * 1024

    for file in files:
        if file.content_type not in ALLOWED_TYPES:
            return None,"file type not supported !"
        
        if len(files) > max_uploads:
            return None,f"you can't upload more then {max_uploads} files"
        
        content = file.file.read()
        file_size = len(content)
        if file_size < min_size_bytes or file_size > max_size_bytes:
            return None,f"File size should be in between {min_size_kb} kb to {max_size_mb} mb."
        file.file.seek(0)  # Reset file pointer for further processing
    return True,"ok"