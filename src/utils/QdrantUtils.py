from qdrant_client import QdrantClient, models
from config.settings import get_settings
from qdrant_client.models import VectorParams, Distance
from uuid import uuid4
from fastapi import HTTPException,status

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
            # print(one_face_embedding)
            # Calculate the mean along dimension 1
            # query_vector = one_face_embedding.mean()[0].tolist()
            # print(query_vector)
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