from django.shortcuts import get_object_or_404
from rest_framework import filters, status, views, viewsets
from rest_framework.response import Response
from .permissions import IsAuthenticatedIsOwnerOrReadOnlyListing, IsAuthenticatedIsOwnerBooking
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from .serializers import BookingSerializer, ListingSerializer, PaymentSerializer, PropertyImageSerializer, ReviewSerializer 
from .models import Booking, Listing
from django_filters.rest_framework import DjangoFilterBackend
from .pagination import StandardResultsSetPagination
import uuid, requests, os
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Payment, Booking, PropertyImage
from .serializers import PaymentSerializer
from .tasks import send_payment_confirmation_email, send_booking_confirmation_email
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging

logger = logging.getLogger(__name__)

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

        logger.info(f"Booking {booking.booking_id} created by user {self.request.user.user_id}")

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
    # Performance optimization: prefetch single image layout along with one-to-one relations
    queryset = Listing.objects.all().select_related('address', 'offers', 'description', 'host').prefetch_related('categories', 'images')
    serializer_class = ListingSerializer
    permission_classes = [IsAuthenticatedIsOwnerOrReadOnlyListing]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["name", "pricepernight", "address__city", "address__country"]
    search_fields = ["name", "address__city", "address__country", "description__title"]
    ordering_fields = ["name", "pricepernight", "created_at"]
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

    # --- ACTION ENDPOINT FOR UPLOADING PROPERTY IMAGES ---
    # Target: POST /api/listings/{id}/upload_image/
    @swagger_auto_schema(operation_summary="Upload property gallery image")
    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser], url_path='upload_image')
    def upload_image(self, request, pk=None):
        listing = self.get_object()
        is_main_image = not listing.images.exist()
        
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

                serializer.save(property=locked_listing, is_main=final_is_main)

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
            logger.error(f"Image storage upload failed for listing {listing.pk}: {str(e)}")

            return Response(
                {"detail": "Failed to store image file. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({"detail": "Image uploaded successfully."}, status=status.HTTP_201_CREATED)    

    # Target: PATCH /api/listings/{id}/set_main_image/
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

    # --- ACTION ENDPOINT FOR FETCHING/CREATING PROPERTY REVIEWS ---
    # Target: GET or POST /api/listings/{id}/reviews/
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
