import datetime
from django.db import transaction
from django.conf import settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import LimitOffsetPagination
from ..serializer import InterviewerAvailabilitySerializer, InterviewerRequestSerializer
from ..models import InterviewerAvailability, Candidate
from ..tasks import send_email_to_multiple_recipients
from core.permissions import (
    IsInterviewer,
    IsClientAdmin,
    IsClientUser,
    IsClientOwner,
    IsAgency,
)
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


@extend_schema(tags=["Interviewer"])
class InterviewerReqeustView(APIView):
    serializer_class = InterviewerRequestSerializer
    permission_classes = [
        IsAuthenticated,
        IsClientUser | IsClientAdmin | IsClientOwner | IsAgency,
    ]

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            candidate_id = serializer.validated_data["candidate_id"]
            interviewer_ids = serializer.validated_data["interviewer_ids"]
            candidate = Candidate.objects.filter(pk=candidate_id).first()
            contexts = []

            for interviewer_obj in InterviewerAvailability.objects.filter(
                pk__in=interviewer_ids, booked_by__isnull=True
            ).select_related("interviewer"):
                data = f"interviewer_id:{interviewer_obj.interviewer.id};candidate_id:{candidate_id}:"
                uid = urlsafe_base64_encode(force_bytes(data))
                context = {
                    "name": interviewer_obj.interviewer.name,
                    "email": interviewer_obj.interviewer.email,
                    "interview_date": serializer.validated_data["date"],
                    "interview_time": serializer.validated_data["time"],
                    "position": candidate.designation.get_name_display(),
                    "site_domain": settings.SITE_DOMAIN,
                    "link": "/confirmation/{}/".format(uid),
                }
                contexts.append(context)

            send_email_to_multiple_recipients.delay(
                contexts,
                "Interview Opportunity Available - Confirm Your Availability",
                "interviewer_interview_notification.html",
            )
            return Response(
                {
                    "status": "success",
                    "message": "Interviewers notified successfully progress.",
                },
                status=status.HTTP_200_OK,
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
