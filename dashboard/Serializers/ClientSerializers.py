from rest_framework import serializers
from organizations.utils import create_organization
from phonenumber_field.serializerfields import PhoneNumberField
from core.models import User, Role
from ..models import (
    ClientUser,
    InternalClient,
    ClientPointOfContact,
    InternalInterviewer,
)
from hiringdogbackend.utils import (
    validate_incoming_data,
    get_random_password,
    is_valid_gstin,
    is_valid_pan,
    get_boolean,
)


class ClientUserSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d/%m/%Y", read_only=True)
    job_assigned = serializers.CharField()

    class Meta:
        model = ClientUser
        fields = (
            "id",
            "user",
            "name",
            "email",
            "user_type",
            "job_assigned",
            "created_at",
        )

    def validate(self, data):
        errors = []
        if not self.partial:
            errors = validate_incoming_data(
                data, ["name", "email", "user_type", "job_assigned"]
            )

        valid_job_choices = {"sde3", "pe", "sde2", "devops1", "em", "sdet2", "sdet1"}
        job_assigned = data.get("job_assigned")

        if job_assigned and job_assigned not in valid_job_choices:
            errors.append(
                {
                    "job_assigned": "Invalid choice. Choices are sde3, pe, sde2, devops1, em, sdet2, sdet1."
                }
            )

        if errors:
            raise serializers.ValidationError({"errors": errors})

        return data
