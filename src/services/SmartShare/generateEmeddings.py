import torch
from config.settings import get_settings
from dependencies.mlModelsManager import ModelManager

settings = get_settings()
models = ModelManager.get_models(settings)
embedding_img_processor = models["embedding_img_processor"]
embedding_model = models["embedding_model"]

def generate_face_embeddings(image_name: str, image_pillow_obj):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    try:
        # #Ensure the face image is resized to the expected input size of the model
        # resized_face = image_pillow_obj.resize((224, 224))

        # # Process the image using the model's processor
        # inputs = processor(resized_face).unsqueeze(0).to(device)

        # # Print out the shape of the tensor for debugging
        # print(f"Shape of pixel_values: {inputs.shape}")

        # # Get model output
        # with torch.no_grad():  # Disable gradient calculation
        #     outputs = model.encode_image(inputs)

        image = embedding_img_processor(image_pillow_obj, return_tensors="pt")

        pixel_values = image['pixel_values'].to(device)

        with torch.no_grad():
            outputs = embedding_model.get_image_features(pixel_values)

        embeddings = outputs[0]  # Extract embeddings

        # print(embeddings)

        return {
            'name': image_name,
            'embeddings': embeddings
        }

    except Exception as e:
        raise Exception(f"Error generating embeddings: {str(e)}")

