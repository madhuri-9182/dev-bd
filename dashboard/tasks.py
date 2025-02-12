from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from celery import shared_task
from django.conf import settings


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
            if not email_address:
                continue

            html_content = render_to_string(template, context)

            email = EmailMultiAlternatives(
                subject=subject,
                body="This is an HTML email. Please view it in an HTML-compatible email client.",
                from_email=settings.EMAIL_HOST_USER,
                to=[email_address],
                connection=connection,
            )
            email.attach_alternative(html_content, "text/html")
            emails.append(email)

        if emails:
            connection.send_messages(emails)
