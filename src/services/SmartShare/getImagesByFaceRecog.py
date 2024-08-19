from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException,status
from config.settings import get_settings
import torch
from transformers import AutoImageProcessor, ResNetForImageClassification
import base64
import io
from services.SmartShare.extractFace import extract_face
from services.SmartShare.generateEmeddings import generate_face_embeddings
import numpy as np
from transformers import CLIPImageProcessor, CLIPModel



import torch
import open_clip
import cv2
from sentence_transformers import util
from PIL import Image

# from services.SmartShare.similaritySearch import getSimilarity
#----instances---
settings = get_settings()


async def get_images_by_face_recog(image:list[UploadFile], user_id:str, event_name:str, qdrant_util, db_session:Session):
    
    #Initialize processor and model for embeddings
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # processor = AutoImageProcessor.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL)
    # model = ResNetForImageClassification.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL).to(device)

    # preprocessor = open_clip.create_model_and_transforms('ViT-B-16-plus-240', pretrained="laion400m_e32")[1]
    # model = open_clip.create_model_and_transforms('ViT-B-16-plus-240', pretrained="laion400m_e32")[0].to(device)

    model = CLIPModel.from_pretrained('openai/clip-vit-base-patch32').to(device)
    preprocessor = CLIPImageProcessor.from_pretrained('openai/clip-vit-base-patch32')
    
    faces = []
    for image_data in image:
        content = await image_data.read()
        #extract face
        face_data = extract_face(image_content=content,
                                image_name=image_data.filename
                                )

    
        try:
            output =  generate_face_embeddings(image_name=image_data.filename,
                                                image_pillow_obj=face_data.get('faces')[0],
                                                model=model,
                                                processor=preprocessor
                                            )
            first_image = output.get('embeddings')
            faces.append(first_image)
        # print(first_image)
        # if len(first_image.shape) == 1:
            # first_image = first_image.reshape(1, -1)  # Reshape to (1, 1000)

        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    

    # img1 = torch.tensor(faces[0]).unsqueeze(0)  # Add a batch dimension
    # img2 = torch.tensor(faces[1]).unsqueeze(0) 

    img1= faces[0]
    img2 = faces[1]

    print(len(img1))
    print(img1)
    def generateScore(image1_embed, image2_embed):
        img1 = image1_embed
        img2 = image2_embed

        cos_scores = util.pytorch_cos_sim(img1, img2)
        score = round(float(cos_scores[0][0]) * 100, 2)
        return score

    print(f"similarity Score: {round(generateScore(img1, img2), 2)}")

    # Calculate the cosine similarity between the embeddings
    # similarity_score = torch.nn.functional.cosine_similarity(img1, img2, dim=1)

    # # Print the similarity score
    # print('Similarity score:', similarity_score.item())

    # def imageEncoder(img):
    #     img1 = preprocess(img).unsqueeze(0).to(device)
    #     img1 = model.encode_image(img1)
    #     return img1
    
    # print(len(imageEncoder(img1)[0]))

    
 



        
    
    # # if len(face_data.get('faces')) > 1 or len(face_data.get('faces')) < 1:
    #     raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'You can only provide an image of one person—no more, no less')


    
    
    # img1 = faces[0]
    # img2= faces[1]


    # distance = getSimilarity(img1,img2)
    # print(distance)
    # if distance < 0.6:
    #     print("Faces are of the same person.")
    # else:
        # print("Faces are of different people.")
    


    # qdrant_util.search_points(collection_name=event_name,
    #                           one_face_embedding=output.get('embeddings'))
