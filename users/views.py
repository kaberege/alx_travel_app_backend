from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from .serializers import RegisterUserSerializer, UpdateUserSerializer, LoginUserSerializer, LogoutUserSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

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
            # Save the new user to the database if the data is valid
            serializer.save()
            
            # Return a success message with HTTP status 201 (Created)
            return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)
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
                # Return the tokens
                return Response({'user_data':user_data,'access': str(access_token),'refresh': str(refresh)})
            return Response({"error": "Invalid password!"}, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
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
        instance = request.user
        serializer = UpdateUserSerializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()   # Update the user
            return Response(serializer.data, status=status.HTTP_200_OK)
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
        serializer = LogoutUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Successfully logged out"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as error:
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
        instance = request.user
        instance.delete()  # Delete the user
        return Response({"message": "User has been deleted successfully."}, status=status.HTTP_204_NO_CONTENT)