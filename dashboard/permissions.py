from rest_framework.permissions import BasePermission


class CanDeleteUpdateUser(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role == "client_owner":
            return obj.user.role in ["client_admin", "client_user"]
        if request.user.role == "client_admin":
            return obj.user.role == "client_user"
        return False
