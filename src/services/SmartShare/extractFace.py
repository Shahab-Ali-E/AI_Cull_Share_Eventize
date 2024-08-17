import numpy as np
import cv2
from PIL import Image

def extract_face(image_content, image_name:str, face_extractor_model):
    try:
        # Convert byte data to numpy array
        nparr = np.frombuffer(image_content, np.uint8)
        if nparr.size == 0:
            raise ValueError("Converted numpy array is empty")
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None or image.size == 0:
            raise ValueError("Failed to decode image from numpy array") 
        
        # Convert the image to grayscale for face detection
        image_grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Detect faces in the grayscale image
        faces = face_extractor_model.detectMultiScale(image_grey, scaleFactor=1.16, minNeighbors=5, minSize=(25, 25), flags=0)

        # Iterate through detected faces and save them
        face_images = []
        for (x, y, w, h) in faces:
            face_image = image[y:y+h, x:x+w]
            face_pil = Image.fromarray(face_image) # Convert array to pillow image obj
            face_images.append(face_pil)
        
        return{
            'name': image_name,
            'faces': face_images
        }
    except Exception as e:
        raise Exception(f"Error detecting faces in {image_name}: {str(e)}")