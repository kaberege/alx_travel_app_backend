from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def send_password_reset_email_task(email, reset_url):
    subject = "Password Reset Request"
    message = f"Hello,\n\nUse the link below to reset your password:\n{reset_url}\n\nIf you did not request this, please ignore this email."
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )