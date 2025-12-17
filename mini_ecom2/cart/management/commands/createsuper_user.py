from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

class Command(BaseCommand):
    help = 'Create a superuser if none exists'

    def handle(self, *args, **options):
        User = get_user_model()
        email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
        username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD')
        
        if not password:
            self.stdout.write(self.style.ERROR('DJANGO_SUPERUSER_PASSWORD not set'))
            return
            
        if not User.objects.filter(email=email).exists():
            User.objects.create_superuser(email=email, username=username, password=password)
            self.stdout.write(self.style.SUCCESS(f'Superuser {email} created!'))
        else:
            self.stdout.write(self.style.WARNING(f'User {email} already exists'))