from django.urls import path
from ..views import (
    InternalClientView,
    InternalClientDetailsView,
    InterviewerDetails,
    InterviewerView,
    AgreementView,
    AgreementDetailView,
)

urlpatterns = [
    path("internal-client/", InternalClientView.as_view(), name="internal-client"),
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
    path("agreements/", AgreementView.as_view(), name="agreement"),
    path("agreement/<int:pk>/", AgreementDetailView.as_view(), name="agreement-details")
]
