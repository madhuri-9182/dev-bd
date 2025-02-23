from django.urls import path
from ..views import (
    InternalClientView,
    InternalClientDetailsView,
    InterviewerDetails,
    InterviewerView,
    InternalDashboardView,
    InternalUserView,
    HDIPUsersViews,
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
    path("dashboard/", InternalDashboardView.as_view(),name="dashboard"),
    path("hdip-user/", HDIPUsersViews.as_view(), name="hdip-user"),
    path("internal-user/", InternalUserView.as_view(), name="internal-user")
]
