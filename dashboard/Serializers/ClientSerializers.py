from rest_framework import serializers
from dashboard.models import ClientUser
from hiringdogbackend.utils import validate_incoming_data


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
            raise serializers.ValidationError({"error": errors})

        return data
