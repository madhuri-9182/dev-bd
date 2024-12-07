from django.urls import path
from .views import (
    UserSignupView,
    UserLoginView,
    CookieTokenRefreshView,
    LogoutView,
    LogoutAllView,
    PasswordResetView,
    PasswordResetConfirmView,
)

urlpatterns = [
    path("refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("login/", UserLoginView.as_view(), name="user_login"),
    path("signup/", UserSignupView.as_view(), name="user_signup"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("logout-all/", LogoutAllView.as_view(), name="logout-all"),
    path("password_reset/", PasswordResetView.as_view(), name="password_reset_token"),
    path(
        "password_reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]
