from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import password_validation, authenticate
from django.contrib.auth.hashers import check_password
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import InvalidToken
from django_rest_passwordreset import models
from django_rest_passwordreset.serializers import (
    PasswordTokenSerializer,
)
from .models import User
from hiringdogbackend.utils import validate_incoming_data


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "id": user.id,
        "role": user.role,
    }


class UserSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True, required=False)
    name = serializers.CharField(max_length=100, required=False)

    class Meta:
        model = User
        fields = ("name", "email", "password", "confirm_password", "phone")
        extra_kwargs = {
            "email": {"required": False},
            "password": {"required": False},
            "phone": {"required": False},
        }

    def validate(self, data):
        errors = validate_incoming_data(data, list(self.fields.keys()))

        if errors:
            raise serializers.ValidationError({"errors": errors})

        password = data.get("password")
        confirm_password = data.get("confirm_password")

        if password != confirm_password:
            raise serializers.ValidationError(
                {"errors": "Password and confirm_password are not the same."}
            )
        password_validation.validate_password(password)
        return data

    def create(self, validated_data):
        validated_data.pop("confirm_password", None)
        name = validated_data.pop("name", None)
        user = User.objects.create_user(**validated_data)
        user.profile.name = name
        user.profile.save()
        return user


class UserLoginSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()

    def validate(self, data):
        request = self.context["request"]
        errors = validate_incoming_data(
            self.initial_data, ["email", "password"], ["csrfmiddlewaretoken"]
        )

        if errors:
            raise serializers.ValidationError({"errors": errors})
        user = authenticate(request, **data)
        errors = {}

        if not user:
            errors.setdefault("credentials", []).append("Invalid credentials")

        if user and hasattr(user, "clientuser"):
            client_user = user.clientuser
            if (
                user.role not in ["client_admin", "client_owner"]
                and client_user.status != "ACT"
            ):
                errors.setdefault("account", []).append(
                    "Your account is not activated. Please check your organization invitation email for activation link."
                )

        if errors:
            raise serializers.ValidationError({"errors": errors})

        tokens = get_tokens_for_user(user)
        data["tokens"] = tokens

        return data

    class Meta:
        model = User
        fields = ("email", "password")
        extra_kwargs = {
            "email": {"required": False},
            "password": {"write_only": True, "required": False},
        }


class CookieTokenRefreshSerializer(TokenRefreshSerializer):
    refresh = None

    def validate(self, data):
        data["refresh"] = self.context.get("request").COOKIES.get("refresh_token")

        if data["refresh"]:
            return super().validate(data)

        raise ValidationError({"errors": "No valid token found in cookie"})


class ResetPasswordConfirmSerailizer(PasswordTokenSerializer):
    def validate(self, data):
        try:
            reset_password_token = get_object_or_404(
                models.ResetPasswordToken, key=data.get("token")
            )
        except (
            TypeError,
            ValueError,
            ValidationError,
            Http404,
            models.ResetPasswordToken.DoesNotExist,
        ):
            raise Http404(
                _("The OTP password entered is not valid. Please check and try again.")
            )

        if check_password(data.get("password"), reset_password_token.user.password):
            raise ValidationError(
                {
                    "errors": "The new password cannot be the same as your current password. Please choose a different password."
                }
            )

        return super().validate(data)
