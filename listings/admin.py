from django.contrib import admin
from .models import Listing, Booking, Payment

class ListingAdmin(admin.ModelAdmin):
    list_display=('name','location', 'pricepernight', 'created_at', 'updated_at')
    list_filter=('name','location', 'pricepernight', 'created_at', 'updated_at')
    search_fields=('name','location', 'pricepernight', 'created_at', 'updated_at')
    odering=('name','location', 'pricepernight', 'created_at', 'updated_at')

class BookingAdmin(admin.ModelAdmin):
    list_display=('property','user', 'start_date', 'total_price', 'status', 'created_at')
    list_filter=('property','user', 'start_date', 'total_price', 'status', 'created_at')
    search_fields=('property','user', 'start_date', 'total_price', 'status', 'created_at')
    odering=('property','user', 'start_date', 'total_price', 'status', 'created_at')

class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_id', 'booking', 'amount', 'tx_ref', 'chapa_transaction_id', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = ('tx_ref', 'chapa_transaction_id', 'booking__booking_id', 'booking__user__email')
    readonly_fields = ('payment_id', 'created_at', 'updated_at', 'chapa_transaction_id')
    ordering = ('-created_at',)

admin.site.register(Listing, ListingAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(Payment, PaymentAdmin)