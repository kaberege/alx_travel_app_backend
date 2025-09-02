from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Payment, Booking


@shared_task
def send_payment_confirmation_email(user_email, payment_id):
    """
    Sends a confirmation email to the user after a successful payment (HTML + plain fallback).
    """
    try:
        payment = Payment.objects.get(payment_id=payment_id)
    except Payment.DoesNotExist:
        return f"Payment with ID {payment_id} not found"

    subject = "Payment Confirmation"

    # Plain text fallback
    message = (
        f"Hello {payment.booking.user.first_name},\n\n"
        f"Your payment for booking {payment.booking.booking_id} has been successfully processed.\n"
        f"Amount Paid: {payment.amount} USD.\n"
        f"Transaction Reference: {payment.tx_ref}.\n"
        f"Chapa Transaction ID: {payment.chapa_transaction_id}.\n\n"
        "Thank you for your payment!\n\n"
        "Best regards,\n"
        "Your Booking Team"
    )

    # HTML version
    html_message = f"""
    <html>
        <body>
            <h2 style="color:#2E86C1;">Payment Confirmation</h2>
            <p>Hello <strong>{payment.booking.user.first_name}</strong>,</p>
            <p>Your payment for booking <strong>{payment.booking.booking_id}</strong> has been successfully processed.</p>
            <ul>
                <li><b>Amount Paid:</b> {payment.amount} USD</li>
                <li><b>Transaction Reference:</b> {payment.tx_ref}</li>
                <li><b>Chapa Transaction ID:</b> {payment.chapa_transaction_id}</li>
            </ul>
            <p>Thank you for your payment!</p>
            <p>Best regards,<br>Your Booking Team</p>
        </body>
    </html>
    """

    send_mail(
        subject,
        message,  # plain text fallback
        settings.DEFAULT_FROM_EMAIL,
        [user_email],
        fail_silently=False,
        html_message=html_message  # HTML email
    )

    return f"Confirmation email sent to {user_email}"


@shared_task
def send_booking_confirmation_email(user_email, booking_id):
    """
    Sends a booking confirmation email (HTML + plain fallback).
    """
    subject = "Booking Confirmation"

    # Plain text fallback
    message = f"Your booking with ID {booking_id} has been successfully created!"

    # HTML version
    html_message = f"""
    <html>
        <body>
            <h2 style="color:#27AE60;">Booking Confirmation</h2>
            <p>Your booking with ID <strong>{booking_id}</strong> has been successfully created!</p>
            <p>We look forward to serving you.</p>
            <p>Best regards,<br>Your Booking Team</p>
        </body>
    </html>
    """

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user_email],
        fail_silently=False,
        html_message=html_message  # HTML email
    )

    return f"Confirmation email sent to {user_email} for booking {booking_id}"
