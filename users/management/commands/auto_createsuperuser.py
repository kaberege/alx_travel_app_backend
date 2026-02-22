from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
import os

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates a superuser if one does not already exist using environment variables.'

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        # Validation: Ensure variables are present
        if not email or not password:
            raise CommandError(
                "DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD must be set in environment."
            )

        # Logic: Check existence and create
        if not User.objects.filter(email=email).exists():
            User.objects.create_superuser(
                email=email,
                password=password,
                role="admin"
            )
            
            self.stdout.write(self.style.SUCCESS(f'Successfully created superuser: {email}'))
        else:
            self.stdout.write(self.style.WARNING(f'Superuser {email} already exists.'))