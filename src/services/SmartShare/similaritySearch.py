# from io import BytesIO
# from fastapi import HTTPException, status
# import pickle
# import tempfile
# import faiss
# import numpy as np
# from src.services.SmartShare.tasks.imageShareTask import get_face_embedding
# from PIL import Image

# async def get_similar_images(query_image, index_fias_filepath: str, image_map_picklefilepath: str, threshold=0.6):
#     """Finds all images with an exact matching face to the query image."""
    
#     # Read file bytes
#     image_bytes = await query_image.read()
    
#     # Convert bytes to a PIL image
#     image_pil = Image.open(BytesIO(image_bytes)).convert('RGB')

#     # Save image to a temporary file
#     with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
#         image_pil.save(temp_file, format="JPEG")
#         temp_file_path = temp_file.name  # Get the temp file path

   
#     index = faiss.read_index(index_fias_filepath)
#     with open(image_map_picklefilepath, "rb") as f:
#         image_map = pickle.load(f)
#     query_embedding = get_face_embedding(temp_file_path)
#     if query_embedding is None:
#         raise HTTPException(status_code=status, detail="No face detected in the image.")

#     query_embedding = np.array(query_embedding[0])  # Use the first detected face
#     D, I = index.search(query_embedding, len(image_map))

#     # matched_images = [image_map[i] for i, d in zip(I[0], D[0]) if d < threshold]
#     # return matched_images
    
#     # Collect matches below threshold
#     matches = [image_map[i] for i, dist in zip(I[0], D[0]) if dist < threshold]
#     # Remove duplicates while preserving order
#     unique_matches = list(dict.fromkeys(matches))
#     return unique_matches

import hnswlib
import numpy as np
import pickle
from PIL import Image
from io import BytesIO
import tempfile
from fastapi import HTTPException
from src.services.SmartShare.tasks.imageShareTask import get_face_embedding

async def get_similar_images(query_image, index_hnsw_filepath: str, image_map_picklefilepath: str, threshold=0.6):
    """Finds all images with a matching face to the query image."""

    # Read and process the query image
    image_bytes = await query_image.read()
    image_pil = Image.open(BytesIO(image_bytes)).convert('RGB')

    # Save image to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        image_pil.save(temp_file, format="JPEG")
        temp_file_path = temp_file.name

    # Load the HNSW index
    dim = 512  # FaceNet embedding size
    index = hnswlib.Index(space='l2', dim=dim)
    index.load_index(index_hnsw_filepath)
    index.set_ef(50)  # ef should be > top_k

    # Load the image map
    with open(image_map_picklefilepath, "rb") as f:
        image_map = pickle.load(f)

    # Get the embedding for the query image
    query_embedding = get_face_embedding(temp_file_path)
    if not query_embedding:
        raise HTTPException(status_code=400, detail="No face detected in the image.")

    query_embedding = np.array(query_embedding[0]).astype('float32').reshape(1, -1)

    # Perform the search
    labels, distances = index.knn_query(query_embedding, k=len(image_map))

    # Filter results based on the threshold
    matches = [image_map[i] for i, dist in zip(labels[0], distances[0]) if dist < threshold]
    unique_matches = list(dict.fromkeys(matches))
    return unique_matches
