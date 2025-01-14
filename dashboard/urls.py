from django.urls import path
from .views import (
    ClientUserView,
    InternalClientView,
    InternalClientDetailsView,
    InterviewerView,
    InterviewerDetails,
)


urlpatterns = [
    path("client-user/", ClientUserView.as_view(), name="client-user"),
    path("internal-clients/", InternalClientView.as_view(), name="internal-client"),
    path(
        "internal-client/<int:pk>/",
        InternalClientDetailsView.as_view(),
        name="internal-client-details",
    ),
    path("interviewers/", InterviewerView.as_view(), name="interviewer"),
    path(
        "interviewer/<int:pk>/",
        InterviewerDetails.as_view(),
        name="interviewer-details",
    ),
]
