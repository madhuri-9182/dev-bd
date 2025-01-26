import datetime
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import LimitOffsetPagination
from ..serializer import InterviewerAvailabilitySerializer
from ..models import InterviewerAvailability
from core.permissions import IsInterviewer
from core.models import OAuthToken
from externals.google.google_calendar import GoogleCalendar


@extend_schema(tags=["Interviewer"])
class InterviewerAvailabilityView(APIView, LimitOffsetPagination):
    serializer_class = InterviewerAvailabilitySerializer
    permission_classes = [IsAuthenticated, IsInterviewer]

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"interviewer_user": request.user.interviewer}
        )

        try:
            oauth_obj = OAuthToken.objects.get(user=request.user)
        except OAuthToken.DoesNotExist:
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid Request. Please give the calendar permission.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if serializer.is_valid():
            with transaction.atomic():
                try:
                    interviewer = serializer.save(interviewer=request.user.interviewer)

                    combine_start_datetime = datetime.datetime.combine(
                        interviewer.date, interviewer.start_time
                    )
                    combine_end_datetime = datetime.datetime.combine(
                        interviewer.date, interviewer.end_time
                    )

                    iso_format_start_time = combine_start_datetime.isoformat()
                    iso_format_end_time = combine_end_datetime.isoformat()

                    recurrence = serializer.validated_data.get("recurrence")
                    calender = GoogleCalendar()
                    event_details = {
                        "summary": "Interview Available Time",
                        # "location": "123 Main St, Virtual",
                        # "description": "Discussing project milestones and deadlines.",
                        "start": {
                            "dateTime": iso_format_start_time,
                            "timeZone": "Asia/Kolkata",
                        },
                        "end": {
                            "dateTime": iso_format_end_time,
                            "timeZone": "Asia/Kolkata",
                        },
                        # "attendees": [
                        #     {"email": "attendee1@example.com"},
                        #     {"email": "attendee2@example.com"},
                        # ],
                        # "reminders": {
                        #     "useDefault": False,
                        #     "overrides": [
                        #         {"method": "email", "minutes": 24 * 60},  # 1 day before
                        #         {"method": "popup", "minutes": 10},  # 10 minutes before
                        #     ],
                        # },
                    }
                    if recurrence:
                        event_details["recurrence"] = [
                            calender.generate_rrule_string(recurrence)
                        ]

                    event = calender.create_event(
                        access_token=oauth_obj.access_token,
                        refresh_token=oauth_obj.refresh_token,
                        user=request.user,
                        event_details=event_details,
                    )
                    interviewer.google_calendar_id = event.pop("id", "")
                    interviewer.save()

                except Exception as e:
                    transaction.set_rollback(True)
                    return Response(
                        {
                            "status": "failed",
                            "message": "Something went wrong while creating the event.",
                            "error": str(e),
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            return Response(
                {
                    "status": "success",
                    "message": "Interviewer Availability added successfully.",
                    "data": serializer.data,
                    "event_details": event,
                },
                status=status.HTTP_201_CREATED,
            )

        custom_error = serializer.errors.pop("errors", None)
        return Response(
            {
                "status": "failed",
                "message": "Invalid data.",
                "errors": serializer.errors if not custom_error else custom_error,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def get(self, request):
        interviewer_avi_qs = InterviewerAvailability.objects.filter(
            interviewer=request.user.interviewer
        )
        if not interviewer_avi_qs.exists():
            return Response(
                {"status": "failed", "message": "There is no availability for you."},
                status=status.HTTP_404_NOT_FOUND,
            )

        paginated_queryset = self.paginate_queryset(interviewer_avi_qs, request, self)
        serializer = self.serializer_class(paginated_queryset, many=True)
        paginated_response = self.get_paginated_response(serializer.data)

        return_response = {
            "status": "success",
            "message": "Successfully retrieve the availability.",
            **paginated_response.data,
        }

        return Response(
            return_response,
            status=status.HTTP_200_OK,
        )
