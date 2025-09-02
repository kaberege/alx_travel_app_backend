from django.urls import path, include
from .views import RegisterUserView, LoginUserView, UpdateUserView, LogoutUserView, DeleteUserView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("register/", RegisterUserView.as_view(), name="register"),
    path("login/", LoginUserView.as_view(), name="login"),
    path("logout/", LogoutUserView.as_view(), name="logout"),
    path("update/", UpdateUserView.as_view(), name="update"),
    path("delete/", DeleteUserView.as_view(), name="delete"),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]