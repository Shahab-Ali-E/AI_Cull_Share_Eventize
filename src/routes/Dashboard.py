from fastapi import APIRouter, HTTPException,status,Depends
from fastapi.responses import JSONResponse
from config.settings import get_settings
from dependencies.user import get_user
from dependencies.core import DBSessionDep
from model.AssociationTable import SmartShareFoldersSecondaryUsersAssociation
from model.EventArrangmentForm import EventArrangmentForm
from model.ContactUs import ContactUs
from model.CullingFolders import CullingFolder
from model.SmartShareFolders import SmartShareFolder
from model.User import User
from schemas.ContactUs import ContactUsSchema
from utils.MailSender import celery_send_mail
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, select
from utils.template_engine import templates


router = APIRouter(
    prefix='/User',
    tags=['Dashboard'],
)

settings = get_settings()


@router.get('/get-analytics')
async def get_analytics(db_session:DBSessionDep, user = Depends(get_user)):
    user_id = user.get('id') #"user_2pn6uXJhoILeAubepXAoaluOQM2"

    # Base querie
    smart_share_base_query = select(SmartShareFolder.id, SmartShareFolder.name, SmartShareFolder.created_at).where(
        SmartShareFolder.user_id == user_id
    )
    
    # Count queries (batch execution)
    count_queries = {
        "total_smart_share_events":select(func.count()).select_from(smart_share_base_query.subquery()),
        "total_culling_workspaces":select(func.count()).select_from(select(CullingFolder).where(CullingFolder.user_id == user_id).subquery()),
        "total_booked_events":select(func.count()).select_from(select(EventArrangmentForm).where(EventArrangmentForm.userId == user_id).subquery()),
    }
    
    # Fetch all event and associated user data in one query using OUTER JOIN
    smart_share_event_with_access_query = select(   SmartShareFolder.id, 
                                                    SmartShareFolder.name, 
                                                    SmartShareFolder.created_at, 
                                                    SmartShareFoldersSecondaryUsersAssociation.user_id,
                                                    SmartShareFoldersSecondaryUsersAssociation.accessed_at,
                                                    User.first_name,
                                                    User.last_name,
                                                    User.email,
                                                ).outerjoin(
                                                    SmartShareFoldersSecondaryUsersAssociation,
                                                    SmartShareFoldersSecondaryUsersAssociation.smart_share_folder_id == SmartShareFolder.id
                                                ).outerjoin(
                                                    User,
                                                    SmartShareFoldersSecondaryUsersAssociation.user_id == User.id
                                                    
                                                ).where(
                                                    SmartShareFolder.user_id == user_id
                                                )
    
    async with db_session.begin():
        # Fetch all count result
        count_results = {key: await db_session.scalar(query) for key,query in count_queries.items()}
        
        # Fetch event and access data
        result_set = await db_session.execute(smart_share_event_with_access_query)
        rows = result_set.all()
        
        # Process results into a structured format
        event_list = []
        for row in rows:
            event_id, event_name, created_at, user_id, accessed_at, first_name, last_name, email, = row
            
            # Check if event_id already exists in event_list
            existing_event = next((event for event in event_list if event["event_id"] == event_id), None)
            
            if existing_event:
                if user_id:
                    existing_event["views"].append({"user_id":user_id, "first_name":first_name, "last_name":last_name, "email":email, "accessed_at":accessed_at})

            else:
                # Create a new event entry
                event_data = {
                    "event_id": event_id,
                    "event_name": event_name,
                    "created_at": created_at,
                    "views": [{"user_id":user_id, "first_name":first_name, "last_name":last_name, "email":email, "accessed_at":accessed_at}] if user_id else []
                }
                event_list.append(event_data)

        return {
            "smart_share_events": count_results["total_smart_share_events"],
            "culling_workspaces": count_results["total_culling_workspaces"],
            "booked_events": count_results["total_booked_events"],
            "user_event_access": event_list,
            "total_smart_culling_storage":settings.MAX_SMART_CULL_MODULE_STORAGE,
            "total_smart_culling_storage_used":user.get("total_culling_storage_used"),
            "total_smart_share_storage":settings.MAX_SMART_SHARE_MODULE_STORAGE,
            "total_smart_share_storage_used":user.get("total_image_share_storage_used")
        }

@router.post('/contact-us')
async def contact_us(
    contact_us: ContactUsSchema,
    db_session:DBSessionDep
):
    try:
        # Save the contact form data to the database
        contact_us_dict = contact_us.model_dump()
        new_complaint = ContactUs(**contact_us_dict)
        db_session.add(new_complaint)
        await db_session.commit()

    
        # Send an email to the user using Celery
        subject = "Thank you for contacting us!"
        recipients = [contact_us.email]
        body = templates.get_template("ContactUs.html").render(
            user_name=f"{contact_us.first_name} {contact_us.last_name}",
            user_message=contact_us.description
        )

        celery_send_mail.apply_async(args=[recipients, subject, body])

    except SQLAlchemyError as e:
        # Rollback the transaction in case of a database error
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

    except Exception as e:
        # Rollback the transaction in case of any other error
        await db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": "Your message has been sent. We will contact you soon."
        }
    )

