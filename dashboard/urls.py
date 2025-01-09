from django.urls import path, include
from .views import (
    InternalClientView,
    InternalClientDetailsView,
    InterviewerView,
    InterviewerDetails,
)


urlpatterns = [
    path("client/", include("dashboard.URLs.ClientUrls")),
    path("internal/", include("dashboard.URLs.InternalUrls")),
]
