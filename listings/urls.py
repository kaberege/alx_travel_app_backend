from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BookingViewSet, ListingViewSet, InitiatePaymentView, VerifyPaymentView

router = DefaultRouter()
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'listings', ListingViewSet, basename='listing')

urlpatterns = [
    path('', include(router.urls)),
    path('payments/<str:booking_id>/initiate/', InitiatePaymentView.as_view(), name="initiate"),
    path('payments/verify/<str:tx_ref>/', VerifyPaymentView.as_view(), name="verify")
]
