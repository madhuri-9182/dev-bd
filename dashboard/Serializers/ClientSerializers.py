from datetime import datetime
from rest_framework import serializers
from django.conf import settings
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from core.models import User, Role
from ..models import ClientUser, Job
from phonenumber_field.serializerfields import PhoneNumberField
from hiringdogbackend.utils import (
    validate_incoming_data,
    get_random_password,
    check_for_email_and_phone_uniqueness,
    validate_attachment,
    validate_json,
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
        name = validated_data.get("name")
        organization = validated_data.get("organization")
        temp_password = get_random_password()
        current_user = self.context.get("user")

        with transaction.atomic():
            user = User.objects.create_user(
                email=email, phone=phone_number, password=temp_password, role=user_role
            )
            user.profile.name = name
            user.profile.organization = organization
            user.profile.save()
            client_user = ClientUser.objects.create(user=user, **validated_data)
            data = f"user:{current_user.email};invitee-email:{email}"
            uid = urlsafe_base64_encode(force_bytes(data))
            send_mail.delay(
                email=email,
                subject=f"You're Invited to Join {organization.name} on Hiring Dog",
                template="invitation.html",
                invited_name=name,
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
        name = validated_data.get("name")

        updated_client_user = super().update(instance, validated_data)

        if email:
            updated_client_user.user.email = email
        if phone_number:
            updated_client_user.user.phone = phone_number
        if role:
            updated_client_user.user.role = role
        if name:
            updated_client_user.user.profile.name = name
            updated_client_user.user.profile.save()

        updated_client_user.user.save()
        return updated_client_user


class JobClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientUser
        fields = ("id", "name")


class JobSerializer(serializers.ModelSerializer):
    client = JobClientSerializer(read_only=True)
    hiring_manager = JobClientSerializer(read_only=True)
    recruiter_id = serializers.IntegerField(write_only=True, required=False)
    hiring_manager_id = serializers.IntegerField(write_only=True, required=False)
    interview_time = serializers.TimeField(input_formats=["%H:%M:%S"])

    class Meta:
        model = Job
        fields = (
            "id",
            "client",
            "name",
            "job_id",
            "hiring_manager",
            "recruiter_id",
            "hiring_manager_id",
            "total_positions",
            "job_description_file",
            "mandatory_skills",
            "interview_time",
            "other_details",
            "reason_for_archived",
        )

    def run_validation(self, data=...):
        valid_reasons = ["PF", "POH", "OTH"]
        reason = data.get("reason_for_archived")

        if reason and reason not in valid_reasons:
            raise serializers.ValidationError(
                {
                    "errors": {
                        "reason_for_archived": "Invalid reason_for_archived value."
                    }
                }
            )

        return super().run_validation(data)

    def validate(self, data):
        org = self.context["org"]
        required_keys = [
            "name",
            "job_id",
            "hiring_manager_id",
            "recruiter_id",
            "total_positions",
            "job_description_file",
            "mandatory_skills",
        ]
        allowed_keys = [
            "reason_for_archived",
            "other_details",
            "interview_time",
        ]

        errors = validate_incoming_data(
            self.initial_data,
            required_keys,
            allowed_keys,
            form=True,
            partial=self.partial,
        )

        if errors:
            raise serializers.ValidationError({"errors": errors})

        hiring_manager_id = data.get("hiring_manager_id")
        recruiter_id = data.get("recruiter_id")

        client_user_ids = set(
            ClientUser.objects.filter(organization=org).values_list("id", flat=True)
        )
        if not self.partial and recruiter_id not in client_user_ids:
            errors.append({"recruiter_id": "Invalid recruiter_id"})
        if not self.partial and hiring_manager_id not in client_user_ids:
            errors.append({"hiring_manager_id": "Invalid hiring_manager_id"})
        if not self.partial and hiring_manager_id == recruiter_id:
            errors.append(
                {
                    "conflict_error": "hiring_manager_id and recruiter_id cannot be the same."
                }
            )

        if not self.partial and not (0 <= data.get("total_positions") < 100):
            errors.append({"total_positions": "Invalid total_positions"})

        if data.get("interview_time"):
            try:
                datetime.strptime(str(data["interview_time"]), "%H:%M:%S")
            except (ValueError, TypeError):
                errors.append(
                    {
                        "interview_time": "Invalid interview time. Format should be %H:%M:%S"
                    }
                )

        if data.get("job_description_file"):
            errors += validate_attachment(
                "job_description_file",
                data["job_description_file"],
                ["doc", "docx", "pdf"],
                max_size_mb=5,
            )

        if data.get("other_details") is not None:
            schema = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "details": {
                            "type": "string",
                            "minLength": 1,
                        },
                        "time": {
                            "type": "string",
                            "pattern": "^\\d+min$",
                        },
                        "guidelines": {
                            "type": "string",
                            "minLength": 1,
                        },
                    },
                    "required": ["details", "time", "guidelines"],
                },
            }
            errors += validate_json(data["other_details"], "other_details", schema)

        if errors:
            raise serializers.ValidationError({"errors": errors})
        return data

    def create(self, validated_data):
        validated_data["client_id"] = validated_data.pop("recruiter_id")
        return super().create(validated_data)
