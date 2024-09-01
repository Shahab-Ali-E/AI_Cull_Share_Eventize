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
    🔄 **Retrieve the Status of a Background Culling Task** 🔄

    This endpoint allows you to check the current status of a background culling task using its unique task ID. The status is streamed to you in real-time via Server-Sent Events (SSE), keeping you updated as the task progresses.

    ### Parameters:
    - **`task_id`** 🆔: The unique ID of the culling task whose status you want to check.
    - **`request`** 🧾: The request object used to manage connection status.
    - **`user`** 👤: The user making the request, provided through dependency injection.

    ### Responses:
    - ✅ **200 OK**: Real-time updates on the task's status are successfully streamed to the client.
    - ❓ **404 Not Found**: The specified task ID does not exist.
    - ⚠️ **500 Internal Server Error**: An unexpected error occurred while retrieving the task status.
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
            await asyncio.sleep(2)  # Adjust the sleep time as needed

    return EventSourceResponse(event_generator(task_id))