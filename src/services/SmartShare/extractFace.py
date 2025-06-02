import numpy as np
import cv2
from PIL import Image
from src.dependencies.mlModelsManager import ModelManager
from src.config.settings import get_settings

settings = get_settings()
models = ModelManager.get_models(settings)
face_detector = models["face_detector"]

def is_face_forward_facing(detection, tolerance=0.1):
    """
    Determines if a face is forward-facing based on landmark positions.
    
    Args:
        detection: A dictionary containing face bounding box and landmarks.
        tolerance: A float specifying how symmetrical the landmarks should be.
    
    Returns:
        bool: True if the face is forward-facing, False otherwise.
    """
    # Extract landmarks
    landmarks = detection.get('keypoints', {})
    if not landmarks:
        return False

    left_eye, right_eye = landmarks['left_eye'], landmarks['right_eye']
    nose = landmarks['nose']

    # Calculate symmetry between eyes and nose
    eye_center_x = (left_eye[0] + right_eye[0]) / 2
    nose_symmetry_x = abs(eye_center_x - nose[0]) / abs(right_eye[0] - left_eye[0])

    return nose_symmetry_x <= tolerance


def extract_face(image_content, image_name:str):
    """
    Determines if a face is forward-facing based on landmark positions.
    
    Args:
        detection: A dictionary containing face bounding box and landmarks.
        tolerance: A float specifying how symmetrical the landmarks should be.
    
    Returns:
        bool: True if the face is forward-facing, False otherwise.
    """
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
            if is_face_forward_facing(detection):
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

# def get_face_embedding(image_path):
#     """Detects faces and extracts embeddings."""
#     image = Image.open(image_path).convert('RGB')
#     faces = mtcnn(image)
    
#     if faces is None:
#         return None  # No face detected
#     print(len(faces))
    
#     embeddings = []
#     for face in faces:
#         # face = face.unsqueeze(0)  # Add batch dimension
#         embedding = model(face)
#         embeddings.append(embedding.detach().numpy())

#     return embeddings
