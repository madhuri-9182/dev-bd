from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from .Client import Candidate
from .Internal import InternalInterviewer
from hiringdogbackend.ModelUtils import SoftDelete, CreateUpdateDateTimeAndArchivedField


class Interview(CreateUpdateDateTimeAndArchivedField):
    objects = SoftDelete()
    object_all = models.Manager()

    candidate = models.ForeignKey(
        Candidate, on_delete=models.DO_NOTHING, related_name="interviews", blank=True
    )
    interviewer = models.ForeignKey(
        InternalInterviewer,
        on_delete=models.DO_NOTHING,
        related_name="interviews",
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=15,
        choices=Candidate.STATUS_CHOICES,
        blank=True,
        help_text="Interview status",
    )
    scheduled_time = models.DateTimeField(help_text="Scheduled interview date and time")
    previous_interview = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rescheduled_interviews",
        help_text="Reference to the previous interview instance if rescheduled.",
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
    scheduled_service_account_event_id = models.CharField(
        max_length=255, null=True, blank=True
    )
    meeting_link = models.URLField(null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.candidate.status = self.status
        self.candidate.score = self.score
        self.candidate.total_score = self.total_score
        self.candidate.save()


class InterviewFeedback(CreateUpdateDateTimeAndArchivedField):
    interview = models.OneToOneField(
        Interview,
        on_delete=models.CASCADE,
        related_name="interview_feedback",
        help_text="The interviewer's feedback on interview.",
        blank=True,
        null=True,
    )
    skill_based_performance = models.JSONField(default=dict)
    skill_evaluation = models.JSONField(default=dict)
    strength = models.CharField(max_length=500, null=True)
    improvement_points = models.CharField(max_length=500, null=True)
    overall_remark = models.CharField(
        max_length=10,
        null=True,
        choices=(
            ("HREC", "Highly Recommended"),
            ("REC", "Recommended"),
            ("NREC", "Not Recommended"),
            ("SNREC", "Strongly Not Recommended"),
            ("NJ", "Not Joined"),
        ),
    )
    overall_score = models.PositiveSmallIntegerField(
        default=0,
        validators=[
            MinValueValidator(0, message="Score should be greater than or equal to 0"),
            MaxValueValidator(100, message="Scroe must not exceed 100"),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
