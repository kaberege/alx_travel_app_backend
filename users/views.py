from django.conf import settings
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from .serializers import RegisterUserSerializer, UpdateUserSerializer, LoginUserSerializer, LogoutUserSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer
from .tasks import send_password_reset_email_task
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
import logging

logger = logging.getLogger(__name__)

User = get_user_model()  # Custom user model

# Handle user registration logic
class RegisterUserView(views.APIView):
    @swagger_auto_schema(
        operation_summary="Register a user",
        operation_description="Register a new user.",
        request_body=RegisterUserSerializer,
        responses={
            201: openapi.Response('User registered successfully'),
            400: 'Validation error'
        }
    )
    def post(self, request):
        # Initialize the serializer with the provided request data
        serializer = RegisterUserSerializer(data=request.data)
        
        # Check if the data is valid according to the serializer's validation logic
        if serializer.is_valid():
            email = serializer.validated_data['email']
            # Save the new user to the database if the data is valid
            serializer.save()

            logger.info(f"[Views] User registration successful for email: {email}")

            # Return a success message with HTTP status 201 (Created)
            return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)

        logger.warning(f"[Views] Registration failed for email: {email}. Errors: {serializer.errors}")

        # If the serializer data is invalid, return the validation errors with HTTP status 400 (Bad Request)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Handle user login logic
class LoginUserView(views.APIView):
    @swagger_auto_schema(
        operation_summary="User Login",
        operation_description="Login a user and get JWT tokens.",
        request_body=LoginUserSerializer,
        responses={
            200: openapi.Response('JWT token returned'),
            400: 'Invalid email or password'
        }
    )
    def post(self, request):
        # Initialize the login serializer with the provided request data
        serializer = LoginUserSerializer(data=request.data)

        # Check for data validation
        if not serializer.is_valid():
            logger.warning(f"[Views] Login failed: Invalid data format for user: {request.data.get('email')}")

            return Response({"error": "Invalid email or password"}, status=status.HTTP_400_BAD_REQUEST)
    
        user_email = serializer.validated_data['email']
        user_password = serializer.validated_data['password']
    
        # Attempt to authenticate the user
        try:
            user = User.objects.get(email=user_email)
            user_data = {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
            }

            if user.check_password(user_password):
                # Create JWT token
                refresh = RefreshToken.for_user(user)
                access_token = refresh.access_token

                logger.info(f"User logged in successfully: {user_email}")

                # Return the tokens
                return Response({'user_data':user_data,'access': str(access_token),'refresh': str(refresh)})
            
            logger.warning(f"[Views] Login failed: Incorrect password for user: {user_email}")
            return Response({"error": "Invalid password!"}, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            logger.warning(f"[Views] Login failed: User does not exist: {user_email}")

            return Response({"error": "Invalid email!"}, status=status.HTTP_400_BAD_REQUEST)

# Handle user update logic
class UpdateUserView(views.APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Update User",
        operation_description="Update current authenticated user.",
        request_body=UpdateUserSerializer,
        responses={
            200: openapi.Response('User updated successfully'),
            400: 'Validation error'
        }
    )
    def put(self, request):
        logger.info(f"[Views] Profile update attempt for user ID: {request.user.pk}")
        instance = request.user
        serializer = UpdateUserSerializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()   # Update the user
            logger.info(f"[Views] Profile updated successfully for user ID: {request.user.pk}")
            return Response(serializer.data, status=status.HTTP_200_OK)

        logger.warning(f"[Views] Profile update failed for user ID: {request.user.pk}. Errors: {serializer.errors}")

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# This view uses the refresh token to blacklist it on logout
class LogoutUserView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_summary="Logout User",
        operation_description="Logout a user by blacklisting their refresh token.",
        request_body=LogoutUserSerializer,
        responses={
            205: openapi.Response('Successfully logged out'),
            400: 'Invalid or already blacklisted token'
        }
    )
    def post(self, request):
        logger.info(f"[Views] Logout requested by user ID: {request.user.pk}")
        serializer = LogoutUserSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"[Views] Logout failed: Invalid request body for user ID: {request.user.pk}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
       
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            logger.info(f"[Views] User logged out successfully: {request.user.email}")
            return Response({"message": "Successfully logged out"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as error:
            logger.error(f"[Views] Logout failure for user ID: {request.user.pk}. Exception: {str(error)}", exc_info=True)
            return Response({"error": "Invalid token or already blacklisted"}, status=status.HTTP_400_BAD_REQUEST)
        
# Handle user delete logic
class DeleteUserView(views.APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_summary="Delete User",
        operation_description="Delete the current user.",
        responses={
            204: openapi.Response('User deleted'),
            400: 'Error deleting user'
        }
    )
    def delete(self, request):
        user_id = request.user.pk
        instance = request.user
        instance.delete()  # Delete the user

        logger.info(f"[Views] Account deleted successfully for user ID: {user_id}")
        
        return Response({"message": "User has been deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

class PasswordResetRequestView(views.APIView):
    @swagger_auto_schema(
        operation_summary="Request Password Reset",
        request_body=PasswordResetRequestSerializer,
        responses={200: openapi.Response("Reset email sent if account exists")}
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        logger.info(f"[Views] Password reset request received for email: {email}")

        try:
            user = User.objects.get(email=email)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = PasswordResetTokenGenerator().make_token(user)
            
            reset_url = f"{settings.FRONTEND_URL.rstrip("/")}/reset-password/{uidb64}/{token}/"
            
            # Trigger Celery Task
            send_password_reset_email_task.delay(user.email, reset_url)
            logger.info(f"[Views] Password reset link dispatched via Celery for user ID: {user.pk}")
        except User.DoesNotExist:
            logger.info(f"[Views] Password reset requested for non-existent email: {email}. Ignored for security.")

        return Response(
            {"message": "If an account with this email exists, a password reset link has been sent."},
            status=status.HTTP_200_OK
        )

class PasswordResetConfirmView(views.APIView):
    @swagger_auto_schema(
        operation_summary="Confirm Password Reset",
        request_body=PasswordResetConfirmSerializer,
        responses={200: openapi.Response("Password reset successful")}
    )
    def post(self, request):
        logger.info("[Views] Password reset confirmation request received.")
        serializer = PasswordResetConfirmSerializer(data=request.data)

        if not serializer.is_valid():
            logger.warning(f"[Views] Password reset confirmation failed validation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user = serializer.validated_data['user']
        password = serializer.validated_data['password']
        
        user.set_password(password)
        user.save()
        logger.info(f"[Views] Password updated successfully for user ID: {user.pk}")

        return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)

class UpgradeToHostView(views.APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Upgrade user role to Host",
        responses={200: "Successfully upgraded to host", 400: "Already a host"}
    )
    def post(self, request):
        user = request.user
        
        if user.role == 'host':
            return Response({"detail": "You are already registered as a host."}, status=status.HTTP_400_BAD_REQUEST)
        
        user.role = 'host'
        user.save()
        
        logger.info(f"[Views] User ID {user.pk} successfully upgraded their role to Host.")
        return Response({"detail": "Successfully upgraded to host account.", "role": user.role}, status=status.HTTP_200_OK)