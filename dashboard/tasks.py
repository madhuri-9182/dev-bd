from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from celery import shared_task
from celery.exceptions import Ignore
from django.conf import settings
from django.utils.safestring import mark_safe
from .models import EngagementOperation


@shared_task()
def send_mail(email, subject, template, **kwargs):
    context = {
        "email": email,
        **kwargs,
    }

    content = render_to_string(template, context=context)
    email = EmailMultiAlternatives(
        subject,
        "",
        settings.EMAIL_HOST_USER,
        [email],
    )
    email.attach_alternative(content, "text/html")
    email.send(fail_silently=True)


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
        self.retry(exec=e, countdown=60)
