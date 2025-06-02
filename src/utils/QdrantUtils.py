from qdrant_client import QdrantClient, models
from src.config.settings import get_settings
from qdrant_client.models import  Distance
from uuid import uuid4
from fastapi import HTTPException,status

settings = get_settings()

class QdrantUtils:
    def __init__(self) -> None:
        self.qdrant_client = QdrantClient(
            url = settings.QDRANT_ENDPOINT_URL,
            api_key = settings.QDRANT_API_KEY,
        )
    
    def create_collection(self, collection_name: str, vector_size:int):
        if not collection_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Collection name not provided.",
            )

        if vector_size <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vector size must be greater than 0.",
            )

        try:
            # Check if the collection already exists
            try:
                self.qdrant_client.get_collection(collection_name)
                return {"message": "Collection already exists."}
            except Exception as e:
                if "Not found" in str(e):
                    # Collection doesn't exist, proceed to create it
                    self.qdrant_client.create_collection(
                        collection_name=collection_name,
                        vectors_config={
                            "vector": {  # Correct structure for VectorsConfig
                                "size": vector_size,  # Set vector size
                                "distance": "Cosine",  # Use a valid distance metric
                            }
                        },
                    )
                    return {"message": "Collection created successfully."}
                else:
                    raise  # Reraise other exceptions

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error occurred while creating collection: {e}",
            )

            
        
    #Put data or embedding into collection
    def upload_image_embeddings(self, collection_name:str, embedding_size:int, vector_data:list): 
        #some data preprocessing and saving into Qdrant database
        """
        Dynamically sets vector parameters on the first upload.
        """
        if not vector_data:
            return {"error": "No valid vector data provided."}

        try:
            # Check if the collection already exists
            try:
                collection_info = self.qdrant_client.get_collection(collection_name)
                collection_vector_size = collection_info.config.params.vectors.size
            except Exception:
                collection_vector_size = None

            # If the collection exists but doesn't have vector size, set it
            if collection_vector_size is None or collection_vector_size == 1000:
                self.qdrant_client.update_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=embedding_size,  # Dynamically set the size
                        distance=Distance.COSINE,
                    ),
                )

            # Prepare points
            Points = []
            for idx, data in enumerate(vector_data):
                if isinstance(data, dict):
                    name = data.get("name", "")
                    embeddings = data.get("embeddings", [])
                    if name and embeddings:
                        point = models.PointStruct(
                            id=str(uuid4()),
                            vector=embeddings,
                            payload={"image_name": name},
                        )
                        Points.append(point)

            # Insert records into Qdrant Database
            response = self.qdrant_client.upsert(
                collection_name=collection_name,
                points=Points,
            )
            return response

        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"Error occurred while uploading embeddings: {e}")

    def see_images(self, results, top_k=2):
        for i in range(top_k):
            name    = results[i].payload['image_name']
            score = results[i].score

            print(f"Result #{i+1}: {name} was diagnosed with {score * 100} confidence")
            print(f"This image score was {score}")
            # display(image)
            print("-" * 50)
            print()

    #It will get collections
    def search_points(self, collection_name:str, one_face_embedding):
        try:
            result = self.qdrant_client.search(
                collection_name=collection_name,
                query_vector=one_face_embedding,
                limit=1000,
                with_payload=True,
                search_params=models.SearchParams(
                exact=True,  # Turns on the exact search mode
                ),
            )
            
            return result

        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error occurred while searching points: {e}")


    def remove_collection(self, collection_name:str):
        try:
            response = self.qdrant_client.delete_collection(collection_name=collection_name)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error occurred while deleting the collection: {e}")

        # Optionally, return the full response object
        return response