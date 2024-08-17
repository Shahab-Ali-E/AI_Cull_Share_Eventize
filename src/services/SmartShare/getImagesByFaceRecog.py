import cv2
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException,status
from config.settings import get_settings
import torch
from transformers import AutoImageProcessor, ResNetForImageClassification
from PIL import Image
import io
from services.SmartShare.extractFace import extract_face
from services.SmartShare.generateEmeddings import generate_face_embeddings

#----instances---
settings = get_settings()


async def get_images_by_face_recog(image:UploadFile, user_id:str, event_name:str, qdrant_util, db_session:Session):
    # Initialize processor and model for embeddings
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(device)
    processor = AutoImageProcessor.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL)
    model = ResNetForImageClassification.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL).to(device)
    face_extractor = cv2.CascadeClassifier(settings.FACE_CASCADE_MODEL)

    image_data = await image.read()

    #extract face
    face_data = extract_face(image_content=image_data,
                            face_extractor_model=face_extractor,
                            image_name=image.filename
                            )
    
    if len(face_data.get('faces')) > 1 or len(face_data.get('faces')) < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f'You can only provide an image of one person—no more, no less')
        
    output =  generate_face_embeddings(image_name=image.filename,
                                        image_pillow_obj=face_data.get('faces')[0],
                                        model=model,
                                        processor=processor
                                    )
    
    qdrant_util.search_points(collection_name=event_name,
                              one_face_embedding=output.get('embeddings'))