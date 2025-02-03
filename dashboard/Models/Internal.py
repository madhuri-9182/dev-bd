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
        ("SDE_1", "SDE-1"),
        ("SDE_2", "SDE-2"),
        ("SDE_3", "SDE-3"),
        ("PRINCIPAL_ENGINEER", "Principal Engineer"),
        ("ENGINEERING_MANAGER", "Engineering Manager"),
        ("TECHNICAL_LEAD", "Technical Lead"),
        ("VP_ENGINEERING", "VP Engineering"),
        ("DOE", "Director of Engineering"),
        ("DEVOPS_ENGINEER", "DevOps Engineer"),
        ("SENIOR_DEVOPS_ENGINEER", "Senior DevOps Engineer"),
        ("LEAD_DEVOPS_ENGINEER", "Lead DevOps Engineer"),
        ("SDET", "SDET"),
        ("SR_SDET", "Sr. SDET"),
        ("MANAGER_SDET", "Manager-SDET"),
        ("DIRECTOR_SDET", "Director-SDET"),
        ("ML_SCIENTIST", "ML Scientist"),
        ("SR_ML_SCIENTIST", "Sr. ML Scientist"),
        ("LEAD_ML_SCIENTIST", "Lead ML Scientist"),
        ("PRINCIPAL_ML_SCIENTIST", "Principal ML Scientist"),
        ("DATA_ENGINEER", "Data Engineer"),
        ("SR_DATA_ENGINEER", "Sr. Data Engineer"),
        ("LEAD_DATA_ENGINEER", "Lead Data Engineer"),
        ("PRINCIPAL_DATA_ENGINEER", "Principal Data Engineer"),
    )

    STRENGTH_CHOICES = (
        ("backend", "Backend"),
        ("frontend", "Frontend"),
        ("devops", "DevOps"),
        ("testing", "Strength"),
        ("aiml", "AI/ML"),
        ("data_engineer", "Data Engineer"),
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
    assigned_roles = models.JSONField(
        default=list, blank=True
    )  # e.g., ["SDE III", "EM"]
    skills = models.JSONField(default=list, blank=True)  # e.g., ["Java", "Python"]
    strength = models.CharField(
        max_length=50, blank=True, choices=STRENGTH_CHOICES
    )  # e.g., Backend
    cv = models.FileField(upload_to="interviewer_cvs", blank=True)

    def __str__(self):
        return f"{self.name} - {self.organization}"


class Agreement(CreateUpdateDateTimeAndArchivedField):
    objects = SoftDelete()
    object_all = models.Manager()

    YEARS_OF_EXPERIENCE_CHOICES = (
        ("0 - 4 years", "0 - 4 Years"),
        ("4 - 6 years", "4 - 6 Years"),
        ("6 - 8 years", "6 - 8 Years"),
        ("8 - 10 years", "8 - 10 Years"),
        ("10+ years", "10+ Years"),
    )
    
    organization = models.OneToOneField(
        Organization, related_name="agreements", blank=True,on_delete=models.CASCADE)

    years_of_experience = models.CharField(max_length=50, choices=YEARS_OF_EXPERIENCE_CHOICES)
    rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True)
   

    def __str__(self):
        return f"{self.client.name} - {self.rate}"
