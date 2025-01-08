from rest_framework import serializers
from django.conf import settings
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from core.models import User, Role
from ..models import ClientUser
from phonenumber_field.serializerfields import PhoneNumberField
from hiringdogbackend.utils import (
    validate_incoming_data,
    get_random_password,
    check_for_email_and_phone_uniqueness,
)
from ..tasks import send_mail


class ClientUserDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "role")


class ClientUserSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d/%m/%Y", read_only=True)
    user = ClientUserDetailsSerializer(read_only=True)
    email = serializers.EmailField(write_only=True, required=False)
    role = serializers.ChoiceField(
        choices=Role.choices, write_only=True, required=False
    )
    phone = PhoneNumberField(write_only=True, required=False)

    class Meta:
        model = ClientUser
        fields = (
            "id",
            "user",
            "name",
            "email",
            "phone",
            "role",
            "designation",
            "created_at",
        )
        read_only_fields = ["created_at"]

    def run_validation(self, data=...):
        email = data.get("email")
        phone = data.get("phone")
        role = data.get("role")
        errors = check_for_email_and_phone_uniqueness(email, phone, User)
        if role and role not in Role.values:
            errors.append({"role": "Invalid role type."})
        if errors:
            raise serializers.ValidationError({"errors": errors})
        return super().run_validation(data)

    def validate(self, data):
        errors = validate_incoming_data(
            self.initial_data,
            ["name", "email", "role", "designation", "phone"],
            partial=self.partial,
        )

        if errors:
            raise serializers.ValidationError({"errors": errors})

        return data

    def create(self, validated_data):
        email = validated_data.pop("email", None)
        phone_number = validated_data.pop("phone", None)
        user_role = validated_data.pop("role", None)
        organization = validated_data.get("organization")
        temp_password = get_random_password()
        current_user = self.context.get("user")

        with transaction.atomic():
            user = User.objects.create_user(
                email=email, phone=phone_number, password=temp_password, role=user_role
            )
            client_user = ClientUser.objects.create(user=user, **validated_data)
            data = f"user:{current_user.email};invitee-email:{email}"
            uid = urlsafe_base64_encode(force_bytes(data))
            send_mail.delay(
                email=email,
                subject=f"You're Invited to Join {organization.name} on Hiring Dog",
                template="invitation.html",
                invited_name=validated_data.get("name"),
                user_name=current_user.clientuser.name,
                user_email=current_user.email,
                org_name=organization.name,
                password=temp_password,
                login_url=settings.LOGIN_URL,
                activation_url=f"/client/client-user-activate/{uid}/",
                site_domain=settings.SITE_DOMAIN,
            )
        return client_user

    def update(self, instance, validated_data):
        email = validated_data.pop("email", None)
        phone_number = validated_data.pop("phone", None)
        role = validated_data.pop("role", None)

        updated_client_user = super().update(instance, validated_data)

        if email:
            updated_client_user.user.email = email
        if phone_number:
            updated_client_user.user.phone = phone_number
        if role:
            updated_client_user.user.role = role

        updated_client_user.user.save()
        return updated_client_user
