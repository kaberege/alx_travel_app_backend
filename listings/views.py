from django.shortcuts import get_object_or_404
from rest_framework import filters, status, views, viewsets
from rest_framework.response import Response
from .permissions import IsAuthenticatedIsOwnerOrReadOnlyListing, IsAuthenticatedIsOwnerBooking
from django.contrib.auth import get_user_model
from .serializers import BookingSerializer, ListingSerializer, PaymentSerializer
from .models import Booking, Listing
from django_filters.rest_framework import DjangoFilterBackend
from .pagination import StandardResultsSetPagination
import uuid, requests, os
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .models import Payment, Booking
from .serializers import PaymentSerializer
from .tasks import send_payment_confirmation_email, send_booking_confirmation_email
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

CHAPA_SECRET_KEY = os.environ.get('CHAPA_SECRET_KEY')

User = get_user_model()  # Custom user model

# Booking view
class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticatedIsOwnerBooking]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["property", "start_date", "end_date", "total_price", "status", "created_at"]
    search_fields = ["property", "start_date", "end_date", "total_price", "status", "created_at"]
    ordering_fields = ["property", "start_date", "end_date", "total_price", "status", "created_at"]
    ordering = ["property"]

    def get_queryset(self):
        # Short-circuit for Swagger schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()
            
        return Booking.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        booking = serializer.save(user=self.request.user)
        send_booking_confirmation_email.delay(
            booking.user.email,
            str(booking.booking_id)
        )

    @swagger_auto_schema(
        operation_summary="List user's bookings",
        operation_description="Retrieve a list of all bookings made by the authenticated user."
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Create a booking",
        operation_description="Create a new booking for a property. The booking will be associated with the authenticated user."
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Retrieve a booking",
        operation_description="Retrieve details of a specific booking made by the authenticated user."
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Update a booking",
        operation_description="Update all details of an existing booking. Only the booking owner can perform this action."
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Partially update a booking",
        operation_description="Update one or more fields of an existing booking. Only the booking owner can perform this action."
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Cancel a booking",
        operation_description="Delete (cancel) an existing booking. Only the booking owner can perform this action."
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

# Listing view
class ListingViewSet(viewsets.ModelViewSet):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer
    permission_classes = [IsAuthenticatedIsOwnerOrReadOnlyListing]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["name", "description", "location", "pricepernight", "created_at"]
    search_fields =  ["name", "description", "location", "pricepernight", "created_at"]
    ordering_fields =  ["name", "description", "location", "pricepernight", "created_at"]
    ordering = ["name"]

    def perform_create(self, serializer):
        serializer.save(host=self.request.user)

    @swagger_auto_schema(
        operation_summary="List all properties",
        operation_description="Retrieve a list of all available property listings."
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Create a property listing",
        operation_description="Create a new property listing. The listing will be associated with the authenticated user as the host."
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Retrieve a property",
        operation_description="Retrieve details of a specific property listing."
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Update a property listing",
        operation_description="Update all details of an existing property listing. Only the host (owner) can perform this action."
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Partially update a property",
        operation_description="Update one or more fields of an existing property listing. Only the host (owner) can perform this action."
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Delete a property",
        operation_description="Delete an existing property listing. Only the host (owner) can perform this action."
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

class InitiatePaymentView(views.APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Initiate a payment",
        operation_description="Initialize a payment for a specific booking. Returns a checkout URL and tx_ref.",
        responses={
            200: openapi.Response(
                description="Payment initialized successfully",
                examples={
                    "application/json": {
                        "checkout_url": "https://checkout.chapa.co/...",
                        "tx_ref": "booking-xxxx"
                    }
                }
            ),
            404: "Booking not found or not yours",
            400: "Failed to initialize payment"
        }
    )
    def post(self, request, booking_id=None):
        try:
            booking = Booking.objects.get(pk=booking_id, user=request.user)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found or not yours'}, status=status.HTTP_404_NOT_FOUND)

        tx_ref = f"booking-{uuid.uuid4()}"

        payload = {
            "amount": str(booking.total_price),
            "currency": "USD",
            "email": request.user.email,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "tx_ref": tx_ref,
            "callback_url": request.build_absolute_uri(f'/api/payments/verify/{tx_ref}/'),
            "return_url": "https://kaberege-portfolio.vercel.app/",
            "customization": {
                "title": "Booking Payment",
                "description": f"Payment for booking"
            }
        }

        headers = {
            "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        try:
            chapa_response = requests.post(
                "https://api.chapa.co/v1/transaction/initialize",
                json=payload, 
                headers=headers
            )
            data = chapa_response.json()
        except Exception as e:
            return Response({"error": f"Payment failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        if chapa_response.status_code == 200 and data.get('status') == 'success':
            try:
                payment = Payment.objects.create(
                    booking=booking,
                    amount=booking.total_price,
                    tx_ref=tx_ref
                )
                
                return Response({
                    "checkout_url": data['data']['checkout_url'],
                    "tx_ref": tx_ref
                })
            except Exception as e:
                return Response({"error": f"Failed to record payment in system: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
    
class VerifyPaymentView(views.APIView):
    @swagger_auto_schema(
        operation_summary="Verify payment",
        operation_description="Verify the status of a payment by tx_ref. Returns payment status and Chapa response.",
        manual_parameters=[
            openapi.Parameter("tx_ref", openapi.IN_PATH, description="Transaction reference to verify", type=openapi.TYPE_STRING)
        ],
        responses={
            200: openapi.Response(
                description="Payment verification result",
                examples={
                    "application/json": {
                        "status": "completed",
                        "chapa_response": {"status": "success", "data": {}}
                    }
                }
            ),
            404: "Payment not found",
            400: "Verification failed"
        }
    )    
    def get(self, request, tx_ref=None):
        # callback_url recive a GET request with a JSON payload
        callback_url_trx_ref = request.GET.get("trx_ref")
        callback_url_ref_id = request.GET.get("ref_id")
        callback_url_chapa_status = request.GET.get("status")

        try:
            payment = Payment.objects.get(tx_ref=tx_ref)
            
            if callback_url_ref_id and callback_url_trx_ref == tx_ref and callback_url_chapa_status == "success":
                payment.chapa_transaction_id = callback_url_ref_id 
                payment.save()

        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}"}
        try:
            response = requests.get(
                f"https://api.chapa.co/v1/transaction/verify/{tx_ref}",
                headers=headers
            ) 
            data = response.json()
        except Exception as e:
            return Response({"error": f"Failed to verify payment in system: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if data.get('status') == 'success':
            chapa_status = data['data']['status']
            payment.status = 'completed' if chapa_status == 'success' else 'failed'
            payment.save()

            if payment.status == 'completed':
                send_payment_confirmation_email.delay(
                    payment.booking.user.email,
                    str(payment.payment_id)
                )

            return Response({"status": payment.status, "chapa_response": data})
        else:
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
