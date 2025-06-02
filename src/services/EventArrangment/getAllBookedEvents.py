from typing import Optional, Tuple
from uuid import UUID
from sqlalchemy import asc, desc, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from fastapi import HTTPException, status
from src.model.EventArrangmentForm import EventArrangmentForm

async def get_all_booked_events_service(
    db_session,
    user_id: UUID,
    limit: int,
    page: int,
    search: Optional[str],
    sort_by: str,
    sort_order: str,
) -> Tuple[list[EventArrangmentForm], int]:
    
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access!')

    query = select(EventArrangmentForm).where(EventArrangmentForm.userId == user_id)

    if search:
        query = query.where(EventArrangmentForm.eventType.ilike(f"%{search}%"))

    order_col = (
        EventArrangmentForm.budget if sort_by == 'budget' else EventArrangmentForm.submittedAt
    )
    query = query.order_by(desc(order_col) if sort_order == 'desc' else asc(order_col))

    offset = limit * (page - 1)
    paginated_q = query.limit(limit).offset(offset)
    count_q = select(func.count()).select_from(query.subquery())

    async with db_session.begin():
        try:
            result = await db_session.scalars(paginated_q)
            events = result.all()
            total = await db_session.scalar(count_q) or 0
            return events, total
        except SQLAlchemyError as e:
            await db_session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {e}",
            )
            