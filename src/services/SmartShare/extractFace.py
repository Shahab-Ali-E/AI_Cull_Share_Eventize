import numpy as np
import cv2
from PIL import Image
from dependencies.mlModelsManager import ModelManager
from config.settings import get_settings

settings = get_settings()
models = ModelManager.get_models(settings)
face_detector = models["face_detector"]

def extract_face(image_content, image_name:str):
    try:
        # Convert byte data to numpy array
        nparr = np.frombuffer(image_content, np.uint8)
        if nparr.size == 0:
            raise ValueError("Converted numpy array is empty")
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None or image.size == 0:
            raise ValueError("Failed to decode image from numpy array") 
        
        # Convert the image to grayscale for face detection
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Detect faces in the image
        detections = face_detector.detect_faces(image_rgb)

        # Iterate through detected faces and save them
        face_images = []
        for detection in detections:
            x, y, width, height = detection['box']
            x, y = max(0, x), max(0, y)  # Ensure coordinates are positive
            face_image = image_rgb[y:y+height, x:x+width]
            face_pil = Image.fromarray(face_image)  # Convert array to PIL image object
            face_images.append(face_pil)
        
        return{
            'name': image_name,
            'faces': face_images
        }
    except Exception as e:
        raise Exception(f"Error detecting faces in {image_name}: {str(e)}")