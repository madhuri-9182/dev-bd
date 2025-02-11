from organizations.models import Organization
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from phonenumber_field.modelfields import PhoneNumberField
from core.models import User
from hiringdogbackend.ModelUtils import SoftDelete, CreateUpdateDateTimeAndArchivedField


class InternalClient(CreateUpdateDateTimeAndArchivedField):
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

    def __str__(self):
        return self.name


class ClientPointOfContact(CreateUpdateDateTimeAndArchivedField):
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

    def __str__(self):
        return self.name


class InternalInterviewer(CreateUpdateDateTimeAndArchivedField):
    objects = SoftDelete()
    object_all = models.Manager()

    ROLE_CHOICES = (
        ("SDE_I", "SDE-I"),
        ("SDE_II", "SDE-II"),
        ("SDE_III", "SDE-III"),
        ("PE", "Principal Engineer"),
        ("EM", "Engineering Manager"),
        ("TL", "Technical Lead"),
        ("VPE", "VP Engineering"),
        ("DOE", "Director of Engineering"),
        ("DE", "DevOps Engineer"),
        ("SR_DE", "Senior DevOps Engineer"),
        ("LD_DE", "Lead DevOps Engineer"),
        ("SDET", "SDET"),
        ("SR_SDET", "Sr. SDET"),
        ("MGR_SDET", "Manager-SDET"),
        ("DIR_SDET", "Director-SDET"),
        ("MLS", "ML Scientist"),
        ("SR_MLS", "Sr. ML Scientist"),
        ("LD_MLS", "Lead ML Scientist"),
        ("P_MLS", "Principal ML Scientist"),
        ("DEE", "Data Engineer"),
        ("SR_DEE", "Sr. Data Engineer"),
        ("LD_DEE", "Lead Data Engineer"),
        ("P_DEE", "Principal Data Engineer"),
    )

    STRENGTH_CHOICES = (
        ("frontend", "Frontend"),
        ("backend", "Backend"),
        ("fullstack", "Fullstack"),
        ("aiml", "AI/ML"),
        ("devops", "DevOps"),
        ("data_engineer", "Data Engineering"),
        ("testing", "Testing/QA"),
        ("android", "Android"),
        ("ios", "iOS"),
        ("mobile", "Mobile (Android + iOS)"),
    )

    organization = models.ManyToManyField(
        Organization, related_name="interviewers", blank=True
    )
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="interviewer", blank=True
    )
    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(unique=True, blank=True)
    phone_number = PhoneNumberField(region="IN", unique=True, blank=True)
    current_company = models.CharField(max_length=255, blank=True)
    previous_company = models.CharField(max_length=255, blank=True)
    current_designation = models.CharField(max_length=255, blank=True)
    total_experience_years = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1, message="Expereince should be more than 1 year"),
            MaxValueValidator(50, message="Enter a valid Experience"),
        ],
    )
    total_experience_months = models.PositiveSmallIntegerField(default=0)
    interview_experience_years = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1, message="Expereince should be more than 1 year"),
            MaxValueValidator(50, message="Enter a valid Experience"),
        ],
    )
    interview_experience_months = models.PositiveSmallIntegerField(default=0)
    assigned_roles = models.CharField(
        max_length=15, choices=ROLE_CHOICES, blank=True
    )  # e.g., ["SDE III", "EM"]
    skills = models.JSONField(default=list, blank=True)  # e.g., ["Java", "Python"]
    strength = models.CharField(
        max_length=50, blank=True, choices=STRENGTH_CHOICES
    )  # e.g., Backend
    cv = models.FileField(upload_to="interviewer_cvs", blank=True)

    def __str__(self):
        return f"{self.name} - {self.organization}"
