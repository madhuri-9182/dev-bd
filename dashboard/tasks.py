from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from celery import shared_task
from django.conf import settings


@shared_task()
def send_welcome_mail_upon_successful_onboarding(email, password, **kwargs):
    context = {
        "email": email,
        "password": password,
        **kwargs,
    }
    subject = "Welcome to Hiring Dog"

    content = render_to_string("onboard.html", context=context)
    email = EmailMultiAlternatives(
        subject,
        "",
        settings.EMAIL_HOST_USER,
        [email],
    )
    email.attach_alternative(content, "text/html")
    email.send()
