from django.core.mail import EmailMultiAlternatives
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
