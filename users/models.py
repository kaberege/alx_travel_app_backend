import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

class CustomUserManager(BaseUserManager):
    def create_user(self, email, role, password=None, **other_fields):
        if not email:
            raise ValueError("Users must have an email address!")
        
        if not password:
            raise ValueError("Password is required!")
        
        user_email=self.normalize_email(email)
        user=self.model(email=user_email, role=role, **other_fields)
        user.set_password(password)
        user.save(using=self.db)
        return user
    
    def create_superuser(self, email, role, password=None, **other_fields):
        user = self.create_user(email, role, password=password, **other_fields)
        user.is_superuser=True
        user.is_staff=True
        user.is_active=True
        user.save(using=self.db)
        return user

class CustomUser(AbstractUser):
    ROLE_CHOICES = [('guest', 'Guest'), ('host', 'Host'), ('admin', 'Admin')]

    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(unique=False, max_length=50)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, blank=False, null=False)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['role']

    def __str__(self):
        return f'{self.email} A {self.role}'
