import os
import uuid
import logging
import requests
from django.db import transaction, IntegrityError
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, views, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Booking, Listing, Payment, PropertyImage, Review
from .serializers import (
    BookingSerializer, ListingSerializer, PaymentSerializer,
    PropertyImageSerializer, ReviewSerializer
)
from .permissions import IsHostOrReadOnly, IsBookingOwnerOrHost, IsReviewAuthorOrReadOnly
from .pagination import StandardResultsSetPagination
from .tasks import send_payment_confirmation_email, send_booking_confirmation_email

logger = logging.getLogger(__name__)
CHAPA_SECRET_KEY = os.environ.get('CHAPA_SECRET_KEY')
User = get_user_model()

class BookingViewSet(viewsets.ModelViewSet):
    """ViewSet for managing guest bookings."""
    serializer_class = BookingSerializer
    permission_classes = [IsBookingOwnerOrHost]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["property", "start_date", "end_date", "status"]
    search_fields = ["property__name", "status"]
    ordering_fields = ["start_date", "created_at", "total_price"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Booking.objects.none()
        user = self.request.user
        if user.is_staff:
            return Booking.objects.all()
        # Guests see their own bookings; Hosts see bookings for their properties
        return Booking.objects.filter(user=user) | Booking.objects.filter(property__host=user)

    def perform_create(self, serializer):
        booking = serializer.save(user=self.request.user)

        logger.info(f"Booking {booking.booking_id} created by user {self.request.user.user_id}")

        send_booking_confirmation_email.delay(
            booking.user.email,
            str(booking.booking_id)
        )

    @swagger_auto_schema(
        operation_summary="List user/host bookings",
        operation_description="Retrieve a list of all bookings made by the authenticated user."
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Create a new property booking",
        operation_description="Create a new booking for a property. The booking will be associated with the authenticated user."
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Retrieve booking details",
        operation_description="Retrieve details of a specific booking made by the authenticated user."
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Update booking details",
        operation_description="Update all details of an existing booking. Only the booking owner can perform this action."
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Partially update booking details",
        operation_description="Update one or more fields of an existing booking. Only the booking owner can perform this action."
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_summary="Cancel/Delete a booking",
        operation_description="Delete (cancel) an existing booking. Only the booking owner can perform this action."
    )
    def destroy(self, request, *args, **kwargs):
        booking = self.get_object()
        logger.warning(f"Booking {booking.booking_id} was canceled by User {request.user.pk}")
        return super().destroy(request, *args, **kwargs)

class ListingViewSet(viewsets.ModelViewSet):
    """ViewSet for managing property listings and their assets."""
    queryset = Listing.objects.all().select_related('address', 'offers', 'description', 'host').prefetch_related('categories', 'images')
    serializer_class = ListingSerializer
    permission_classes = [IsHostOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["name", "price_per_night", "address__city", "address__country"]
    search_fields = ["name", "address__city", "address__country", "description__title"]
    ordering_fields = ["name", "price_per_night", "created_at"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        listing = serializer.save(host=self.request.user)
        logger.info(f"New listing '{listing.name}' ({listing.pk}) created by Host {self.request.user.pk}")

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

    # --- ACTION ENDPOINT FOR UPLOADING PROPERTY IMAGES ---
    # Target: POST /api/listings/{id}/upload_image/
    @swagger_auto_schema(
        operation_summary="Upload property gallery image",
        request_body=PropertyImageSerializer,
        responses={201: PropertyImageSerializer(), 400: "Invalid payload/file format", 403: "Not listing owner"}
    )
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser], url_path='upload_image')
    def upload_image(self, request, pk=None):
        listing = self.get_object()
        is_main_image = not listing.images.exists()
        
        if listing.host != request.user:
            return Response({"detail": "Only the host can add photos to this property."}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = PropertyImageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                locked_listing = Listing.objects.select_for_update().get(pk=listing.pk)
                is_first_image = not locked_listing.images.exists()
                is_main_input = str(request.data.get("is_main", "false")).lower() in ['true', '1']
                final_is_main = is_first_image or is_main_input

                if final_is_main:
                    locked_listing.images.filter(is_main=True).update(is_main=False)

                image_instance = serializer.save(property=locked_listing, is_main=final_is_main)
                logger.info(f"Uploaded image {image_instance.pk} for Listing {listing.pk}")
            return Response(PropertyImageSerializer(image_instance).data, status=status.HTTP_201_CREATED)    

        except Listing.DoesNotExist:
            return Response(
                {"detail": "Property no longer exists."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        except IntegrityError:
            return Response(
                {"detail": "A main image for this property was updated concurrently. Please try again."},
                status=status.HTTP_400_BAD_REQUEST
            )

        except (IOError, OSError) as e:
            logger.error(f"File storage write error for listing {listing.pk}: {str(e)}")

            return Response(
                {"detail": "Failed to store image file. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # Target: PATCH /api/listings/{id}/set_main_image/
    @swagger_auto_schema(
        operation_summary="Set main dashboard thumbnail",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['image_id'],
            properties={'image_id': openapi.Schema(type=openapi.TYPE_STRING, description="UUID of target image")}
        ),
        responses={200: "Main image updated", 404: "Image not found"}
    )
    @action(detail=True, methods=['patch'], url_path='set_main_image')
    def set_main_image(self, request, pk=None):
        listing = self.get_object()
        new_image_id = request.data.get('image_id')

        if not new_image_id:
            return Response(
                {"error": "image_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            # The atomic block ensures both database changes succeed, or both roll back
            with transaction.atomic():
                # Clear any existing main images for this listing
                listing.images.filter(is_main=True).update(is_main=False)

                # Get the target image and set it as the new main image
                # Using select_for_update() locks the row until the transaction finishes
                new_main_image = listing.images.select_for_update().get(
                    pk=new_image_id
                )
                new_main_image.is_main = True
                new_main_image.save()
        
            return Response({"detail": "Main dashboard thumbnail updated successfully."}, status=status.HTTP_200_OK)
        except PropertyImage.DoesNotExist:
            return Response({"error": "Image not found on this listing."}, status=status.HTTP_404_NOT_FOUND)

    # --- DELETE INDIVIDUAL GALLERY IMAGE ---
    # Target: DELETE /api/listings/{id}/delete_image/
    @swagger_auto_schema(
        operation_summary="Delete individual gallery image",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['image_id'],
            properties={'image_id': openapi.Schema(type=openapi.TYPE_STRING)}
        ),
        responses={200: "Deleted successfully", 400: "Cannot delete final or main image"}
    )
    @action(detail=True, methods=['delete'], url_path='delete_image')
    def delete_image(self, request, pk=None):
        listing = self.get_object()
        image_id = request.data.get('image_id')

        if not image_id:
            return Response(
                {"error": "image_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            target_image = listing.images.get(pk=image_id)
        except PropertyImage.DoesNotExist:
            return Response({"detail": "Image not found on this listing."}, status=status.HTTP_404_NOT_FOUND)
            
        # Block if they are trying to delete the absolute last image
        if listing.images.count() <= 1:
            return Response(
                {"detail": "A listing must have at least one image remaining."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Block if they delete the main image while other choices exist
        if target_image.is_main:
            return Response(
                {"detail": "Please assign a new main thumbnail before deleting this image."}, 
                status=status.HTTP_400_BAD_REQUEST
            )  

        # Delete from your storage file graph and MySQL table rows
        target_image.image.delete(save=False) # Removes file asset from disk/S3
        target_image.delete()
        logger.info(f"Image {image_id} removed from listing {listing.pk}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    # --- ACTION ENDPOINT FOR FETCHING/CREATING PROPERTY REVIEWS ---
    # Target: GET or POST /api/listings/{id}/reviews/
    @swagger_auto_schema(
        method='get',
        operation_summary="Fetch property reviews",
        responses={200: ReviewSerializer(many=True)}
    )
    @swagger_auto_schema(
        method='post',
        operation_summary="Submit a property review",
        request_body=ReviewSerializer,
        responses={201: ReviewSerializer(), 400: "Invalid input", 401: "Unauthorized"}
    )
    @action(detail=True, methods=['get', 'post'], url_path='reviews')
    def reviews(self, request, pk=None):
        listing = self.get_object()

        if request.method == 'GET':
            reviews = listing.property_reviews.all().select_related('user')
            serializer = ReviewSerializer(reviews, many=True)
            return Response(serializer.data)

        if request.method == 'POST':
            if not request.user.is_authenticated:
                return Response({"detail": "Authentication required to leave feedback."}, status=status.HTTP_401_UNAUTHORIZED)
            
            serializer = ReviewSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(user=request.user, property=listing)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class InitiatePaymentView(views.APIView):
    """Initiates transaction payment flow via Chapa API."""
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Initiate payment transaction",
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
            "callback_url": request.build_absolute_uri(f'/api/payments/verify/'),
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
            logger.error(f"Chapa Connection Error: {str(e)}")
            return Response({"error": f"Payment gateway initialization failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                logger.error(f"Failed to record Payment model row: {str(e)}")
                return Response({"error": f"Failed to record payment in system: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
    
class VerifyPaymentView(views.APIView):
    """Verifies payment transaction status with Chapa."""
    @swagger_auto_schema(
        operation_summary="Verify Chapa Payment Callback",
        operation_description="Callback handler for Chapa payment verification.",
        manual_parameters=[
            openapi.Parameter("trx_ref", openapi.IN_QUERY, description="Unique transaction reference", type=openapi.TYPE_STRING, required=True),
            openapi.Parameter("ref_id", openapi.IN_QUERY, description="Chapa tracking ID", type=openapi.TYPE_STRING, required=False),
            openapi.Parameter("status", openapi.IN_QUERY, description="Status sent by Chapa", type=openapi.TYPE_STRING, required=False),
        ],
        responses={
            200: openapi.Response(
                description="Payment verified successfully",
                examples={"application/json": {"status": "completed", "message": "Payment verified successfully."}}
            ),
            400: "Missing required parameters or payment failed",
            404: "Transaction record not found"
        }
    )
    def get(self, request):
        # callback_url recive a GET request with a JSON payload
        trx_ref = request.query_params.get('trx_ref') or request.data.get('trx_ref')
        ref_id = request.query_params.get('ref_id') or request.data.get('ref_id')
        cb_status = request.query_params.get('status') or request.data.get('status')

        if not trx_ref:
            return Response({'error': 'trx_ref is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.select_for_update().select_related('booking').get(tx_ref=trx_ref)
        except Payment.DoesNotExist:
            logger.error(f"Callback error: Payment with tx_ref '{trx_ref}' not found.")
            return Response({'error': 'Payment record not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        # Idempotency Check: Return immediately if already processed
        if payment.status in ['completed', 'failed']:
            return Response({
                'status': payment.status,
                'message': 'Transaction already processed.'
            }, status=status.HTTP_200_OK)

        chapa_url = f"https://api.chapa.co/v1/transaction/verify/{trx_ref}"
        headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}"}

        try:
            chapa_response = requests.get(chapa_url, headers=headers, timeout=10)
            res_data = chapa_response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Chapa API verification request failed: {str(e)}")
            return Response({'error': 'Failed to connect to gateway.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Confirm verification status from server-to-server check
        api_status = res_data.get('status')
        inner_data = res_data.get('data', {}) or {}
        tx_status = inner_data.get('status')

        is_verified = (chapa_response.status_code == 200) and (api_status == 'success') and (tx_status == 'success')

        with transaction.atomic():
            if is_verified:
                payment.status = 'completed'
                payment.booking.status = 'confirmed'
                payment.chapa_transaction_id = ref_id or inner_data.get('reference')
            else:
                payment.status = 'failed'
                payment.booking.status = 'canceled'

            payment.booking.save()
            payment.save()

        if is_verified:
            send_payment_confirmation_email.delay(
                payment.booking.user.email,
                str(payment.payment_id)
            )
            return Response({
                'status': 'completed',
                'message': 'Payment verified and booking confirmed.'
            }, status=status.HTTP_200_OK)

        return Response({
            'status': 'failed',
            'message': 'Payment verification failed.',
            'details': res_data
        }, status=status.HTTP_400_BAD_REQUEST)