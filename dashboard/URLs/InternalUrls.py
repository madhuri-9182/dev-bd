from django.urls import path
from ..views import (
    InternalClientView,
    InternalClientDetailsView,
    InterviewerDetails,
    InterviewerView,
    AgreementView,
    AgreementDetailView,
    OrganizationView,
    InternalDashboardView,
    InternalClientUserView,
    HDIPUsersViews,
    DomainDesignationView,
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
    path(
        "agreement/<int:pk>/", AgreementDetailView.as_view(), name="agreement-details"
    ),
    path("organizations/", OrganizationView.as_view(), name="organizations"),
    path("dashboard/", InternalDashboardView.as_view(), name="dashboard"),
    path("hdip-users/", HDIPUsersViews.as_view(), name="hdip-user"),
    path("hdip-user/<int:pk>/", HDIPUsersViews.as_view(), name="hdip-user-details"),
    path(
        "internal-client-user/", InternalClientUserView.as_view(), name="internal-user"
    ),
    path(
        "internal-client-user/<int:pk>/",
        InternalClientUserView.as_view(),
        name="internal-user",
    ),
    path(
        "domain-designation/",
        DomainDesignationView.as_view(),
        name="domain-designation",
    ),
]
