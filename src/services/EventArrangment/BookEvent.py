from fastapi import HTTPException, logger, status
from fastapi.responses import JSONResponse
from jinja2 import TemplateNotFound
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession 
from src.model.EventArrangmentForm import EventArrangmentForm
from src.schemas.EventArrangment import BookEventFormSchema
from src.utils.MailSender import celery_send_mail
from src.utils.template_engine import templates


async def book_event_service(
    form: BookEventFormSchema,
    db_session:AsyncSession,
    user_name
):
    data = form.model_dump()
    event = EventArrangmentForm(**data)
    db_session.add(event)
    try:
        # 1) persist and commit first
        await db_session.flush()
        await db_session.commit()
        await db_session.refresh(event)
        
        
        #Sending mail task to celery
        try:
            # Email Subject & Body
            subject = f"🎉 Event Booked Successfully!"
            recipients = [event.email]
            html = templates.get_template("bookedeventtemplate.html").render(
                subject=subject,
                form_id=event.id,
                user_name=user_name
            )
            celery_send_mail.apply_async([recipients, subject, html])
        except TemplateNotFound as e:
            # handle or log template error without touching DB
            logger.error("Email template missing: %s", e)
        except Exception as e:
            # handle Celery dispatch issues
            logger.error("Failed to send confirmation email: %s", e)
        
        
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"message": "Success submitted!", "form_id": str(event.id)}
        )
    except SQLAlchemyError as e:
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"DB error while saving form: {e}",
        )
    except Exception:
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error while saving form."
        )