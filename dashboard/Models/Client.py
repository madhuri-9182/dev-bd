from organizations.models import Organization
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from core.models import User
from hiringdogbackend.ModelUtils import SoftDelete, CreateUpdateDateTimeAndArchivedField
from .Internal import InternalInterviewer


class ClientUser(CreateUpdateDateTimeAndArchivedField):
    STATUS_CHOICES = (
        ("ACT", "Active"),
        ("INACT", "Inactive"),
        ("PEND", "Pending"),
    )

    objects = SoftDelete()
    object_all = models.Manager()

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="clientuser", blank=True
    )
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="clientuser", blank=True
    )
    name = models.CharField(max_length=100, blank=True)
    designation = models.CharField(
        max_length=100,
        blank=True,
        null=True,  # Allows null values to prevent empty strings from being stored as null
    )
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="invited_by_clientuser",
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        blank=True,
        help_text="verification status",
        default="PEND",
    )


class Job(CreateUpdateDateTimeAndArchivedField):
    REASON_FOR_ARCHIVED_CHOICES = (
        ("PF", "Position Filled"),
        ("POH", "Position On Hold"),
        ("OTH", "Other"),
    )
    objects = SoftDelete()
    object_all = models.Manager()
    client = models.ForeignKey(
        ClientUser, on_delete=models.CASCADE, related_name="recruiter", blank=True
    )
    name = models.CharField(max_length=100, blank=True)
    job_id = models.CharField(max_length=100, blank=True, null=True)
    hiring_manager = models.ForeignKey(
        ClientUser,
        on_delete=models.CASCADE,
        related_name="hiringmanager",
        blank=True,
    )
    total_positions = models.PositiveSmallIntegerField(default=0)
    job_description_file = models.FileField(upload_to="job_descriptions", blank=True)
    mandatory_skills = models.TextField(blank=True)
    interview_time = models.TimeField(help_text="duration", null=True)
    other_details = models.JSONField(default=list, blank=True, null=True)
    reason_for_archived = models.CharField(
        max_length=15, choices=REASON_FOR_ARCHIVED_CHOICES, blank=True, null=True
    )


class Candidate(CreateUpdateDateTimeAndArchivedField):
    STATUS_CHOICES = (
        ("HREC", "Highly Recommended"),
        ("REC", "Recommended"),
        ("NREC", "Not Recommended"),
        ("SNREC", "Strongly Not Recommended"),
        ("SCH", "Schedule"),
        ("NSCH", "Not Schedule"),
        ("NJ", "Not Joined"),
    )
    REASON_FOR_DROPPING_CHOICES = (
        ("CNI", "Candidate Not Interested"),
        ("CNA", "Candidate Not Available"),
        ("CNR", "Candidate Not Responded"),
        ("OTH", "Others"),
    )
    objects = SoftDelete()
    object_all = models.Manager()
    name = models.CharField(max_length=100, blank=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="candidate"
    )
    year = models.PositiveSmallIntegerField(
        default=0, help_text="candidate experience total year"
    )
    month = models.PositiveBigIntegerField(
        default=0, help_text="candidate experience total month"
    )
    phone = PhoneNumberField(region="IN", blank=True)
    email = models.EmailField(max_length=255, blank=True)
    company = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    source = models.CharField(
        max_length=100, blank=True, help_text="From Which side this candidate is ?"
    )
    cv = models.FileField(upload_to="candidate_cvs")
    remark = models.TextField(max_length=255, blank=True, null=True)
    specialization = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        blank=True,
        default="NSCH",
        help_text="candidate interview status",
    )
    reason_for_dropping = models.CharField(
        max_length=100, choices=REASON_FOR_DROPPING_CHOICES, blank=True
    )
    score = models.PositiveSmallIntegerField(default=0)
    total_score = models.PositiveSmallIntegerField(default=0)


class Interview(CreateUpdateDateTimeAndArchivedField):
    objects = SoftDelete()
    object_all = models.Manager()

    candidate = models.ForeignKey(
        Candidate, on_delete=models.DO_NOTHING, related_name="interviews", blank=True
    )
    interivewer = models.ForeignKey(
        InternalInterviewer,
        on_delete=models.DO_NOTHING,
        related_name="interviews",
        blank=True,
    )
    status = models.CharField(
        max_length=15,
        choices=Candidate.STATUS_CHOICES,
        blank=True,
        help_text="Interview status",
    )
    date = models.DateTimeField(help_text="Scheduled interview date and time")
    reschedule = models.BooleanField(
        default=False, help_text="Indicates if the interview has been rescheduled"
    )
    recording = models.FileField(
        upload_to="interview_recordings",
        blank=True,
        null=True,
        help_text="Interview recording file",
    )
    feedback = models.TextField(
        blank=True, null=True, help_text="Feedback for the candidate"
    )
    score = models.PositiveSmallIntegerField(default=0)
    total_score = models.PositiveSmallIntegerField(default=0)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.candidate.status = self.status
        self.candidate.score = self.score
        self.candidate.total_score = self.total_score
        self.candidate.save()
