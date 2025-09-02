# ALX Travel App - Milestone 5: Background Jobs for Email Notifications

This milestone enhances the `alx_travel_app` project by adding **asynchronous email notifications** using **Celery** with **RabbitMQ** as the message broker.

The main feature added is sending **booking confirmation emails** in the background without blocking the main request-response cycle.

---

## Objectives

- Configure **Celery** with **RabbitMQ** as the message broker.
- Implement **asynchronous email notifications** for bookings.
- Ensure **non-blocking user experience** by offloading email sending to background tasks.
- Gain hands-on experience with Django’s **email backend**.

---

## Tech Stack

- **Django** (backend framework)
- **Django REST Framework** (API development)
- **Celery** (task queue for background processing)
- **RabbitMQ** (message broker)
- **SMTP Email Backend** (for sending emails)

---

## Key Feature: Email Notifications

- When a **new booking is created**, a **Celery task** is triggered.
- The task sends a **confirmation email** to the guest using Django’s email backend.
- The email task runs asynchronously in the background via RabbitMQ.

---

## Setup & Configuration

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables (`.env`)

```env
DEBUG=True
SECRET_KEY=your_secret_key
DATABASE_URL=mysql://user:password@localhost:3306/travelapp
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@example.com
EMAIL_HOST_PASSWORD=your_email_password
```

### 3. Run Migrations

```bash
python manage.py migrate
```

### 4. Start RabbitMQ

```bash
sudo systemctl start rabbitmq-server
```

### 5. Start Celery Worker

```bash
celery -A alx_travel_app worker --loglevel=info
```

### 6. Run Django Server

```bash
python manage.py runserver
```

---

## Workflow

1. **User creates a booking** via the API (`POST /bookings/`).
2. **BookingViewSet** triggers the **Celery task** using `.delay()`.
3. **Celery worker** picks up the task from RabbitMQ.
4. **Email is sent** to the user confirming the booking.
5. User receives a **non-blocking experience** — booking response is instant, email is handled in background.

---

## API Documentation

- Swagger UI: [`/swagger/`](http://localhost:8000/swagger/)
- ReDoc: [`/redoc/`](http://localhost:8000/redoc/)
