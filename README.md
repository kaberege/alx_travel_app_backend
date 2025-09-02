# ALX Travel App

A full-stack **travel booking platform** built with **Django & Django REST Framework (DRF)**.
The app allows users to browse property listings, make bookings, process payments via **Chapa**, and receive **asynchronous email notifications** powered by **Celery** and **RabbitMQ**.

---

## Features

- **JWT Authentication** (via `djangorestframework-simplejwt`)
- **Property Listings** (CRUD for hosts)
- **Bookings** (users can book properties, cancel, manage reservations)
- **Payments with Chapa API** (initiate & verify payments)
- **Asynchronous Email Notifications**

  - Booking confirmation emails
  - Payment confirmation emails

- **Interactive API docs** via **Swagger** & **ReDoc**
- **CORS enabled** for frontend integration
- Secure settings with **environment variables**

---

## Tech Stack

- **Backend**: Django 5, Django REST Framework
- **Auth**: SimpleJWT
- **Task Queue**: Celery
- **Broker**: RabbitMQ
- **Database**: MySQL
- **Email**: SMTP (Gmail)
- **Payments**: Chapa API
- **Docs**: drf-yasg (Swagger, ReDoc)
- **Hosting**: PythonAnywhere (for production)

---

## Setup & Installation

### 1. Clone Repo

```bash
git clone https://github.com/kaberege/alx_travel_app_backend.git
cd alx_travel_app_backend
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Variables

Create a `.env` file for **local development**:

```env
DEBUG=True
SECRET_KEY=your_secret_key

# Database
DATABASE_NAME=travelapp
DATABASE_USER=root
DATABASE_PASSWORD=yourpassword
DATABASE_HOST=127.0.0.1
DATABASE_PORT=3306

# Email
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=ALX Travel <your_email@gmail.com>

# Payments
CHAPA_SECRET_KEY=your_chapa_secret_key
```

For **PythonAnywhere deployment**, set these in your **WSGI config file** using `os.environ[...]`.

### 5. Run Migrations

```bash
python manage.py migrate
```

### 6. Create Superuser

```bash
python manage.py createsuperuser
```

### 7. Run Development Server

```bash
python manage.py runserver
```

---

## Background Jobs (Celery + RabbitMQ)

1. Start RabbitMQ (locally):

```bash
sudo systemctl start rabbitmq-server
```

2. Start Celery worker:

```bash
celery -A alx_travel_app_backend worker --loglevel=info
```

3. Now booking & payment confirmation emails will be sent **asynchronously** 🎉

---

## API Documentation

- Swagger UI → `/swagger/`
- ReDoc → `/redoc/`

---

## Email Notifications

- **Booking Confirmation Email** → sent when a new booking is created.
- **Payment Confirmation Email** → sent when payment is verified via Chapa.
- Uses **Django SMTP backend** with HTML + plain text fallback.

---

## API Highlights

- **Listings**:

  - `GET /api/listings/` → List all properties
  - `POST /api/listings/` → Create property (host only)

- **Bookings**:

  - `GET /api/bookings/` → User’s bookings
  - `POST /api/bookings/` → Create booking

- **Payments**:

  - `POST /api/payments/initiate/{booking_id}/` → Start payment
  - `GET /api/payments/verify/{tx_ref}/` → Verify payment
