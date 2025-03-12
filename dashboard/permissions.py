from rest_framework.permissions import BasePermission
from core.models import Role


class CanDeleteUpdateUser(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role == Role.CLIENT_OWNER:
            return (
                obj.user.role in [Role.CLIENT_ADMIN, Role.CLIENT_USER, Role.AGENCY]
                or obj.user == request.user
            )
        if request.user.role == Role.CLIENT_ADMIN:
            return (
                obj.user.role in [Role.CLIENT_USER, Role.AGENCY]
                or obj.user == request.user
            )
        return False


class UserRoleDeleteUpdateClientData(BasePermission):
    def has_object_permission(self, request, view, obj):
        user_role = request.user.role
        if user_role in (Role.CLIENT_ADMIN, Role.CLIENT_OWNER):
            return True

        view_name = view.__class__.__name__
        if view_name == "JobView" and user_role == Role.CLIENT_USER:
            return request.user.clientuser in obj.clients.all()
        elif view_name == "CandidateView" and user_role in (
            Role.CLIENT_USER,
            Role.AGENCY,
        ):
            return request.user.clientuser in obj.designation.clients.all()

        return False
