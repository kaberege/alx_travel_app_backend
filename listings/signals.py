from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg
from .models import Review

@receiver([post_save, post_delete], sender=Review)
def update_listing_rating(sender, instance, **kwargs):
    listing = instance.property
    result = listing.property_reviews.aggregate(Avg('rating'))['rating__avg']
    listing.average_rating = round(result, 2) if result is not None else 0.0
    listing.save()
