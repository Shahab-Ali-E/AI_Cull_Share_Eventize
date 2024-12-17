from fastapi import APIRouter, HTTPException, status, Depends
from dependencies.user import get_user
from dependencies.core import DBSessionDep
from model.EventArrangmentForm import EventArrangmentForm
from schemas.EventArrangment import BookEventFormSchema

router = APIRouter(
    prefix='/event_arrangment',
    tags=['Event Arrangment'],
)

@router.post('/book_event', status_code=status.HTTP_202_ACCEPTED)
async def book_event(form:BookEventFormSchema, db_session:DBSessionDep, user = Depends(get_user)):
    user_id  = user.get('id')

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Unauthorized access!')
    
    # submit the form
    try:
        event_form = EventArrangmentForm(**form.model_dump())
        db_session.add(event_form)
        await db_session.commit()
        await db_session.refresh(event_form)

        return {"message": "Form submitted successfully", "form_id": event_form.id}
    
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while saving the form: {str(e)}",
        )