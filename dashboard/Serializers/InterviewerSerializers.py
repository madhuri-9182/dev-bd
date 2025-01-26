import datetime
from rest_framework import serializers
from ..models import InterviewerAvailability
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
    intervals = serializers.IntegerField(min_value=1, max_value=90)
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
            errors.append(
                {"availability": "Interviewer already available at this date and time."}
            )

        if data["date"] < datetime.datetime.now().date():
            errors.append({"date": "Invalid date. Date can't in past"})

        current_time = datetime.datetime.now().time()
        if data["end_time"] <= data["start_time"]:
            errors.append({"end_time": "end_time must be after start_time"})
        if data["start_time"] <= current_time or data["end_time"] <= current_time:
            errors.append(
                {
                    "start_time & date_time": "start_time and end_time must be in the future for today"
                }
            )

        if errors:
            raise serializers.ValidationError({"errors": errors})

        data["date"] = datetime.datetime.strptime(str(data["date"]), "%Y-%m-%d").date()

        return data

    def create(self, validated_data):
        validated_data.pop("recurrence", None)
        return super().create(validated_data)
