from qdrant_client import QdrantClient, models
from config.settings import get_settings
from qdrant_client.models import VectorParams, Distance
from uuid import uuid4

settings = get_settings()

class QdrantUtils:
    def __init__(self) -> None:
        self.qdrant_client = QdrantClient(
            url = settings.QDRANT_ENDPOINT_URL,
            api_key = settings.QDRANT_API_KEY,
        )


    #Put data or embedding into collection
    def upload_image_embeddings(self, collection_name:str, embedding_size:int, vector_data:list):
        # Create collection
        try:
           if not self.qdrant_client.collection_exists(collection_name):
                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=embedding_size, distance=Distance.COSINE),
                )
        except Exception as e:
            return {"error": str(e)}
        
        #some data preprocessing and saving into Qdrant database
        Points = []
        if isinstance(vector_data, list) and len(vector_data) != 0:
            for idx, data in enumerate(vector_data):
                # Checking the dict is not empty
                if isinstance(data, dict):
                    name = data.get('name', '')
                    embeddings = data.get('embeddings', [])
                    # Checking if either name or embeddings were not empty
                    if bool(name) and len(embeddings) != 0:

                        #Prepare the record
                        point = models.PointStruct(
                            id=str(uuid4()),
                            vector=embeddings.tolist(),
                            payload={"image_name": name}
                        )
                        Points.append(point)
                    else:
                        print("Name or embeddings were empty, skipping.")
                else:
                    print("Invalid data format, skipping.")
            
            try:
                # Inserting records into Qdrant Database
                response = self.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=Points
                )
            except Exception as e:
                raise Exception(f"error:{e}")
            
            return response
        
        else:
            return {"error": "No valid vector data provided."}



    #It will get collections
    def get_collection(self):
        pass