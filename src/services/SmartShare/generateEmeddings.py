import torch


def generate_face_embeddings(image_name:str, image_pillow_obj, processor, model):
    try:
        # Process images into tensors
        image_name = image_name
        pil_objs = image_pillow_obj

        # Process images into tensors
        inputs = processor(
            images=pil_objs,
            return_tensors='pt'  # Use 'pt' for PyTorch tensors
        )

        pixel_values = inputs['pixel_values']

        if isinstance(pixel_values, list):
            pixel_values = torch.stack(pixel_values)

        # Get model output
        with torch.no_grad():  # Disable gradient calculation
            outputs = model(pixel_values=pixel_values)

        embeddings = outputs.logits
        print(embeddings.size(0)>0)
        if embeddings.size(0)>0:
            embedding_list = embeddings[0].cpu().numpy()
            return {
                'name': image_name,
                'embeddings':embedding_list
            } # Convert embeddings to numpy arrays for easier handling
        else:
            raise ValueError("No embeddings found in the model output.")

    except Exception as e:
        raise Exception(f"Error generating embeddings: {str(e)}")
