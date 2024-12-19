from celery import current_app as current_celery_app
from celery.result import AsyncResult
from fastapi import HTTPException, status
from Celery.config import get_settings


settings = get_settings()


def create_celery():
    celery_app = current_celery_app
    celery_app.config_from_object(settings, namespace='CELERY')
    celery_app.conf.update(task_track_started=True)
    celery_app.conf.update(acks_late= True)
    celery_app.conf.update(task_serializer='pickle')
    celery_app.conf.update(result_serializer='pickle')
    celery_app.conf.update(accept_content=['pickle', 'json'])
    celery_app.conf.update(result_expires=200)

    # timeout and heartbeat settings
    # celery_app.conf.update(broker_heartbeat=None)
    celery_app.conf.update(broker_connection_timeout=3600) # Broker connection timeout in seconds
    
    # Prevents timeout errors during lengthy interactions with Redis for storing or retrieving task results
    celery_app.conf.update( redis_socket_timeout=7200) # Set to 2 hours for long-running tasks
    celery_app.conf.update(redis_socket_keepalive=True)  # Keep the Redis connection alive
    # Worker-related settings
    celery_app.conf.update(worker_max_tasks_per_child=10) # will retart after 10 task so if any task won't let the resource free it will help in that case
    celery_app.conf.update(worker_concurrency=4) # 4 task can run at same time

    # Other useful settings
    celery_app.conf.update(result_persistent=True)
    celery_app.conf.update(worker_send_task_events=False)
    celery_app.conf.update(broker_connection_retry_on_startup=True)
    celery_app.conf.update(imports=['src.services.SmartShare.tasks','src.services.Culling.tasks'])

    return celery_app


# celery = create_celery()

def get_task_info(task_id):
    """
    return task info for the given task_id
    """
    try:
        task_result = AsyncResult(task_id)

        if task_result is None:
            raise HTTPException(status_code=404, detail="Task not found")

        if task_result.state == 'PENDING':
            return {'state': task_result.state, 'status': 'Task is waiting to be processed.'}
        elif task_result.state == 'PROGRESS':
            return {'state': task_result.state, 'status': 'Task is in progress.', 'progress': task_result.info}
        elif task_result.state == 'SUCCESS':
            return {'state': task_result.state, 'status': 'Task completed successfully.', 'result': task_result.result}
        elif task_result.state == 'FAILURE':
            return {'state': task_result.state, 'status': 'Task failed.', 'error': str(task_result.result)}
        else:
            return {'state': task_result.state, 'status': 'Unknown status.'} 
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    