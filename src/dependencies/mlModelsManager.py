from transformers import ViTForImageClassification, ViTFeatureExtractor, CLIPImageProcessor, CLIPModel 
from tensorflow.keras.models import load_model  # type: ignore
from mtcnn import MTCNN
import torch

# Singleton pattern to manage models
class ModelManager:
    _models = None
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print()
    print()
    print("device",device)

    @staticmethod #this decoretor allow us to do not create instance of class we can call this function by just class name
    def get_models(settings):
        if ModelManager._models is None:
            ModelManager._models = ModelManager.initialize_models(settings=settings)
        return ModelManager._models
    
    @staticmethod
    def initialize_models(settings):
    
        # Blur detection loading 
        blur_detect_model = ViTForImageClassification.from_pretrained(settings.BLUR_VIT_MODEL, from_tf=True).to(ModelManager.device)
        feature_extractor = ViTFeatureExtractor.from_pretrained(settings.FEATURE_EXTRACTOR)
        #closed eye detection loading
        # closed_eye_detection_model = load_model(settings.CLOSED_EYE_DETECTION_MODEL)
        closed_eye_detection_model = ViTForImageClassification.from_pretrained(settings.CLOSED_EYE_DETECTION_MODEL, from_tf=True).to(ModelManager.device)
        # Initialize processor and model for embeddings
        embedding_img_processor = CLIPImageProcessor.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL)
        embedding_model = CLIPModel.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL).to(ModelManager.device)
        #Face detector model
        face_detector = MTCNN()

        return{
            "blur_detect_model": blur_detect_model,
            "feature_extractor": feature_extractor,
            "closed_eye_detection_model": closed_eye_detection_model,
            "embedding_img_processor": embedding_img_processor,
            "embedding_model": embedding_model,
            "face_detector": face_detector
        }