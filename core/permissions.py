from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from .models import Role


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == Role.SUPER_ADMIN


class IsModerator(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == Role.MODERATOR


class IsClientAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == Role.CLIENT_ADMIN


class IsClientOwner(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == Role.CLIENT_OWNER


class IsClientUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == Role.CLIENT_USER


class IsInterviewer(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == Role.INTERVIEWER


class IsAgency(BasePermission):
    def has_permission(self, request, view):
        return request.user.role == Role.AGENCY
