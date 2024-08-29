from typing import Dict
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException,status
from config.settings import get_settings
import torch
from model.ImagesMetaData import ImagesMetaData
from services.SmartShare.extractFace import extract_face
from utils.generateEmeddings import generate_embeddings
from transformers import CLIPImageProcessor, CLIPModel



import torch
import open_clip
import cv2
from sentence_transformers import util

from services.SmartShare.similaritySearch import get_similar_images

# from services.SmartShare.similaritySearch import getSimilarity
#----instances---
settings = get_settings()
def image_to_dict(image: ImagesMetaData) -> Dict:
    return {
        'id': image.id,
        'image_name': image.image_name,
        'user_id': image.user_id,
        # Add other fields as needed
    }

async def get_images_by_face_recog(image:UploadFile, user_id:str, event_name:str, qdrant_util, db_session:Session):
    
    #Initialize processor and model for embeddings
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # processor = AutoImageProcessor.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL)
    # model = ResNetForImageClassification.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL).to(device)

    # preprocessor = open_clip.create_model_and_transforms('ViT-B-16-plus-240', pretrained="laion400m_e32")[1]
    # model = open_clip.create_model_and_transforms('ViT-B-16-plus-240', pretrained="laion400m_e32")[0].to(device)
    # mm = 'openai/clip-vit-base-patch16'
    model = CLIPModel.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL).to(device)
    preprocessor = CLIPImageProcessor.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL)

    content = await image.read()
    #extract face
    face_data = extract_face(image_content=content,
                            image_name=image.filename
                            )
    if len(face_data.get('faces')) > 1 or len(face_data.get('faces')) < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'You can only provide an image of one person—no more, no less')


    face_embeddings =  generate_embeddings(image_name=image.filename,
                                        image_pillow_obj=face_data.get('faces')[0],
                                        model=model,
                                        processor=preprocessor,
                                        device=device
                                    )
    
    #it will get only those images which are match with face only
    message , similar_images = get_similar_images(event_name=event_name,
                                                one_face_embeddings=face_embeddings.get('embeddings'),
                                                qdrant_util=qdrant_util,
                                                user_id=user_id,
                                                db_session=db_session,
                                                threshold=0.845
                                                )
    
    if not similar_images:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(message))
    
    return similar_images
    
    
    
    # img1 = torch.tensor(faces[0]).unsqueeze(0)  # Add a batch dimension
    # img2 = torch.tensor(faces[1]).unsqueeze(0) 

   

    # img1= faces[0]
    # img2 = faces[1]

    # print(len(img1))
    # print(img1)
    

    # Calculate the cosine similarity between the embeddings
    # similarity_score = torch.nn.functional.cosine_similarity(img1, img2, dim=1)

    # # Print the similarity score
    # print('Similarity score:', similarity_score.item())

    # def imageEncoder(img):
    #     img1 = preprocess(img).unsqueeze(0).to(device)
    #     img1 = model.encode_image(img1)
    #     return img1
    
    # print(len(imageEncoder(img1)[0]))


###########IMP CODE:


# import cv2 
# import numpy as np 
# import insightface from insightface.app 
# import FaceAnalysis from insightface.data 
# import cosine_similarity from sklearn.metrics.pairwise

# app = FaceAnalysis(providers=['CUDAExecutionProvider', 'CPUExecutionProvider']) 
# app.prepare(ctx_id=0, det_size=(640, 640)) 

# img = cv2.imread('ref_face1.jpg') 
# ref_face1 = app.get(img)[0]
# img = cv2.imread('ref_face2.jpg') 
# ref_face2 = app.get(img)[0]
# img = cv2.imread('ref_face3.jpg') 
# ref_face3 = app.get(img)[0]

# out_vec = np.average([ref_face1.normed_embedding, ref_face2.normed_embedding,ref_face3.normed_embedding], axis=0)

# img = cv2.imread('unknown_face1.jpg')
# unk_face = app.get(img)[0]
# similarity = cosine_similarity([out_vec],[unk_face2.normed_embedding])
# print('Similarity:',similarity)

    


   