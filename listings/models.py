from django.db import models
import uuid
from django.contrib.auth import get_user_model

User = get_user_model()

class Amenity(models.Model):
    """Stores unique amenities like 'Pool', 'Wifi', 'Gym'"""
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "Amenities"

    def __str__(self):
        return self.name


class Listing(models.Model):
    property_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_properties')
    name = models.CharField(max_length=255)
    pricepernight = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.IntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.00)
    
    # Many Listings can have Many Amenities (and vice-versa)
    categories = models.ManyToManyField(Amenity, related_name="listings", blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class PropertyImage(models.Model):
    """
    The Image Gallery Table.
    Many images can point back to a single Listing.
    """
    image_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='images')
    image_url = models.CharField(max_length=500)
    
    # Flag to determine which image is the main dashboard thumbnail vs. detail gallery
    is_main = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.property.name} ({'Main' if self.is_main else 'Detail'})"

class PropertyAddress(models.Model):
    property = models.OneToOneField(Listing, on_delete=models.CASCADE, related_name='address')
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)


class PropertyOffers(models.Model):
    property = models.OneToOneField(Listing, on_delete=models.CASCADE, related_name='offers')
    bed = models.IntegerField()
    shower = models.IntegerField()
    occupants = models.CharField(max_length=50)


class PropertyDescription(models.Model):
    property = models.OneToOneField(Listing, on_delete=models.CASCADE, related_name='description')
    title = models.TextField()
    space = models.TextField(blank=True, null=True)
    offer = models.TextField(blank=True, null=True)
    host = models.TextField(blank=True, null=True)


class Booking(models.Model):
    STATUS_CHOICES = [('pending', 'Pending'), ('confirmed', 'Confirmed'), ('canceled', 'Canceled')]

    booking_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='bookings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    start_date = models.DateField()
    end_date = models.DateField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Booking by {self.user.email} for {self.property.name}"

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]

    payment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tx_ref = models.CharField(max_length=255, unique=True)
    chapa_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment for booking {self.booking.booking_id} - {self.status}"
