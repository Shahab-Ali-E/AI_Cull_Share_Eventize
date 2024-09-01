from sqlalchemy.ext.asyncio import AsyncSession
from model.ImagesMetaData import ImagesMetaData
from fastapi import HTTPException,status
from sqlalchemy.future import select

async def get_similar_images(qdrant_util, event_name:str, one_face_embeddings, db_session:AsyncSession, user_id:str, event_id:int, threshold:float=0.80):
    try:
        qdrant_reponse = qdrant_util.search_points(collection_name=event_name,
                                                    one_face_embedding=one_face_embeddings
                                                    )
        
        #getting images name on the base of threshold
        images_name =  [data.payload['image_name'] for data in qdrant_reponse if data.score > threshold]
        # score = [data.score for data in qdrant_reponse if data.score > threshold]

        # print(score)

        if not images_name:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Not found any similar image')

        async with db_session.begin():
            image_meta_data = (await db_session.scalars(
                                    select(ImagesMetaData)
                                    .where(
                                        ImagesMetaData.id.in_(images_name),
                                        ImagesMetaData.user_id == user_id,
                                        ImagesMetaData.folder_id == event_id
                                    )
                                )).all()

        if not image_meta_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Not found record in database')
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR , detail=str(e))

    
    
    # img1 = image1_embed
    # img2 = image2_embed

    # cos_scores = util.pytorch_cos_sim(img1, img2)
    # score = round(float(cos_scores[0][0]) * 100, 2)
    

    # print(f"similarity Score: {round(g, 2)}")
