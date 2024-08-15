from qdrant_client import QdrantClient, models
from config.settings import get_settings
from qdrant_client.models import VectorParams, Distance

settings = get_settings()

class QdrantUtils:
    def __init__(self) -> None:
        self.qdrant_client = QdrantClient(
            url = settings.QDRANT_ENDPOINT_URL,
            api_key = settings.QDRANT_API_KEY,
        )

    #It will create a collection
    def create_collection(self, collection_name:str, embedding_size:int):
        if not self.qdrant_client.collection_exists(collection_name):
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=embedding_size, distance=Distance.COSINE),
            )
        else:
            raise Exception()
    
    #Put data or embedding into collection
    def upload_image_embeddings(self, collection_name, embedding_size,):

        self.qdrant_client.upsert(
            collection_name="my_collection",
            records=[
                models.Record(
                        id=idx,
                        vector=vector.tolist(),
                        payload={"color": "red", "rand_number": idx % 10}
                )
                for idx, vector in enumerate(vectors)
            ]
        )
    #It will get collections
    def get_collection(self):
        pass