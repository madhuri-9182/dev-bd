from rest_framework.permissions import BasePermission
from core.models import Role


class CanDeleteUpdateUser(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role == Role.CLIENT_OWNER:
            return obj.user.role in [Role.CLIENT_ADMIN, Role.CLIENT_USER]
        if request.user.role == Role.CLIENT_ADMIN:
            return obj.user.role == Role.CLIENT_USER
        return False


class CanDeleteUpdateCandidateData(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role in [Role.CLIENT_ADMIN, Role.CLIENT_OWNER]:
            return True
        if request.user.role in [Role.CLIENT_USER, Role.AGENCY]:
            return request.user.clientuser in obj.designation.clients.all()
        return False
