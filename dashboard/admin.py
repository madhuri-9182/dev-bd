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
    Candidate,
    InternalInterviewer,
    Interview,
    InterviewerAvailability,
    InterviewFeedback,
    BillingRecord,
)

@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'get_candidate_name',
        'get_interviewer_name',
        'client_amount',
        'interviewer_amount',
        'get_organization_name',
        'created_at',
        "scheduled_time",
        "status",
    )
    list_filter = ('interviewer__name', 'candidate__organization__internal_client__name')
    search_fields = ('candidate__name', 'interviewer__name', 'candidate__organization__internal_client__name')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            'candidate',
            'candidate__organization',
            'candidate__organization__internal_client',
            'interviewer'
        )

    def get_candidate_name(self, obj):
        return obj.candidate.name if hasattr(obj.candidate, 'name') else None
    get_candidate_name.short_description = 'Candidate'

    def get_interviewer_name(self, obj):
        return obj.interviewer.name if hasattr(obj.interviewer, 'name') else None
    get_interviewer_name.short_description = 'Interviewer'

    def get_organization_name(self, obj):
        return obj.candidate.organization.internal_client.name
    get_organization_name.short_description = 'Organization'


@admin.register(InternalInterviewer)
class InternalInterviewer(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "phone_number",
        "total_experience_years",
        "total_experience_months",
    )
    search_fields = ("name", "email", "phone_number")
    list_filter = ("strength",)


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
    list_display = ("pk", "name", "job_id")
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


admin.site.register(InterviewerAvailability)


@admin.register(InterviewFeedback)
class InterviewFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'get_interview_name',
        'overall_remark',
        'overall_score',
        'is_submitted'
    )
    list_filter = ('is_submitted',)
    search_fields = ('interview__candidate__name', 'interview__interviewer__name')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('interview', 'interview__candidate', 'interview__interviewer')

    def get_interview_name(self, obj):
        return f"{obj.interview.candidate.name} - {obj.interview.interviewer.name}"
    get_interview_name.short_description = "Interview"


@admin.register(BillingRecord)
class BillingRecordAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'amount_due',
        "due_date",
        'get_client_name',
        'get_interviewer_name',
    )
    list_filter = ('client', 'interviewer')
    search_fields = ('client__name', 'interviewer__name')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('client', 'interviewer')

    def get_client_name(self, obj):
        return obj.client.name if hasattr(obj.client, 'name') else None
    get_client_name.short_description = 'Client'

    def get_interviewer_name(self, obj):
        return obj.interviewer.name if hasattr(obj.interviewer, 'name') else None
    get_interviewer_name.short_description = 'Interviewer'
