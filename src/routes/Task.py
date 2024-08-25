from fastapi import APIRouter,Request,Depends
from model.User import User
from dependencies.user import get_user
import asyncio
from Celery.utils import get_task_info
from sse_starlette.sse import EventSourceResponse

router = APIRouter(
    tags=['Task Status'],
)


@router.get("/task_status/{task_id}")
async def get_task_status(request:Request,task_id: str, user:User = Depends(get_user)):
    """
    Retrieve the Status of a Background Culling Task

    This endpoint returns the current status of a background culling task, identified by its task ID. The task status is streamed to the client in real-time using Server-Sent Events (SSE).

    ### Parameters:
    - **task_id**: The ID of the task whose status is being queried.
    - **request**: The request object for checking connection status.
    - **user**: The user making the request, obtained through dependency injection.

    ### Responses:
    - **200 OK**: The task status is streamed to the client in real-time.
    - **404 Not Found**: If the task ID does not exist.
    - **500 Internal Server Error**: If an error occurs while retrieving the task status.

    ### Example Usage:
    Send a GET request with the task ID to receive real-time updates on the task's progress.
    """
    async def event_generator(task_id):
        while True:
            if await request.is_disconnected():
                break
            task_info = get_task_info(task_id=task_id)
            yield {
                "event": "message",
                "data": task_info,
            }

            if task_info['state'] in ['FAILURE','SUCCESS']:
                break
            await asyncio.sleep(1)  # Adjust the sleep time as needed

    return EventSourceResponse(event_generator(task_id))