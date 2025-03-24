from typing import Any
from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.db.models.query import QuerySet
from django.http import HttpRequest
from .models import (
    InternalClient,
    ClientPointOfContact,
    Job,
    ClientUser,
    EngagementTemplates,
    Candidate
)


@admin.register(InternalClient)
class InternalClientAdmin(admin.ModelAdmin):
    list_display = ("name", "gstin", "pan", "is_signed", "assigned_to")
    search_fields = ("name", "gstin", "pan")
    list_filter = ("is_signed",)


@admin.register(ClientPointOfContact)
class ClientPointOfContactAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "client")
    search_fields = ("name", "email")

    def get_queryset(self, request):
        return ClientPointOfContact.object_all.all()


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("name", "job_id")
    search_fields = ("name", "job_id")

    def get_queryset(self, request):
        return Job.object_all.all()


@admin.register(ClientUser)
class ClientUserAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "user", "name", "invited_by", "status")
    search_fields = ("id", "organization", "name")
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        return ClientUser.object_all.all()


@admin.register(EngagementTemplates)
class EnagagementTeamplteAdmin(admin.ModelAdmin):
    list_display = ("id", "template_name", "organization__name")
    search_fields = ("organization__name", "template_name")
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return EngagementTemplates.object_all.select_related("organization")

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "specialization", "organization__name")
    search_fields = ("organization__name",)
    readonly_fields = ["created_at", "updated_at"]
    