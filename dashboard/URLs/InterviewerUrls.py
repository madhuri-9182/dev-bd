from django.urls import path
from ..views import InterviewerAvailabilityView, InterviewerReqeustView

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
]
