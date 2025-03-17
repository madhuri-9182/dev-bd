import datetime
from django.utils import timezone
from rest_framework import serializers
from ..models import InterviewerAvailability, Candidate, Interview, Job
from hiringdogbackend.utils import validate_incoming_data


class RecurrenceSerializer(serializers.Serializer):
    frequency = serializers.ChoiceField(
        choices=[
            ("WEEKLY", "Weekly"),
            ("DAILY", "Daily"),
            ("MONTHLY", "Monthly"),
            ("YEARLY", "Yearly"),
            ("HOURLY", "Hourly"),
            ("MINUTELY", "Minutely"),
            ("SECONDLY", "Secondly"),
        ],
        error_messages={
            "invalid_choice": "This is an invalid choice. Valid choices are WEEKLY, DAILY, MONTHLY, YEARLY, HOURLY, MINUTELY, SECONDLY."
        },
    )
    intervals = serializers.IntegerField(min_value=1, max_value=90, required=False)
    count = serializers.IntegerField(min_value=1, max_value=250, required=False)
    until = serializers.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M:%S"], format="%d/%m/%Y %H:%M", required=False
    )
    days = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[
                ("MO", "Monday"),
                ("TU", "Tuesday"),
                ("WE", "Wednesday"),
                ("TH", "Thursday"),
                ("FR", "Friday"),
                ("SA", "Saturday"),
                ("SU", "Sunday"),
            ],
            error_messages={
                "invalid_choice": "This is an invalid choice. Valid choices are MO, TU, WE, TH, FR, SA, SU."
            },
        ),
        required=False,
        min_length=1,
    )
    month_day = serializers.ListField(
        child=serializers.IntegerField(min_value=-31, max_value=31), required=False
    )
    year_day = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=365), required=False
    )

    def validate(self, data):
        frequency = data.get("frequency")
        if data.get("count") and data.get("until"):
            raise serializers.ValidationError(
                {"error": "Count and until date cannot be used simultaneously"}
            )

        invalid_keys = {
            "DAILY": ["byDay", "byMonthDay", "byYearDay"],
            "WEEKLY": ["byMonthDay", "byYearDay"],
            "MONTHLY": ["byYearDay"],
            "YEARLY": ["byMonthDay"],
        }[frequency]

        for key in invalid_keys:
            if data.get(key):
                raise serializers.ValidationError(
                    {"error": f"'{key}' is not applicable for {frequency} frequency."}
                )
        return data


class InterviewerAvailabilitySerializer(serializers.ModelSerializer):
    date = serializers.DateField(
        input_formats=["%d/%m/%Y"], format="%d/%m/%Y", required=False
    )
    start_time = serializers.TimeField(input_formats=["%H:%M"], required=False)
    end_time = serializers.TimeField(input_formats=["%H:%M"], required=False)
    recurrence = RecurrenceSerializer(write_only=True, required=False)

    class Meta:
        model = InterviewerAvailability
        fields = (
            "id",
            "interviewer",
            "date",
            "start_time",
            "end_time",
            "recurrence",
            "is_booked",
            "booked_by",
            "notes",
        )
        read_only_fields = ["interviewer"]

    def validate(self, data):
        interviewer_user = self.context["interviewer_user"]
        required_keys = [
            "date",
            "start_time",
            "end_time",
        ]
        allowed_keys = ["notes", "recurrence"]

        errors = validate_incoming_data(
            self.initial_data,
            required_keys,
            allowed_keys,
            partial=self.partial,
        )

        """ --> commented this for temporary
        if not self.partial and not data.get("recurrence"):
            errors.append(
                {
                    "recurrence": "This field is required.",
                    "schema": {
                        "frequency": "string",
                        "interval": "integer",
                        "count": "integer",
                        "until": "date",
                        "days": "integer",
                        "month_day": "integer",
                        "year_day": "integer",
                    },
                }
            )
        """

        if errors:
            raise serializers.ValidationError({"errors": errors})

        overlapping_slots = InterviewerAvailability.objects.filter(
            interviewer=interviewer_user,
            date=data.get("date"),
            start_time__lt=data.get("end_time"),
            end_time__gt=data.get("start_time"),
        )
        if overlapping_slots.exists():
            errors.setdefault("availability", []).append(
                "Interviewer already available at this date and time."
            )

        if data["date"] < datetime.datetime.now().date():
            errors.setdefault("date", []).append("Invalid date. Date can't in past")

        current_time = datetime.datetime.now().time()
        if data["end_time"] <= data["start_time"]:
            errors.setdefault("end_time", []).append(
                "end_time must be after start_time"
            )
        if data["date"] == datetime.datetime.now().date() and (
            data["start_time"] <= current_time or data["end_time"] <= current_time
        ):
            errors.setdefault("start_time & date_time", []).append(
                "start_time and end_time must be in the future for today"
            )

        if errors:
            raise serializers.ValidationError({"errors": errors})

        data["date"] = datetime.datetime.strptime(str(data["date"]), "%Y-%m-%d").date()

        return data

    def create(self, validated_data):
        validated_data.pop("recurrence", None)
        return super().create(validated_data)


class InterviewerRequestSerializer(serializers.Serializer):
    candidate_id = serializers.IntegerField(min_value=0)
    interviewer_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), min_length=1
    )
    date = serializers.DateField(input_formats=["%d/%m/%Y"])
    time = serializers.TimeField(input_formats=["%H:%M"])

    def validate(self, data):
        request = self.context.get("request")
        errors = {}

        candidate = Candidate.objects.filter(
            organization=request.user.clientuser.organization,
            pk=data.get("candidate_id"),
        ).first()
        if not candidate:
            errors.setdefault("candidate_id", []).append("Invalid candidate_id")

        if candidate.status != "NSCH":
            errors.setdefault("candidate_id", []).append(
                "Candidate is already scheduled and processed"
            )
        if (
            candidate.last_scheduled_initiate_time
            and timezone.now()
            < candidate.last_scheduled_initiate_time + datetime.timedelta(hours=1)
        ):
            errors.setdefault("candidate_id", []).append(
                "Can't reinitiate the scheduling for 1 hour. Previous scheduling is in progress"
            )

        valid_interviewer_ids = set(
            InterviewerAvailability.objects.filter(
                pk__in=data.get("interviewer_ids")
            ).values_list("id", flat=True)
        )
        for index, interviewer_id in enumerate(data.get("interviewer_ids", [])):
            if interviewer_id not in valid_interviewer_ids:
                errors.setdefault("interviewer_ids", []).append(
                    {index: ["interviewer_id is invalid"]}
                )

        if errors:
            raise serializers.ValidationError({"errors": errors})

        data["candidate_obj"] = candidate

        return data


class InterviewerJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ("id", "name", "other_details")


class InterviewerCandidateSerializer(serializers.ModelSerializer):
    designation = InterviewerJobSerializer(read_only=True)

    class Meta:
        model = Candidate
        fields = (
            "id",
            "name",
            "designation",
            "specialization",
            "year",
            "month",
            "company",
            "cv",
        )


class InterviewerDashboardSerializer(serializers.ModelSerializer):
    candidate = InterviewerCandidateSerializer(read_only=True)
    scheduled_time = serializers.DateTimeField(format="%d/%m/%Y %H:%M:%S")

    class Meta:
        model = Interview
        fields = ("id", "candidate", "scheduled_time")
