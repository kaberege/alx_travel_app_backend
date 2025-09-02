from rest_framework import permissions

class IsAuthenticatedIsOwnerOrReadOnlyListing(permissions.BasePermission):
    message = (
        "You must be authenticated to modify this listing, and only the host is allowed "
        "to update or delete it. Unauthenticated users have read-only access."
    )

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return obj.host == request.user

class IsAuthenticatedIsOwnerBooking(permissions.BasePermission):
    message = (
        "Access denied. You must be authenticated and must be the owner of this booking "
        "to view or modify it."
    )

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user