from django.db import models
from core.models import User 
from hiringdogbackend.ModelUtils import SoftDelete


# Internal Client Model
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
    
    

# InternalClient Model
class InternalClient(models.Model):
    objects = SoftDelete()
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='clients'
    )  
    client_registered_name = models.CharField(max_length=255)
    website = models.URLField(max_length=255)
    domain = models.CharField(max_length=255, blank=True, null=True)
    gstin = models.CharField(max_length=15)
    pan = models.CharField(max_length=10)
    signed_or_not = models.CharField(
        max_length=20,
        choices=[('Signed', 'Signed'), ('Not Signed', 'Not Signed')],
    )
    assigned_to = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True,null= True)
    updated_at = models.DateTimeField(auto_now=True)
    archived = models.BooleanField(default=False)

    def __str__(self):
        return self.client_registered_name


class ClientPointOfContact(models.Model):
    objects = SoftDelete()
    
    client = models.ForeignKey(
        InternalClient,
        related_name='points_of_contact',
        on_delete=models.CASCADE,
         null=True,  
        blank=True
    )
    name = models.CharField(max_length=255)
    email_id = models.EmailField()
    mobile_no = models.CharField(max_length=15)
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
    assigned_roles = models.JSONField(default=list, blank=True)  # e.g., ["SDE III", "EM"]
    skills = models.JSONField(default=list, blank=True)         # e.g., ["Java", "Python"]
    strength = models.CharField(max_length=50, blank=True, null=True)  # e.g., Backend
    cv = models.FileField(upload_to="interviewer_cvs/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived = models.BooleanField(default=False)

    def __str__(self):
        return self.name
