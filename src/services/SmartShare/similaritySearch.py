from io import BytesIO
import pickle
import tempfile
import faiss
import numpy as np
from services.SmartShare.tasks.imageShareTask import get_face_embedding
from PIL import Image

async def get_similar_images(query_image, index_fias_filepath: str, image_map_picklefilepath: str, threshold=0.6):
    """Finds all images with an exact matching face to the query image."""
    
    # Read file bytes
    image_bytes = await query_image.read()
    
    # Convert bytes to a PIL image
    image_pil = Image.open(BytesIO(image_bytes)).convert('RGB')

    # Save image to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        image_pil.save(temp_file, format="JPEG")
        temp_file_path = temp_file.name  # Get the temp file path

   
    index = faiss.read_index(index_fias_filepath)
    with open(image_map_picklefilepath, "rb") as f:
        image_map = pickle.load(f)
    query_embedding = get_face_embedding(temp_file_path)
    if query_embedding is None:
        return []

    query_embedding = np.array(query_embedding[0])  # Use the first detected face
    D, I = index.search(query_embedding, len(image_map))

    matched_images = [image_map[i] for i, d in zip(I[0], D[0]) if d < threshold]
    return matched_images