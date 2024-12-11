from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import InternalClient, ClientPointOfContact

@admin.register(InternalClient)
class InternalClientAdmin(admin.ModelAdmin):
    list_display = ('client_registered_name', 'gstin', 'pan', 'signed_or_not', 'assigned_to')
    search_fields = ('client_registered_name', 'gstin', 'pan')
    list_filter = ('signed_or_not',)


@admin.register(ClientPointOfContact)
class ClientPointOfContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'email_id', 'mobile_no', 'client')
    search_fields = ('name', 'email_id')
