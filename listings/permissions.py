from rest_framework import permissions

class IsHostUser(permissions.BasePermission):
    """
    Allows access only to authenticated users with the 'host' role or staff/admins.
    """
    message = "Access restricted: You must be registered as a Host."

    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role == 'host' or request.user.is_staff)
        )


class IsHostOrReadOnly(permissions.BasePermission):
    """
    - Safe methods (GET, HEAD, OPTIONS): Allowed for everyone (public/guests).
    - Unsafe methods (POST, PUT, PATCH, DELETE): Requires authenticated Host ownership or Admin status.
    """
    message = "You must be authenticated as the owner (host) of this property to modify it."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role = 'host' or request.user.is_staff)
        )

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user.is_staff or 
            (obj.host == request.user and request.user.role == 'host')
        )

class IsBookingOwnerOrHost(permissions.BasePermission):
    """
    Custom permission for Bookings:
    - Guests can view and manage their own bookings.
    - Property Hosts can view bookings made for their properties.
    """
    message = "Access denied. You do not have permission to access this booking."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        is_guest = obj.user == request.user
        is_host = obj.property.host == request.user
        return is_guest or is_host or request.user.is_staff


class IsReviewAuthorOrReadOnly(permissions.BasePermission):
    """
    Custom permission for Reviews:
    - Anyone can read reviews.
    - Only the user who authored the review can edit or delete it.
    """
    message = "Only the author of this review can modify it."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user.is_staff or obj.user == request.user)