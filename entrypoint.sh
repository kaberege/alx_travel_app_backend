#!/bin/bash

python manage.py collectstatic --no-input
echo "Running migrations..."
python manage.py migrate
python manage.py auto_createsuperuser
echo "Starting server..."
python manage.py runserver 0.0.0.0:8000