from uuid import UUID
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from model.EventArrangmentForm import EventArrangmentForm

async def get_booked_event_by_id_service(
    db_session,
    event_id: UUID,
    user_id: UUID,
):
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access!')

    async with db_session.begin():
        try:
            event = await db_session.scalar(
                select(EventArrangmentForm).where(
                    EventArrangmentForm.id == event_id,
                    EventArrangmentForm.userId == user_id,
                )
            )
            if event is None:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content=f"Event with id {event_id} not found!"
                )
            return event
        except SQLAlchemyError as e:
            await db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {e}",
            )            