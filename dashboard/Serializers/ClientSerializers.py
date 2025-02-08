import json
from datetime import datetime
from rest_framework import serializers
from django.conf import settings
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from core.models import User, Role
from ..models import ClientUser, Job, Candidate
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


class ClientJobAssignedDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ("id", "name")


class ClientUserSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d/%m/%Y", read_only=True)
    user = ClientUserDetailsSerializer(read_only=True)
    email = serializers.EmailField(write_only=True, required=False)
    role = serializers.ChoiceField(
        choices=Role.choices, write_only=True, required=False
    )
    phone = PhoneNumberField(write_only=True, required=False)
    job_assigned = serializers.ListField(
        child=serializers.IntegerField(), min_length=1, required=False, write_only=True
    )
    assigned_jobs = ClientJobAssignedDetailsSerializer(
        read_only=True, many=True, source="jobs"
    )
    accessibility = serializers.ChoiceField(
        choices=ClientUser.ACCESSIBILITY_CHOICES,
        error_messages={
            "invalid_choice": f"This is an invalid choice. Valid choices are {', '.join([f'{key}({value})' for key, value in ClientUser.ACCESSIBILITY_CHOICES])}"
        },
        required=False,
    )

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
            "job_assigned",
            "assigned_jobs",
            "created_at",
            "accessibility",
        )
        read_only_fields = ["created_at"]

    def run_validation(self, data=...):
        email = data.get("email")
        phone_number = data.get("phone")
        role = data.get("role")
        errors = check_for_email_and_phone_uniqueness(email, phone_number, User)
        if role and role not in ("client_user", "client_admin", "agency"):
            errors.append({"role": "Invalid role type."})
        if errors:
            raise serializers.ValidationError({"errors": errors})
        return super().run_validation(data)

    def validate(self, data):
        errors = validate_incoming_data(
            self.initial_data,
            [
                "name",
                "email",
                "role",
                "designation",
                "phone",
                "accessibility",
            ],
            allowed_keys=["job_assigned"],
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
        job_assigned = validated_data.pop("job_assigned", None)
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
            if job_assigned:
                job_qs = Job.objects.filter(pk__in=job_assigned)
                client_user.jobs.add(*job_qs)

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
        job_assigned = validated_data.pop("job_assigned", None)

        updated_client_user = super().update(instance, validated_data)

        if job_assigned:
            jobs_qs = Job.objects.filter(pk__in=job_assigned)
            updated_client_user.jobs.set(jobs_qs)

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
    clients = JobClientSerializer(read_only=True, many=True)
    hiring_manager = JobClientSerializer(read_only=True)
    recruiter_ids = serializers.CharField(write_only=True, required=False)
    hiring_manager_id = serializers.IntegerField(write_only=True, required=False)
    interview_time = serializers.TimeField(input_formats=["%H:%M:%S"], required=False)

    class Meta:
        model = Job
        fields = (
            "id",
            "clients",
            "name",
            "job_id",
            "hiring_manager",
            "recruiter_ids",
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
                        "reason_for_archived": ["Invalid reason_for_archived value."]
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
            "recruiter_ids",
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
            original_data=data,
            form=True,
            partial=self.partial,
        )
        if errors:
            raise serializers.ValidationError({"errors": errors})

        hiring_manager_id = data.get("hiring_manager_id")
        recruiter_ids = data.get("recruiter_ids")

        client_user_ids = set(
            ClientUser.objects.filter(organization=org).values_list("id", flat=True)
        )
        if recruiter_ids:
            try:
                recruiter_ids = set(json.loads(recruiter_ids))
                if not recruiter_ids.issubset(client_user_ids):
                    errors.setdefault("recruiter_ids", []).append(
                        f"Invalid recruiter_ids(clientuser_ids): {recruiter_ids - client_user_ids}"
                    )
            except (json.JSONDecodeError, ValueError, TypeError):
                errors.setdefault("recruiter_ids", []).append(
                    "Invalid data format. It should be a list of integers."
                )

        if hiring_manager_id and hiring_manager_id not in client_user_ids:
            errors.setdefault("hiring_manager_id", []).append(
                "Invalid hiring_manager_id"
            )
        if (
            hiring_manager_id
            and isinstance(recruiter_ids, list)
            and hiring_manager_id in recruiter_ids
        ):
            errors.setdefault("conflict_error", []).append(
                "hiring_manager_id and recruiter_id cannot be the same."
            )

        if data.get("total_positions") and not (0 <= data.get("total_positions") < 100):
            errors.setdefault("total_positions", []).append("Invalid total_positions")

        if data.get("interview_time"):
            try:
                datetime.strptime(str(data["interview_time"]), "%H:%M:%S")
            except (ValueError, TypeError):
                errors.setdefault("interview_time", []).append(
                    "Invalid interview time. Format should be %H:%M:%S"
                )

        if data.get("job_description_file"):
            error = validate_attachment(
                "job_description_file",
                data["job_description_file"],
                ["doc", "docx", "pdf"],
                max_size_mb=5,
            )
            if error:
                errors.update(error)

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
            errors.update(validate_json(data["other_details"], "other_details", schema))

        if errors:
            raise serializers.ValidationError({"errors": errors})
        data["recruiter_ids"] = recruiter_ids
        return data

    def create(self, validated_data):
        recruiter_ids = validated_data.pop("recruiter_ids")
        job = super().create(validated_data)
        for recruiter_id in recruiter_ids:
            job.clients.add(recruiter_id)
        return job

    def update(self, instance, validated_data):
        recruiter_ids = validated_data.pop("recruiter_ids", None)
        job = super().update(instance, validated_data)
        if recruiter_ids is not None:
            job.clients.set(recruiter_ids)
        return job


class CandidateDesignationDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ("id", "name")


class CandidateSerializer(serializers.ModelSerializer):
    designation = CandidateDesignationDetailSerializer(read_only=True)
    gender = serializers.ChoiceField(
        choices=Candidate.GENDER_CHOICES,
        error_messages={
            "invalid_choice": f"This is an invalid choice. Valid choices are {', '.join([f'{key}({value})' for key, value in Candidate.GENDER_CHOICES])}"
        },
        required=False,
    )
    source = serializers.ChoiceField(
        choices=Candidate.SOURCE_CHOICES,
        error_messages={
            "invalid_choice": f"This is an invalid choice. Valid choices are {', '.join([f'{key}({value})' for key, value in Candidate.SOURCE_CHOICES])}"
        },
        required=False,
    )
    status = serializers.ChoiceField(
        choices=Candidate.STATUS_CHOICES,
        error_messages={
            "invalid_choice": f"This is an invalid choice. Valid choices are {', '.join([f'{key}({value})' for key, value in Candidate.STATUS_CHOICES])}"
        },
        required=False,
    )
    final_selection_status = serializers.ChoiceField(
        choices=Candidate.FINAL_SELECTION_STATUS_CHOICES,
        error_messages={
            "invalid_choice": f"This is an invalid choice. Valid choices are {', '.join([f'{key}({value})' for key, value in Candidate.FINAL_SELECTION_STATUS_CHOICES])}"
        },
        required=False,
    )
    reason_for_dropping = serializers.ChoiceField(
        choices=Candidate.REASON_FOR_DROPPING_CHOICES,
        error_messages={
            "invalid_choice": f"This is an invalid choice. Valid choices are {', '.join([f'{key}({value})' for key, value in Candidate.REASON_FOR_DROPPING_CHOICES])}"
        },
        required=False,
    )
    job_id = serializers.IntegerField(required=False, write_only=True)

    class Meta:
        model = Candidate
        fields = (
            "id",
            "name",
            "designation",
            "source",
            "year",
            "month",
            "cv",
            "status",
            "gender",
            "score",
            "total_score",
            "final_selection_status",
            "email",
            "phone",
            "company",
            "specialization",
            "remark",
            "reason_for_dropping",
            "job_id",
        )
        read_only_fields = ["designation"]

    def validate(self, data):
        request = self.context.get("request")
        required_keys = [
            "name",
            "year",
            "month",
            "phone",
            "email",
            "company",
            "job_id",
            "source",
            "cv",
            "specialization",
            "gender",
        ]
        allowed_keys = [
            "status",
            "final_selection_status",
            "reason_for_dropping",
            "remark",
        ]

        errors = validate_incoming_data(
            self.initial_data,
            required_keys,
            allowed_keys,
            original_data=data,
            form=True,
        )

        if errors:
            raise serializers.ValidationError({"errors": errors})

        if not Job.objects.filter(
            pk=data.get("job_id"),
            client__organization=request.user.clientuser.organization,
        ).exists():
            errors.setdefault("job_id", []).append("Invalid job_id")

        if data.get("cv"):
            errors.update(validate_attachment("cv", data.get("cv"), ["pdf", "docx"], 5))
        if errors:
            raise serializers.ValidationError({"errors": errors})

        return data
