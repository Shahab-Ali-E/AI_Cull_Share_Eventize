# from typing import List, Optional
# from uuid import UUID
# from fastapi import APIRouter, HTTPException, status, Depends, Query
# from fastapi.responses import JSONResponse
# from sqlalchemy import asc, desc, func
# from dependencies.user import get_user
# from dependencies.core import DBSessionDep
# from model.EventArrangmentForm import EventArrangmentForm
# from schemas.EventArrangment import BookEventFormSchema, GetEventResponse, GetMultipleEventsResponse
# from sqlalchemy.exc import SQLAlchemyError
# from sqlalchemy.future import select

# router = APIRouter(
#     prefix='/event_arrangment',
#     tags=['Event Arrangment'],
# )


# @router.get('/all_booked_events', response_model=GetMultipleEventsResponse)
# async def get_all_booked_events(
#     db_session:DBSessionDep,
#     limit:int = Query(default=10, ge=1, le=100, description="Number of events on per page"),
#     page:int = Query(default=1, ge=1, description="Page number (starting from 1)"),
#     search:Optional[str] = Query(default=None, description="For searching events"),
#     sort_by:Optional[str] = Query(default="submittedAt", description="For sorting events by submittedAt, budget"),
#     sort_order:Optional[str] = Query(default="asc", description="For sorting events in ascending or descending order"),
#     user = Depends(get_user) 
# ):
#     user_id  = user.get('id')

#     if not user_id:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access!')
    
#     # Base query
#     query = select(EventArrangmentForm).where(EventArrangmentForm.userId == user_id)
    
#     # Apply search filter if provided
#     if search:
#         query = query.where(EventArrangmentForm.eventType.ilike(f"%{search}%"))
    
#     # sorting logic
#     if sort_by == "budget":
#         order_by_column = EventArrangmentForm.budget
#     else:
#         order_by_column = EventArrangmentForm.submittedAt
    
#     # sorting direction
#     query = query.order_by(desc(order_by_column) if sort_order=="desc" else asc(order_by_column))
    
#     # Apply pagination
#     offset_value = limit * (page-1) #records wants to skip
#     pagination_query = query.limit(limit).offset(offset_value)
    
#     # count queru
#     count_query = select(func.count()).select_from(query.subquery())
    
#     async with db_session.begin():
#         try:
#             # Execute paginated query
#             paginated_result = await db_session.scalars(pagination_query)
#             events = paginated_result.all()
            
#             # total count query
#             total_count_result = await db_session.scalar(count_query)
#             total_count = total_count_result or 0

#             return {
#                 "events":events,
#                 "total_count":total_count               
#             }

            
#         except SQLAlchemyError as e:
#             await db_session.rollback()
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail=f"Database error occurred: {str(e)}",
#             )
        
#         except Exception as e:
#             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# @router.get('/booked_event_by_id/{event_id}', response_model=GetEventResponse)
# async def get_booked_event_by_id(event_id:UUID, db_session:DBSessionDep, user = Depends(get_user)):
    
#     user_id = user.get('id') #"user_2pqOmYikrXY1pWefuBuqzRGm3vA"
#     if not user_id:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access!')

#     async with db_session.begin():
#         try:
#             # Query to get the folder by ID and user ID
#             event = await db_session.scalar(
#                 select(EventArrangmentForm).where(
#                     EventArrangmentForm.id == event_id,
#                     EventArrangmentForm.userId == user_id,
#                 )
#             )

#             # Check if event exists
#             if event is None:
#                 return JSONResponse(
#                     status_code=status.HTTP_404_NOT_FOUND,
#                     content=f'Event with id {event_id} not found!'
#                 )

#             return event
            
#         except SQLAlchemyError as e:
#             await db_session.rollback()
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail=f"Database error occurred: {str(e)}",
#             )

#         except HTTPException as e:
#             raise HTTPException(status_code=e.status_code, detail=str(e))
        
    

# @router.post('/book_event')
# async def book_event(form: BookEventFormSchema, db_session: DBSessionDep, user=Depends(get_user)):
#     user_id = user.get('id')

#     if not user_id:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access!')
    
#     event_form_dict = form.model_dump()
#     print("Received Form Data:", event_form_dict)  
#     print()
#     print()
#     print()
#     print()
    
#     # Submit the form
#     try:
#         # Create the event form object
#         event_form = EventArrangmentForm(**event_form_dict) 
        
#         # Add the form to the session
#         db_session.add(event_form)
        
#         # Flush the session to assign an ID to the event_form object
#         await db_session.flush()
        
#         # Commit the transaction
#         await db_session.commit()
        
#         # Refresh the event_form object to get the latest data from the database
#         await db_session.refresh(event_form)

#         # Return success response
#         return JSONResponse(
#             status_code=status.HTTP_202_ACCEPTED,
#             content={
#                 "message": "Success submitted!",
#                 "form_id": str(event_form.id)  # Convert UUID to string for JSON serialization
#             }
#         )
    
#     except SQLAlchemyError as e:
#         # Rollback the transaction in case of a database error
#         await db_session.rollback()
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"A database error occurred while saving the form. {str(e)}",
#         )
    
#     except Exception as e:
#         # Rollback the transaction in case of an unexpected error
#         await db_session.rollback()
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="An unexpected error occurred while saving the form.",
#         )

from fastapi import APIRouter, Depends, HTTPException, Query, status
from dependencies.user import get_user
from dependencies.core import DBSessionDep
from schemas.EventArrangment import (
    BookEventFormSchema,
    GetEventResponse,
    GetMultipleEventsResponse,
)
from services.EventArrangment.getAllBookedEvents import get_all_booked_events_service
from services.EventArrangment.getBookedEventById import get_booked_event_by_id_service
from services.EventArrangment.BookEvent import book_event_service

router = APIRouter(prefix='/event_arrangment', tags=['Event Arrangment'])

@router.get('/all_booked_events', response_model=GetMultipleEventsResponse)
async def get_all_booked_events(
    db_session: DBSessionDep,
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
    search: str | None = None,
    sort_by: str = 'submittedAt',
    sort_order: str = 'asc',
    user = Depends(get_user),
):
    user_id = user.get('id')
    events, total_count = await get_all_booked_events_service(
        db_session, user_id, limit, page, search, sort_by, sort_order
    )
    return {"events": events, "total_count": total_count}

@router.get('/booked_event_by_id/{event_id}', response_model=GetEventResponse)
async def get_booked_event_by_id(
    event_id, db_session: DBSessionDep, user = Depends(get_user)
):
    user_id = user.get('id')
    return await get_booked_event_by_id_service(db_session, event_id, user_id)

@router.post('/book_event')
async def book_event(
    form: BookEventFormSchema,
    db_session: DBSessionDep,
    user = Depends(get_user)
):
    user_id = user.get('id')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access!')

    return await book_event_service(form, db_session, user.get('username'))
