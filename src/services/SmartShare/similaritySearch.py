from sqlalchemy.orm import Session
from model.ImagesMetaData import ImagesMetaData
from fastapi import HTTPException,status

def get_similar_images(qdrant_util, event_name:str, one_face_embeddings, db_session:Session, user_id:str, threshold:float=0.80):
    try:
        qdrant_reponse = qdrant_util.search_points(collection_name=event_name,
                                                    one_face_embedding=one_face_embeddings
                                                    )

        #getting images name on the base of threshold
        images_name =  [data.payload['image_name'] for data in qdrant_reponse if data.score > threshold]
        score = [data.score for data in qdrant_reponse if data.score > threshold]

        print(score)

        if not images_name:
            return 'Not found any similar image',None
        
        image_meta_data = db_session.query(ImagesMetaData).filter(ImagesMetaData.id.in_(images_name) , ImagesMetaData.user_id == user_id).all()

        if not image_meta_data:
            return 'Not found record in database',None
        
        return 'Sucess',image_meta_data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR , detail=str(e))

    
    
    # img1 = image1_embed
    # img2 = image2_embed

    # cos_scores = util.pytorch_cos_sim(img1, img2)
    # score = round(float(cos_scores[0][0]) * 100, 2)
    

    # print(f"similarity Score: {round(g, 2)}")
