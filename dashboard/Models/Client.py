from django.db import models
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
