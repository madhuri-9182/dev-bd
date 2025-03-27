from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone
from celery import shared_task, chain, group
from celery.exceptions import Reject
from django.conf import settings
from django.utils.safestring import mark_safe
from .models import EngagementOperation, Interview, InterviewFeedback
from externals.google.google_meet import download_from_google_drive
from datetime import datetime, timedelta
from externals.feedback.interview_feedback import (
    analyze_transcription_and_generate_feedback,
)


@shared_task(bind=True, max_retries=3, rate_limit="10/m")
def send_mail(
    self, to, subject, template, reply_to=None, attachmenets=[], bcc=None, **kwargs
):
    email_type = kwargs.get("type")
    context = {
        "email": to,
        **kwargs,
    }

    try:
        content = render_to_string(template, context=context)
        email_message = EmailMultiAlternatives(
            subject, "", settings.EMAIL_HOST_USER, [to], reply_to=[reply_to], bcc=[bcc]
        )
        email_message.attach_alternative(content, "text/html")
        for attachment in attachmenets:
            email_message.attach_file(attachment)
        email_message.send(fail_silently=True)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60, retry_jitter=True)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=60, retry_jitter=True)
def send_email_to_multiple_recipients(self, contexts, subject, template, **kwargs):
    emails = []

    with get_connection() as connection:
        for context in contexts:
            email_address = context.get("email")
            from_email = context.get("from_email")
            if context.get("subject"):
                subject = context["subject"]

            if context.get("template"):
                template = context["template"]

            if not email_address:
                continue

            html_content = render_to_string(template, context)

            email = EmailMultiAlternatives(
                subject=subject,
                body="This is an HTML email. Please view it in an HTML-compatible email client.",
                from_email=from_email if from_email else settings.EMAIL_HOST_USER,
                to=[email_address],
                connection=connection,
            )
            email.attach_alternative(html_content, "text/html")
            emails.append(email)

        if emails:
            connection.send_messages(emails)


@shared_task(bind=True, max_retries=4)
def send_schedule_engagement_email(self, engagement_operation_id):
    try:
        engagement_operation_obj = (
            EngagementOperation.objects.select_related(
                "template", "engagement", "engagement__candidate"
            )
            .only(
                "template__subject",
                "template__template_html_content",
                "engagement__candidate__email",
                "engagement__candidate_email",
            )
            .get(pk=engagement_operation_id)
        )

        email = EmailMultiAlternatives(
            subject=engagement_operation_obj.template.subject,
            body="This is an email.",
            from_email=settings.EMAIL_HOST_USER,
            to=[
                getattr(
                    engagement_operation_obj.engagement.candidate,
                    "email",
                    engagement_operation_obj.engagement.candidate_email,
                )
            ],
        )
        email.attach_alternative(
            mark_safe(engagement_operation_obj.template.template_html_content),
            "text/html",
        )
        email.send()
        engagement_operation_obj.delivery_status = "SUC"
        engagement_operation_obj.save()
    except Exception as e:
        engagement_operation_obj.delivery_status = "FLD"
        engagement_operation_obj.save()
        if self.request.revoked:
            raise Ignore()
        raise self.retry(exec=e, countdown=60)


@shared_task
def fetch_interview_records():
    current_time = timezone.now()
    before_one_and_half_an_hour = current_time - timedelta(hours=1, minutes=30)
    interview_qs = Interview.objects.filter(
        scheduled_time__lte=before_one_and_half_an_hour,
        downloaded=False,
        scheduled_service_account_event_id__isnull=False,
    ).values_list("id", "scheduled_service_account_event_id")
    return list(interview_qs)


@shared_task(bind=True, retry_backoff=5, max_retries=3)
def download_recordings_from_google_drive(self, interview_info):
    if not interview_info or len(interview_info) != 2:
        raise Reject("Missing or invalid interview info")
    interview_id, event_id = interview_info
    try:
        download_recording_info = download_from_google_drive(interview_id, event_id)
        if not download_recording_info:
            raise Reject(f"Failed to download recordings for Interview {interview_id}")
        return download_recording_info
    except Reject:
        raise
    except Exception as e:
        raise self.retry(exc=e)


@shared_task
def store_recordings(recording_info):
    try:
        interview = Interview.objects.get(pk=recording_info["interview_id"])
    except Interview.DoesNotExist:
        raise Reject(f"Interview {recording_info['interview_id']} not found")

    for file in recording_info["files"]:
        if file["type"] == "video":
            interview.recording.save(file["name"], ContentFile(file["data"]))
        elif file["type"] == "transcript":
            interview.transcription.save(file["name"], ContentFile(file["data"]))

    interview.downloaded = True
    interview.save(update_fields=["recording", "transcription", "downloaded"])
    return interview.id


@shared_task(bind=True)
def process_interview_recordings(self, interview_record_ids):
    if not interview_record_ids:
        raise Reject("No interviews to process")

    tasks = [
        chain(
            download_recordings_from_google_drive.s(interview_info),
            store_recordings.s(),
        )
        for interview_info in interview_record_ids
    ]
    group(*tasks).apply_async()


@shared_task
def trigger_interview_processing():
    chain(fetch_interview_records.s(), process_interview_recordings.s()).apply_async()


@shared_task(bind=True, retry_backoff=5, max_retries=3)
def process_interview_video_and_generate_and_store_feedback(self):
    interviews = Interview.objects.filter(
        transcription__isnull=False, interview_feedback__isnull=True
    ).only("id", "feedback")
    print(interviews)
    processed_ids = []
    for interview in interviews:
        try:
            with interview.transcription.open("r") as f:
                file_content = f.read()
            extracted_data = analyze_transcription_and_generate_feedback(file_content)
        except Exception as e:
            print(str(e))
            continue
        InterviewFeedback.objects.update_or_create(
            interview_id=interview.id, defaults={**extracted_data}
        )
        processed_ids.append(interview.id)
        interviewer_name = interview.interviewer.name
        candidate_name = interview.candidate.name
        send_mail.delay(
            to=interview.interviewer.email,
            subject=f"Ready to Review? Feedback for {candidate_name} is Live",
            template="interview_feedback_notification_email.html",
            reply_to=settings.CONTACT_EMAIL,
            interviewer_name=interviewer_name,
            candidate_name=candidate_name,
            dashboard_link="https://app.hdiplatform.in/",
            type="feedback_notification",
        )
    return f"Interview feedback created successfully for {processed_ids}."
