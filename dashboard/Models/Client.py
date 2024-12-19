from organizations.utils import create_organization
from organizations.models import Organization
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from core.models import User
from hiringdogbackend.ModelUtils import SoftDelete


class ClientUser(models.Model):
    objects = SoftDelete()
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="clientuser",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )
    user_type = models.CharField(max_length=100, null=True, blank=True)
    JOB_ASSIGNED_CHOICES = (
        ("sde3", "SDE III"),
        ("pe", "PE"),
        ("sde2", "SDE II"),
        ("devops1", "DevOps I"),
        ("em", "EM"),
        ("sdet2", "SDET II"),
        ("sdet1", "SDET I"),
    )
    job_assigned = models.CharField(
        max_length=10, choices=JOB_ASSIGNED_CHOICES, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived = models.BooleanField(default=False)


class InternalClient(models.Model):
    objects = SoftDelete()
    object_all = models.Manager()
    organization = models.OneToOneField(
        Organization,
        related_name="internal_client",
        on_delete=models.CASCADE,
        blank=True,
    )
    name = models.CharField(max_length=255, blank=True)
    website = models.URLField(max_length=255, blank=True)
    domain = models.CharField(max_length=255, blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    pan = models.CharField(max_length=10, blank=True)
    is_signed = models.BooleanField(default=False)
    assigned_to = models.CharField(max_length=255, blank=True)
    address = models.TextField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class ClientPointOfContact(models.Model):
    objects = SoftDelete()
    object_all = models.Manager()

    client = models.ForeignKey(
        InternalClient,
        related_name="points_of_contact",
        on_delete=models.CASCADE,
        blank=True,
    )
    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(unique=True, blank=True)
    phone = PhoneNumberField(region="IN", unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived = models.BooleanField(default=False)

    def __str__(self):
        return self.name


# Internal Interviewrer Model
class InternalInterviewer(models.Model):
    objects = SoftDelete()
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True)
    current_company = models.CharField(max_length=255, blank=True, null=True)
    previous_company = models.CharField(max_length=255, blank=True, null=True)
    current_designation = models.CharField(max_length=255, blank=True, null=True)
    total_experience_years = models.IntegerField(default=0)
    total_experience_months = models.IntegerField(default=0)
    interview_experience_years = models.IntegerField(default=0)
    interview_experience_months = models.IntegerField(default=0)
    assigned_roles = models.JSONField(
        default=list, blank=True
    )  # e.g., ["SDE III", "EM"]
    skills = models.JSONField(default=list, blank=True)  # e.g., ["Java", "Python"]
    strength = models.CharField(max_length=50, blank=True, null=True)  # e.g., Backend
    cv = models.FileField(upload_to="interviewer_cvs/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived = models.BooleanField(default=False)

    def __str__(self):
        return self.name
