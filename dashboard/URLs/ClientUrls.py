from django.urls import path
from ..views import (
    ClientUserView,
    ClientInvitationActivateView,
    JobView,
    ResumePraserView,
    CandidateView,
)


urlpatterns = [
    path("client-user/", ClientUserView.as_view(), name="client-user"),
    path(
        "client-user/<int:client_user_id>/",
        ClientUserView.as_view(),
        name="client-user-details",
    ),
    path(
        "client-user-activation/<str:uid>/",
        ClientInvitationActivateView.as_view(),
        name="client-user-activation",
    ),
    path("candidates/", CandidateView.as_view(), name="candidates"),
    path("candidate/<int:candidate_id>/", CandidateView.as_view(), name="candidate"),
    path("jobs/", JobView.as_view(), name="job-list"),
    path("job/<int:job_id>/", JobView.as_view(), name="job-details"),
    path("parse-resume/", ResumePraserView.as_view(), name="resume-parser"),
]
