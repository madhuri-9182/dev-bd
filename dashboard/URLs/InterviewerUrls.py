from django.urls import path
from ..views import InterviewerAvailabilityView

urlpatterns = [
    path(
        "block-calendar/",
        InterviewerAvailabilityView.as_view(),
        name="calendar-blocking",
    )
]
