from fastapi.responses import JSONResponse
from config.settings import get_settings
from Celery.utils import create_celery
from celery import chain
from services.Culling.tasks.cullingTask import get_images_from_aws
from services.SmartShare.extractFace import extract_face
from utils.generateEmeddings import generate_embeddings
from utils.CustomExceptions import URLExpiredException
from utils.QdrantUtils import QdrantUtils

#---instances---
settings = get_settings()
celery = create_celery()
qdrant_util = QdrantUtils()

# #---Model---
# face_extractor = cv2.CascadeClassifier(settings.FACE_CASCADE_MODEL)

#---------------------Independent Tasks For Image Share------------------------------------------------
@celery.task(name='extract_faces', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5}, queue='smart_sharing')
def extract_faces(self, images):
    extracted_faces = []

    for image in images:
        image_data = image['content']
        image_name = image['name']

        faces = extract_face(image_content=image_data,
                            image_name=image_name
                            )
        
        extracted_faces.append(faces)

    return extracted_faces


@celery.task(name='generate_embeddings', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5}, queue='smart_sharing')
def generate_embeddings(self, faces_data:list):
    all_results=[]

    for face_data in faces_data:
        image_name = face_data['name']
        pil_objs_array = face_data['faces']
        
        for pil_obj in pil_objs_array: 

            if not pil_obj:
                continue #skip if no face pillow obj found

            embeddings = generate_embeddings(
                image_name=image_name,
                image_pillow_obj=pil_obj,
            )
            
            all_results.append(embeddings)

    return all_results

    

@celery.task(name='uploading_embeddings', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5}, queue='smart_sharing')
def uploading_embeddings(self, all_embeddings, event_name:str):
    embedding_size = len(all_embeddings[0]['embeddings'])
    response = qdrant_util.upload_image_embeddings(
                                                    collection_name=event_name,
                                                    vector_data=all_embeddings,
                                                    embedding_size=embedding_size
                                                )
    
    return response

#-----------------------Chaining All Above Task Here----------------------------------

@celery.task(name='image_share_task', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 2}, queue='smart_sharing')
def image_share_task(self, user_id:str, uploaded_images_url:list, event_name:str):
    self.update_state(state='STARTED', meta={'status': 'Task started'})
    task_ids = []
    try:
        # Chain the tasks correctly
        chain_result = chain(
            get_images_from_aws.s(uploaded_images_url),
            extract_faces.s(),
            generate_embeddings.s(),
            uploading_embeddings.s(event_name)
        )

        result = chain_result.apply_async()

        # Get the task IDs of each task in the chain
        task_ids.append(result.id)
        while result.parent:
            result = result.parent
            task_ids.append(result.id)

        task_ids.reverse()  # Reverse to get the correct order of execution

        self.update_state(state='SUCCESS', meta={'status': 'Image sharing task executing in background', 'task_ids': task_ids})
    
    except URLExpiredException() as e:
        self.update_state(state='FAILURE', meta={'status': str(e), 'task_ids': task_ids})
        raise
    except Exception as e:
        self.update_state(state='FAILURE', meta={'status': f"Unexpected error: {str(e)}", 'task_ids': task_ids})
        raise
    
    return JSONResponse(task_ids)
