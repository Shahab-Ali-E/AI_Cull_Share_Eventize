from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from Celery.utils import create_celery
from config.settings import get_settings
from asgiref.sync import async_to_sync

settings = get_settings()

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,  # Your email address
    MAIL_PASSWORD=settings.MAIL_PASSWORD,     # Your email password
    MAIL_FROM=settings.MAIL_FROM,      # Sender email
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_PORT=587,                           # SMTP port (587 for TLS)
    MAIL_SERVER=settings.MAIL_SERVER,          # SMTP server (e.g., smtp.gmail.com)
    MAIL_STARTTLS=True,                      # Use TLS
    MAIL_SSL_TLS=False,                      # Disable SSL
    USE_CREDENTIALS=True,                    # Use credentials
    VALIDATE_CERTS=True                      # Validate certificates
)
celery = create_celery()
FastApiMail = FastMail(config=conf)

def create_message(
    subject: str,
    recipients: list[str],
    body: str,
):
    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=body,
        subtype=MessageType.html,
    )
    
    return message


# celery task for sending mails
@celery.task(name='celery_send_mail', bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries':5}, queue='email')
def celery_send_mail(self, recipients: list[str], subject:str, body:str):
    message = create_message(recipients=recipients, subject=subject, body=body)

    async_to_sync(FastApiMail.send_message)(message)
    print("Email sent")