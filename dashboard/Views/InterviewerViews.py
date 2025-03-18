import datetime
from django.db import transaction
from django.db.models import Count, Q
from django.conf import settings
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import LimitOffsetPagination
from ..serializer import (
    InterviewerAvailabilitySerializer,
    InterviewerRequestSerializer,
    InterviewerDashboardSerializer,
)
from ..models import InterviewerAvailability, Candidate, InternalInterviewer, Interview
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
        today_date = datetime.datetime.now().date()
        interviewer_avi_qs = InterviewerAvailability.objects.filter(
            interviewer=request.user.interviewer, date__gte=today_date
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
            candidate = serializer.validated_data.pop("candidate_obj")
            contexts = []

            for interviewer_obj in InterviewerAvailability.objects.filter(
                pk__in=interviewer_ids, booked_by__isnull=True
            ).select_related("interviewer"):
                schedule_datetime = datetime.datetime.combine(
                    serializer.validated_data.get("date"),
                    serializer.validated_data.get("time"),
                )
                data = f"interviewer_avialability_id:{interviewer_obj.id};candidate_id:{candidate_id};schedule_time:{schedule_datetime};booked_by:{request.user.id};expired_time:{datetime.datetime.now()+datetime.timedelta(hours=1)}"
                accept_data = data + ";action:accept"
                reject_data = data + ";action:reject"
                accept_uid = urlsafe_base64_encode(force_bytes(accept_data))
                reject_uid = urlsafe_base64_encode(force_bytes(reject_data))
                context = {
                    "name": interviewer_obj.interviewer.name,
                    "email": interviewer_obj.interviewer.email,
                    "interview_date": serializer.validated_data["date"],
                    "interview_time": serializer.validated_data["time"],
                    "position": candidate.designation.get_name_display(),
                    "site_domain": settings.SITE_DOMAIN,
                    "accept_link": "/confirmation/{}/".format(accept_uid),
                    "reject_link": "/confirmation/{}/".format(reject_uid),
                    "from_email": settings.EMAIL_HOST_USER,
                }
                contexts.append(context)

            send_email_to_multiple_recipients.delay(
                contexts,
                "Interview Opportunity Available - Confirm Your Availability",
                "interviewer_interview_notification.html",
            )
            candidate.last_scheduled_initiate_time = timezone.now()
            candidate.save()
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


@extend_schema(tags=["Interviewer"])
class InterviewerRequestResponseView(APIView):
    serializer_class = None

    def post(self, request, request_id):
        try:

            try:
                decode_data = force_str(urlsafe_base64_decode(request_id))
                data_parts = decode_data.split(";")
                if len(data_parts) != 6:
                    raise ValueError("Invalid data format")

                (
                    interviewer_availability_id,
                    candidate_id,
                    schedule_time,
                    booked_by,
                    expired_time,
                    action,
                ) = [item.split(":", 1)[1] for item in data_parts]
            except Exception:
                return Response(
                    {"status": "failed", "message": "Invalid Request ID format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            expired_time = datetime.datetime.strptime(
                expired_time, "%Y-%m-%d %H:%M:%S.%f"
            )
            if datetime.datetime.now() > expired_time:
                return Response(
                    {"status": "failed", "message": "Request expired"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            interviewer_availability = InterviewerAvailability.objects.filter(
                pk=interviewer_availability_id
            ).first()
            candidate = Candidate.objects.filter(pk=candidate_id).first()

            if not interviewer_availability or not candidate:
                return Response(
                    {
                        "status": "failed",
                        "message": "Invalid Interviewer or Candidate.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if candidate.status not in ["SCH", "NSCH"]:
                return Response(
                    {"status": "failed", "message": "Invalid request"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if candidate.status == "SCH":
                return Response(
                    {
                        "status": "failed",
                        "message": "Candidate already has a scheduled interview.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            schedule_time = datetime.datetime.strptime(
                schedule_time, "%Y-%m-%d %H:%M:%S"
            )
            schedule_time = timezone.make_aware(schedule_time)

            # To handle multiple interview requests from different clients to the same interviewer scenario
            schedule_time_after_one_hour = schedule_time + datetime.timedelta(hours=1)
            schedule_time_before_one_hour = schedule_time - datetime.timedelta(hours=1)
            if (
                Interview.objects.filter(
                    interviewer=interviewer_availability.interviewer,
                    status="SCH",
                )
                .filter(
                    Q(scheduled_time=schedule_time)
                    | Q(
                        scheduled_time__gte=schedule_time_before_one_hour,
                        scheduled_time__lt=schedule_time,
                    )
                    | Q(
                        scheduled_time__lte=schedule_time_after_one_hour,
                        scheduled_time__gt=schedule_time,
                    )
                )
                .exists()
            ):
                return Response(
                    {
                        "status": "failed",
                        "message": "There must be a 1-hour gap between two consecutive scheduled interviews.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if action == "accept":
                with transaction.atomic():
                    Interview.objects.create(
                        candidate=candidate,
                        interviewer=interviewer_availability.interviewer,
                        status="SCH",
                        scheduled_time=schedule_time,
                        total_score=100,
                    )
                    interviewer_availability.booked_by_id = booked_by
                    interviewer_availability.is_scheduled = True

                    original_start_time = interviewer_availability.start_time
                    original_end_time = interviewer_availability.end_time

                    # updating with the booked time
                    interviewer_availability.start_time = schedule_time.time()
                    interviewer_availability.end_time = (
                        schedule_time + datetime.timedelta(hours=1)
                    ).time()
                    interviewer_availability.save()

                    # creating new available instance for if interviewer is futher available with 1hour before and after time gap
                    original_availability_date = interviewer_availability.date
                    new_slots = []
                    before_slot_end = (
                        schedule_time - datetime.timedelta(hours=1)
                    ).time()
                    before_slot_start = original_start_time
                    before_slot_end_dt = datetime.datetime.combine(
                        original_availability_date, before_slot_end
                    )
                    before_slot_start_dt = datetime.datetime.combine(
                        original_availability_date, before_slot_start
                    )
                    if (
                        before_slot_end_dt - before_slot_start_dt
                    ) >= datetime.timedelta(hours=1):
                        new_slots.append(
                            InterviewerAvailability(
                                interviewer=interviewer_availability.interviewer,
                                date=interviewer_availability.date,
                                start_time=before_slot_start,
                                end_time=before_slot_end,
                                google_calendar_id=interviewer_availability.google_calendar_id,
                            )
                        )
                    after_slot_start = (
                        schedule_time + datetime.timedelta(hours=2)
                    ).time()
                    after_slot_end = original_end_time

                    after_slot_start_dt = datetime.datetime.combine(
                        original_availability_date, after_slot_start
                    )
                    after_slot_end_dt = datetime.datetime.combine(
                        original_availability_date, after_slot_end
                    )
                    if (after_slot_end_dt - after_slot_start_dt) >= datetime.timedelta(
                        hours=1
                    ):
                        new_slots.append(
                            InterviewerAvailability(
                                interviewer=interviewer_availability.interviewer,
                                date=interviewer_availability.date,
                                start_time=after_slot_start,
                                end_time=after_slot_end,
                                google_calendar_id=interviewer_availability.google_calendar_id,
                            )
                        )

                    InterviewerAvailability.objects.bulk_create(new_slots)

                    # sending the confirmation notification
                    interview_date = schedule_time.date().strftime("%d/%m/%Y")
                    interview_time = schedule_time.time().strftime("%H:%M:%S")

                    contexts = [
                        {
                            "name": candidate.name,
                            "position": candidate.designation.name,
                            "company_name": candidate.organization.name,
                            "interview_date": interview_date,
                            "interview_time": interview_time,
                            "interviewer": interviewer_availability.interviewer.name,
                            "email": candidate.email,
                            "template": "interview_confirmation_candidate_notification.html",
                            "subject": f"Interview Scheduled - {candidate.designation.name}",
                            "from_email": settings.EMAIL_HOST_USER,
                        },
                        {
                            "name": interviewer_availability.interviewer.name,
                            "position": candidate.designation.name,
                            "interview_date": interview_date,
                            "interview_time": interview_time,
                            "candidate": candidate.name,
                            "email": interviewer_availability.interviewer.email,
                            "template": "interview_confirmation_interviewer_notification.html",
                            "subject": f"Interview Assigned - {candidate.name}",
                            "from_email": settings.EMAIL_HOST_USER,
                        },
                        {
                            "name": candidate.organization.name,
                            "position": candidate.designation.name,
                            "interview_date": interview_date,
                            "interview_time": interview_time,
                            "candidate": candidate.name,
                            "email": candidate.designation.hiring_manager.user.email,
                            "template": "interview_confirmation_client_notification.html",
                            "subject": f"Interview Scheduled - {candidate.name}",
                            "from_email": settings.EMAIL_HOST_USER,
                        },
                    ]

                    send_email_to_multiple_recipients.delay(
                        contexts,
                        "",
                        "",
                    )

                    return Response(
                        {"status": "success", "message": "Interview Confirmed"},
                        status=status.HTTP_200_OK,
                    )

            return Response(
                {"status": "success", "message": "Interview Rejected"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"status": "failed", "message": f"Error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class InterviewerAcceptedInterviewsView(APIView, LimitOffsetPagination):
    serializer_class = InterviewerDashboardSerializer
    permission_classes = (IsAuthenticated, IsInterviewer)

    def get(self, request):
        accepted_interviews_qs = Interview.objects.filter(
            interviewer=request.user.interviewer, status="SCH"
        ).select_related("candidate", "candidate__designation")
        paginated_queryset = self.paginate_queryset(accepted_interviews_qs, request)
        serializer = self.serializer_class(paginated_queryset, many=True)
        paginated_data = self.get_paginated_response(serializer.data)
        return Response(
            {
                "status": "success",
                "message": "Accepted interviews fetched successfully",
                **paginated_data.data,
            },
            status=status.HTTP_200_OK,
        )


class InterviewerPendingFeedbackView(APIView, LimitOffsetPagination):
    serializer_class = InterviewerDashboardSerializer
    permission_classes = (IsAuthenticated, IsInterviewer)

    def get(self, request):
        pending_feedback_qs = Interview.objects.filter(
            interviewer=request.user.interviewer, status="PENDING_EVAL"
        ).select_related("candidate", "candidate__designation")

        paginated_queryset = self.paginate_queryset(pending_feedback_qs, request)
        serializer = self.serializer_class(paginated_queryset, many=True)
        paginated_data = self.get_paginated_response(serializer.data)
        return Response(
            {
                "status": "success",
                "message": "Pending feedback fetched successfully",
                **paginated_data.data,
            },
            status=status.HTTP_200_OK,
        )


class InterviewerInterviewHistoryView(APIView, LimitOffsetPagination):
    serializer_class = InterviewerDashboardSerializer
    permission_classes = (IsAuthenticated, IsInterviewer)

    def get(self, request):
        interview_history_qs = Interview.objects.filter(
            interviewer=request.user.interviewer,
            status__in=["HREC", "REC", "NREC", "SNREC"],
        ).select_related("candidate", "candidate__designation")

        paginated_queryset = self.paginate_queryset(interview_history_qs, request)
        serializer = self.serializer_class(paginated_queryset, many=True)
        paginated_data = self.get_paginated_response(serializer.data)
        return Response(
            {
                "status": "success",
                "message": "Interview history fetched successfully",
                **paginated_data.data,
            },
            status=status.HTTP_200_OK,
        )
