from django.contrib import admin
from .models import (
    Amenity, Listing, PropertyImage, PropertyAddress, 
    PropertyOffer, PropertyDescription, Review, Booking, Payment
)

class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    readonly_fields = ('image_id',)

class PropertyAddressInline(admin.StackedInline):
    model = PropertyAddress
    can_delete = False

class PropertyOfferInline(admin.StackedInline):
    model = PropertyOffer
    can_delete = False

class PropertyDescriptionInline(admin.StackedInline):
    model = PropertyDescription
    can_delete = False


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('name', 'host', 'price_per_night', 'discount', 'average_rating', 'get_location', 'created_at')
    list_filter = ('created_at', 'updated_at', 'address__country', 'address__state')
    search_fields = ('name', 'host__email', 'host__username', 'address__city', 'address__country')
    ordering = ('-created_at',)
    inlines = [PropertyAddressInline, PropertyOfferInline, PropertyDescriptionInline, PropertyImageInline]
    filter_horizontal = ('categories',)

    @admin.display(description='Location')
    def get_location(self, obj):
        if hasattr(obj, 'address'):
            return f"{obj.address.city}, {obj.address.country}"
        return "N/A"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'property', 'user', 'start_date', 'end_date', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'start_date', 'created_at')
    search_fields = ('booking_id', 'property__name', 'user__email', 'user__username')
    ordering = ('-created_at',)
    readonly_fields = ('booking_id', 'created_at')
    actions = ['mark_as_confirmed', 'mark_as_canceled']

    @admin.action(description="Mark selected bookings as Confirmed")
    def mark_as_confirmed(self, request, queryset):
        queryset.update(status='confirmed')

    @admin.action(description="Mark selected bookings as Canceled")
    def mark_as_canceled(self, request, queryset):
        queryset.update(status='canceled')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'booking', 'amount', 'tx_ref', 'chapa_transaction_id', 'status', 'created_at')
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = ('tx_ref', 'chapa_transaction_id', 'booking__booking_id', 'booking__user__email')
    readonly_fields = ('payment_id', 'created_at', 'updated_at', 'chapa_transaction_id')
    ordering = ('-created_at',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('review_id', 'property', 'user', 'rating', 'trip_type', 'created_at')
    list_filter = ('rating', 'trip_type', 'created_at')
    search_fields = ('property__name', 'user__email', 'comment')
    readonly_fields = ('review_id', 'created_at')