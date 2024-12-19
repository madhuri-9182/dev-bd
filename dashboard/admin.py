from typing import Any
from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.db.models.query import QuerySet
from django.http import HttpRequest
from .models import InternalClient, ClientPointOfContact


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
