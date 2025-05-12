from transformers import ViTForImageClassification, ViTFeatureExtractor, CLIPImageProcessor, CLIPModel 
from tensorflow.keras.models import load_model  # type: ignore
from tensorflow.keras.applications import ResNet50 # type: ignore
from facenet_pytorch import MTCNN, InceptionResnetV1
import torch


# Singleton pattern to manage models
class ModelManager:
    _models = None # Shared static instance
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print()
    print() 
    print("device", device)

    @staticmethod #this decoretor allow us to do not create instance of class we can call this function by just class name
    def get_models(settings):
        if ModelManager._models is None: # Create instance only once
            ModelManager._models = ModelManager.initialize_models(settings=settings)
        return ModelManager._models
    
    @staticmethod
    def initialize_models(settings):
        print(f"Loading closed eye model from: {settings.CLOSED_EYE_DETECTION_MODEL}")
        print(f"Loading blur model from: {settings.BLUR_IMAGE_DETECTION_MODEL}")
        
        try:
            feature_extractor = ViTFeatureExtractor.from_pretrained(settings.FEATURE_EXTRACTOR)
            # Blur detection loading 
            blur_detect_model = ViTForImageClassification.from_pretrained(settings.BLUR_IMAGE_DETECTION_MODEL, from_tf=True, use_auth_token=settings.HUGGINGFACE_TOKEN).to(ModelManager.device)
            
            # Closed eye detection loading
            closed_eye_detection_model = ViTForImageClassification.from_pretrained(settings.CLOSED_EYE_DETECTION_MODEL, from_tf=True, use_auth_token=settings.HUGGINGFACE_TOKEN).to(ModelManager.device)
            
            # Duplicate detection model
            duplicate_image_detection_model = ResNet50(weights='imagenet', include_top=False, pooling='avg')
            
            # Initialize processor and model for embeddings
            embedding_img_processor = CLIPImageProcessor.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL)
            embedding_model = CLIPModel.from_pretrained(settings.FACE_EMBEDDING_GENERATOR_MODEL).to(ModelManager.device)
            
            # Face detector model
            face_detector = MTCNN(keep_all=True)
            
            # FaceNet model for face embeddings
            face_net_model = InceptionResnetV1(pretrained='vggface2').eval()
            
            # face_net_model = InceptionResnetV1(pretrained=None, classify=False, device=ModelManager.device).to(ModelManager.device)
            # face_net_model.eval()

            # ckpt = torch.load(settings.FACE_NET_MODEL_WEIGHTS, map_location=ModelManager.device)
            # face_net_model.load_state_dict(ckpt['model_state_dict'])

            print("✅ Model weights loaded, ready for inference.")

            return {
                "blur_detect_model": blur_detect_model,
                "feature_extractor": feature_extractor,
                "closed_eye_detection_model": closed_eye_detection_model,
                "duplicate_image_detection_model": duplicate_image_detection_model,
                "embedding_img_processor": embedding_img_processor,
                "embedding_model": embedding_model,
                "face_detector": face_detector,
                "face_net_model": face_net_model
            }
        except Exception as e:
            print(f"Error loading models: {str(e)}")
            raise