from django.urls import path
from .views import ClientUserView

urlpatterns = [path("client-user/", ClientUserView.as_view(), name="client-user")]
