from rest_framework import serializers
from .models import Listing, PropertyAddress, PropertyOffer, PropertyDescription, Amenity, PropertyImage, Review, Booking, Payment
from django.contrib.auth import get_user_model
from datetime import date

User = get_user_model()

class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = '__all__'

class PropertyImageSerializer(serializers.ModelSerializer):
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
        if data['start_date'] < date.today():
            raise serializers.ValidationError("Start date cannot be in the past!")

        if data['end_date'] < date.today():
            raise serializers.ValidationError("End date cannot be in the past!")

        if data['end_date'] < data['start_date']:
            raise serializers.ValidationError("End date cannot be less than start date!")

        return data

class ListingSerializer(serializers.ModelSerializer):
    host = serializers.PrimaryKeyRelatedField(read_only=True)
    address = PropertyAddressSerializer()
    offers = PropertyOfferSerializer()
    description = PropertyDescriptionSerializer()
    category = serializers.SlugRelatedField(Many=True, read_only=True, slug_field="name", source="categories")
    categories_input = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    reviews = ReviewSerializer()
    bookings = BookingSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S', read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S', read_only=True)

    class Meta:
        model = Listing
        fields = '__all__'

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ('status', 'tx_ref', 'chapa_transaction_id')
