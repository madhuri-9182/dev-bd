from django.urls import path
from ..views import (
    ClientUserView,
    ClientInvitationActivateView,
    JobView,
    ResumeParserView,
    CandidateView,
    PotentialInterviewerAvailabilityForCandidateView,
    EngagementTemplateView,
    EngagementView,
    EngagementOperationView,
    EngagementOperationUpdateView,
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
    path(
        "interviewer-availability/",
        PotentialInterviewerAvailabilityForCandidateView.as_view(),
        name="interviewer-availablity",
    ),
    path("parse-resume/", ResumeParserView.as_view(), name="resume-parser"),
    path(
        "engagement-templates/",
        EngagementTemplateView.as_view(),
        name="engagement-tempates",
    ),
    path(
        "engagement-template/<int:pk>/",
        EngagementTemplateView.as_view(),
        name="engagement-tempates",
    ),
    path("engagements/", EngagementView.as_view(), name="candidate-engagements"),
    path(
        "engagement-operation/",
        EngagementOperationView.as_view(),
        name="engagement-operation",
    ),
    path(
        "engagement-operation/<int:engagement_id>/",
        EngagementOperationUpdateView.as_view(),
        name="engagement-operation-update",
    ),
]
