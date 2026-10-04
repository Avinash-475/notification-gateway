import os
from celery import Celery
from database import SessionLocal
from models import NotificationRequest as NotificationDB
import time
import smtplib
from email.mime.text import MIMEText

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

MAILTRAP_HOST = "sandbox.smtp.mailtrap.io"
MAILTRAP_PORT = 2525
MAILTRAP_USERNAME = "your_username_here"
MAILTRAP_PASSWORD = "your_password_here"

celery_app = Celery(
    "notification_gateway",
    broker=REDIS_URL,
    backend=REDIS_URL
)

@celery_app.task
def dummy_task(x, y):
    return x + y


@celery_app.task(
    bind=True,
    max_retries=3
)
@celery_app.task(bind=True, max_retries=3)
def send_notification_task(self, notification_id: int):
    db = SessionLocal()
    try:
        notification = db.query(NotificationDB).filter(
            NotificationDB.id == notification_id
        ).first()

        if not notification:
            return f"Notification {notification_id} not found"

    
        if notification.status == "sent":
            return f"Notification {notification_id} already sent, skipping"

        try:
            if notification.content == "FORCE_FAIL":
                raise Exception("Deliberately forced failure for testing")

            if notification.type == "email":
                msg = MIMEText(notification.content)
                msg["Subject"] = "Notification from Notification Gateway"
                msg["From"] = "noreply@notificationgateway.com"
                msg["To"] = notification.recipient

                with smtplib.SMTP(MAILTRAP_HOST, MAILTRAP_PORT, timeout=10) as server:
                    server.login(MAILTRAP_USERNAME, MAILTRAP_PASSWORD)
                    server.send_message(msg)
            else:
                print(f"Mock sending {notification.type} to {notification.recipient}: {notification.content}")

            notification.status = "sent"
            db.commit()
            return f"Notification {notification_id} sent successfully"

        except Exception as exc:
            notification.retry_count = self.request.retries + 1

            if self.request.retries >= self.max_retries:
                notification.status = "failed"
                db.commit()
                return f"Notification {notification_id} permanently failed after {self.max_retries} retries"

            db.commit()
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    finally:
        db.close()