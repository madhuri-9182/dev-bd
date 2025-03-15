from django.urls import path
from ..views import (
    InterviewerAvailabilityView,
    InterviewerReqeustView,
    InterviewerRequestResponseView,
    InterviewerDashboardView,
)

urlpatterns = [
    path(
        "block-calendar/",
        InterviewerAvailabilityView.as_view(),
        name="calendar-blocking",
    ),
    path(
        "interviewer-request-notification/",
        InterviewerReqeustView.as_view(),
        name="interviewer-request-notification",
    ),
    path(
        "interviewer-requst-confirmation/<str:request_id>/",
        InterviewerRequestResponseView.as_view(),
        name="interviewer-request-confirmation",
    ),
    path(
        "interviewer-dashboard/",
        InterviewerDashboardView.as_view(),
        name="interviewer-dashbard",
    ),
]
