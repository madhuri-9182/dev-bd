from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from hiringdogbackend.ModelUtils import SoftDelete, CreateUpdateDateTimeAndArchivedField
from .Internal import InternalClient, InternalInterviewer
from .Client import Organization
from .Internal import InternalInterviewer
from .Interviews import Interview


class BillingLog(CreateUpdateDateTimeAndArchivedField):
    BILLING_REASON_CHOICES = [
        ("feedback_submitted", "Feedback Submitted"),
        ("late_rescheduled", "Late Rescheduled"),
    ]

    interview = models.ForeignKey(Interview, on_delete=models.CASCADE)
    client = models.ForeignKey(Organization, on_delete=models.CASCADE)
    interviewer = models.ForeignKey(InternalInterviewer, on_delete=models.CASCADE)

    amount_for_client = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_for_interviewer = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )

    reason = models.CharField(max_length=50, choices=BILLING_REASON_CHOICES)
    billing_month = models.DateField()
    is_billing_calculated = models.BooleanField(default=False)

    class Meta:
        unique_together = (("interview", "reason"),)


class BillingRecord(CreateUpdateDateTimeAndArchivedField):
    RECORD_TYPE_CHOICES = (
        ("CLB", "Client Billing"),
        ("INP", "Interviewer Payment"),
    )

    STATUS_CHOICES = (
        ("PED", "Pending"),
        ("PAI", "Paid"),
        ("OVER", "Overdue"),
        ("CAN", "Cancelled"),
        ("FLD", "Failed"),
        ("INP", "Inprogress"),
    )

    objects = SoftDelete()
    object_all = models.Manager()

    billing_month = models.DateField(
        db_index=True, editable=False
    )  # stores first day of month

    record_type = models.CharField(
        max_length=15, choices=RECORD_TYPE_CHOICES, null=True, blank=True
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="PED")

    amount_due = models.DecimalField(max_digits=10, decimal_places=2)

    due_date = models.DateField()
    payment_date = models.DateTimeField(null=True, blank=True) #unused one

    invoice_number = models.CharField(max_length=20, unique=True, null=True, blank=True)

    client = models.ForeignKey(
        InternalClient,
        on_delete=models.CASCADE,
        related_name="finance_records",
        null=True,
        blank=True,
    )
    interviewer = models.ForeignKey(
        InternalInterviewer,
        on_delete=models.CASCADE,
        related_name="finance_records",
        null=True,
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["record_type", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["client", "billing_month"],
                name="unique_client_billing_per_month",
            ),
            models.UniqueConstraint(
                fields=["interviewer", "billing_month"],
                name="unique_interviewer_billing_per_month",
            ),
        ]

    def __str__(self):
        if self.record_type == "CLB":
            return f"Client Billing - {self.client.name} - {self.amount_due}"
        return f"Interviewer Payment - {self.interviewer.name} - {self.amount_due}"

    def save(self, *args, **kwargs):
        if self.record_type == "CLB" and not self.client:
            raise ValidationError("Client is required for client billing records")
        if self.record_type == "INP" and not self.interviewer:
            raise ValidationError(
                "Interviewer is required for interviewer payment records"
            )
        if not self.billing_month:
            self.billing_month = timezone.now().replace(day=1).date()
        super().save(*args, **kwargs)


class BillPayments(CreateUpdateDateTimeAndArchivedField):
    objects = SoftDelete()
    object_all = models.Manager()

    PAYMENT_STATUS_CHOICES = [
        ("SUC", "Success"),
        ("FLD", "Failed"),
        ("UDP", "User Dropped"),
        ("CNL", "Cancelled"),
        ("VOD", "Void"),
    ]

    billing_record = models.ForeignKey(
        BillingRecord, on_delete=models.DO_NOTHING, related_name="billing_payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_link_id = models.CharField(max_length=100, unique=True)
    payment_status = models.CharField(max_length=15, choices=PAYMENT_STATUS_CHOICES)
    payment_date = models.DateField(auto_now_add=True)
    transaction_id = models.CharField(
        max_length=100, unique=True, null=True, blank=True
    )
    link_expired_time = models.DateTimeField()
    cf_link_id = models.CharField(max_length=100, unique=True)
    order_id = models.CharField(max_length=100, unique=True, null=True, blank=True)

    # Customer Details
    customer_name = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=15)
    customer_email = models.EmailField()

    # both link generation and webhook response
    meta_data = models.JSONField(default=dict)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.payment_status == "SUC":
            billing_record = self.billing_record
            billing_record.amount_due = 0
            billing_record.status = "PAI"
            billing_record.save()
