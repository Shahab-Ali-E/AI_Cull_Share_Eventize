import os
from transformers import ViTForImageClassification, ViTFeatureExtractor, CLIPImageProcessor, CLIPModel
from tensorflow.keras.applications import ResNet50 # type: ignore
from facenet_pytorch import MTCNN, InceptionResnetV1
import torch

class ModelManager:
    _models = None
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    @staticmethod
    def get_models(settings):
        if ModelManager._models is None:
            ModelManager._models = ModelManager.initialize_models(settings=settings)
        return ModelManager._models

    @staticmethod
    def initialize_models(settings):

        try:
            feature_extractor = ViTFeatureExtractor.from_pretrained(
                settings.FEATURE_EXTRACTOR,
                cache_dir=settings.HF_HOME
            )

            blur_detect_model = ViTForImageClassification.from_pretrained(
                settings.BLUR_IMAGE_DETECTION_MODEL,
                from_tf=True,
                use_auth_token=settings.HUGGINGFACE_TOKEN,
                cache_dir=settings.HF_HOME
            ).to(ModelManager.device)

            closed_eye_detection_model = ViTForImageClassification.from_pretrained(
                settings.CLOSED_EYE_DETECTION_MODEL,
                from_tf=True,
                use_auth_token=settings.HUGGINGFACE_TOKEN,
                cache_dir=settings.HF_HOME
            ).to(ModelManager.device)

            duplicate_image_detection_model = ResNet50(weights='imagenet', include_top=False, pooling='avg')

            embedding_img_processor = CLIPImageProcessor.from_pretrained(
                settings.FACE_EMBEDDING_GENERATOR_MODEL,
                cache_dir=settings.HF_HOME
            )

            embedding_model = CLIPModel.from_pretrained(
                settings.FACE_EMBEDDING_GENERATOR_MODEL,
                cache_dir=settings.HF_HOME
            ).to(ModelManager.device)

            face_detector = MTCNN(keep_all=True)

            face_net_model = InceptionResnetV1(pretrained='vggface2').eval()

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
