from django.db.models import Subquery
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    OutstandingToken,
    BlacklistedToken,
)
from rest_framework.permissions import IsAuthenticated
from django_rest_passwordreset.views import (
    ResetPasswordRequestToken,
    ResetPasswordConfirm,
)
from .serializer import (
    UserSerializer,
    UserLoginSerializer,
    CookieTokenRefreshSerializer,
    ResetPasswordConfirmSerailizer,
)


class UserSignupView(APIView):
    serializer_class = UserSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"status": "success", "message": "User signup sucessfully."},
            status=status.HTTP_201_CREATED,
        )


class UserLoginView(APIView):
    serializer_class = UserLoginSerializer

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        data = {**serializer.data, **serializer.validated_data.get("tokens")}

        response = Response(
            {
                "status": "success",
                "message": "Login successful.",
                "data": data,
            },
            status=status.HTTP_200_OK,
        )

        refresh_token = data.get("refresh")
        if refresh_token:
            cookie_max_age = 3600 * 24 * 15
            response.set_cookie(
                "refresh_token",
                refresh_token,
                max_age=cookie_max_age,
                httponly=True,
            )
            del data["refresh"]
        return response


class CookieTokenRefreshView(TokenRefreshView):

    def finalize_response(self, request, response, *args, **kwargs):
        if response.data.get("refresh"):
            cookie_max_age = 3600 * 24 * 15
            response.set_cookie(
                "refresh_token",
                response.data["refresh"],
                max_age=cookie_max_age,
                httponly=True,
            )
            del response.data["refresh"]
        return super().finalize_response(request, response, *args, **kwargs)

    serializer_class = CookieTokenRefreshSerializer


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        refresh = request.COOKIES.get("refresh_token")
        if not refresh:
            return Response(
                {"status": "fail", "message": "Invalid request"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            refresh_obj = RefreshToken(refresh)
            refresh_obj.blacklist()
        except TokenError:
            return Response(
                {"status": "fail", "message": "Token errors"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"status": "success", "message": "Logout successful"},
            status=status.HTTP_205_RESET_CONTENT,
        )

    def finalize_response(self, request, response, *args, **kwargs):
        response.delete_cookie("refresh_token")
        return super().finalize_response(request, response, *args, **kwargs)


class LogoutAllView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        user = request.user
        outstanding_tokens = OutstandingToken.objects.filter(user=user).exclude(
            id__in=BlacklistedToken.objects.filter(token__user=user).values("token_id")
        )
        blacklisted_token_obj = [
            BlacklistedToken(token=token) for token in outstanding_tokens
        ]
        BlacklistedToken.objects.bulk_create(blacklisted_token_obj)

        return Response(
            {"status": "success", "message": "Logout sucessfull for all session"},
            status=status.HTTP_200_OK,
        )

    def finalize_response(self, request, response, *args, **kwargs):
        response.delete_cookie("refresh_token")
        return super().finalize_response(request, response, *args, **kwargs)


class PasswordResetView(ResetPasswordRequestToken):
    def finalize_response(self, request, response, *args, **kwargs):
        data = response.data
        if response.status_code == 200:
            data["status"] = "success"
            data["message"] = (
                "If an account with the provided email exists, a password reset link has been sent. Please check your inbox to proceed."
            )
        else:
            data["status"] = "failed"
            data["message"] = "Token creation failed"
            if data.get("detail"):
                data["errors"] = data["detail"]
                del data["detail"]
        return super().finalize_response(request, response, *args, **kwargs)


class PasswordResetConfirmView(ResetPasswordConfirm):
    serializer_class = ResetPasswordConfirmSerailizer

    def finalize_response(self, request, response, *args, **kwargs):
        data = response.data
        if response.status_code == 200:
            data["status"] = "success"
            data["message"] = (
                "Your password has been reset successfully. You can now log in with your new credentials."
            )
        else:
            data["status"] = "failed"
            data["message"] = "Password reset failed. Please try again."
            if data.get("detail"):
                data["errors"] = [data["detail"]]
                del data["detail"]
        return super().finalize_response(request, response, *args, **kwargs)
