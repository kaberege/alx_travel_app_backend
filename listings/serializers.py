import inflect
from datetime import date
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Listing, PropertyAddress, PropertyOffer, PropertyDescription, 
    Amenity, PropertyImage, Review, Booking, Payment
)

User = get_user_model()
p = inflect.engine()

class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = '__all__'

class PropertyImageSerializer(serializers.ModelSerializer):
    property = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = PropertyImage
        fields = '__all__'

class PropertyAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyAddress
        fields = ['state', 'city', 'country']

class PropertyOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyOffer
        fields = ['bed', 'shower', 'occupants']

class PropertyDescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyDescription
        fields = ['title', 'space', 'offer', 'host']

class ReviewSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    property = serializers.PrimaryKeyRelatedField(queryset=Listing.objects.all())
    created_at = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S', read_only=True)

    class Meta:
        model = Review
        fields = '__all__'

class BookingSerializer(serializers.ModelSerializer):
    property = serializers.PrimaryKeyRelatedField(queryset=Listing.objects.all())
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    start_date = serializers.DateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    end_date = serializers.DateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    created_at = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S', read_only=True)

    class Meta:
        model = Booking
        fields = '__all__'

   def validate(self, data):
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        target_property = data.get('property')

        if start_date < date.today():
            raise serializers.ValidationError({"start_date": "Start date cannot be in the past!"})

        if end_date <= start_date:
            raise serializers.ValidationError({"end_date": "End date must be strictly after start date!"})

        # --- Overlapping Booking Safeguard ---
        overlapping_bookings = Booking.objects.filter(
            property=target_property,
            status__in=['pending', 'confirmed'],
            start_date__lt=end_date,
            end_date__gt=start_date
        )

        # Exclude current booking instance if updating
        if self.instance:
            overlapping_bookings = overlapping_bookings.exclude(pk=self.instance.pk)

        if overlapping_bookings.exists():
            raise serializers.ValidationError({"non_field_errors": "This property is already reserved for the selected dates."})

        return data

class ListingSerializer(serializers.ModelSerializer):
    host = serializers.PrimaryKeyRelatedField(read_only=True)
    address = PropertyAddressSerializer()
    offers = PropertyOfferSerializer()
    description = PropertyDescriptionSerializer()
    category = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name", source="categories")
    categories_input = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    images = PropertyImageSerializer(many=True, read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    bookings = BookingSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S', read_only=True)

    class Meta:
        model = Listing
        fields = '__all__'
    
    def create(self, validated_data):
        address_data = validated_data.pop('address')
        offers_data = validated_data.pop('offers')
        description_data = validated_data.pop('description')
        category_names = validated_data.pop('categories_input', [])

        listing = Listing.objects.create(**validated_data)

        PropertyAddress.objects.create(property=listing, **address_data)
        PropertyOffer.objects.create(property=listing, **offers_data)
        PropertyDescription.objects.create(property=listing, **description_data)

        for name in category_names:
            cleaned = name.strip()
            singular_name = p.singular_noun(cleaned)
            normalized = singular_name.title() if singular_name else cleaned.title()
            amenity, _ = Amenity.objects.get_or_create(name=normalized)
            listing.categories.add(amenity)
            
        return listing


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ('status', 'tx_ref', 'chapa_transaction_id')