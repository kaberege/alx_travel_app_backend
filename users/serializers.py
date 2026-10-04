import logging
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import smart_str, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_decode

logger = logging.getLogger(__name__)
User = get_user_model()

# Serializer class for user registration
class RegisterUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "first_name", "last_name", "role"]

    # Override the creation method to handle user creation logic
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")

# Serializer class for updating user profile
class UpdateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(read_only=True)

    class Meta:
        model = User
        fields = "__all__"
    
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("password must have at least 8 charcters")

# Serializer class for user login
class LoginUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

# Serializer class for user logout
class LogoutUserSerializer(serializers.Serializer):
    refresh = serializers.CharField()
    
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)
    token = serializers.CharField()
    uidb64 = serializers.CharField()

    def validate(self, attrs):
        try:
            uid = smart_str(urlsafe_base64_decode(attrs['uidb64']))
            user = User.objects.get(pk=uid)
        except (DjangoUnicodeDecodeError, User.DoesNotExist) as exc:
            logger.warning(f"[Serializers] Password reset token validation failed: Invalid user/uidb64. Details: {str(exc)}")
            raise serializers.ValidationError({"error": "Invalid or expired token link."})

        if not PasswordResetTokenGenerator().check_token(user, attrs['token']):
            logger.warning(f"[Serializers] Password reset token check failed for user ID: {user.pk}")
            raise serializers.ValidationError({"error": "Invalid or expired token link."})
        
        logger.info(f"[Serializers] Password reset token successfully validated for user ID: {user.pk}")
        attrs['user'] = user
        return attrs