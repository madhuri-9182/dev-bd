from django.urls import path
from .views import  ClientUserView, InternalClientView, InternalClientDetailsView, ClientPointOfContactView, ClientPointOfContactDetailsView, InterviewerView ,InterviewerDetails
            


urlpatterns =[
    path("client-user/", ClientUserView.as_view(), name="client-user"),
    path("internal-client/", InternalClientView.as_view(), name="internal-client"),
    path("internal-client/<int:pk>/",InternalClientDetailsView.as_view(),name="internal-client-details"),
    path("client-point-of-contact/<int:client_id>/", ClientPointOfContactView.as_view(), name="client-point-of-contact"),
    path("client-point-of-contact/<int:client_id>/contact-id/<int:contact_id>/", ClientPointOfContactDetailsView.as_view(), name="client-point-of-contact-details"),
    path("inter-viewer/", InterviewerView.as_view(), name="inter-viewer"),
    path("inter-viewer/<int:pk>/",InterviewerDetails.as_view(), name="inter-viewer-details")
]
