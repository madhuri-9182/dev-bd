from celery import group
from celery.result import AsyncResult
from datetime import datetime, timedelta
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.db import transaction
from django.db.models import Q, F, ExpressionWrapper, DurationField, Count
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from ..models import (
    ClientUser,
    Job,
    Candidate,
    EngagementTemplates,
    InterviewerAvailability,
    Engagement,
    EngagementOperation,
)
from ..serializer import (
    ClientUserSerializer,
    JobSerializer,
    CandidateSerializer,
    EngagementTemplateSerializer,
    EngagementSerializer,
    EngagementOperationSerializer,
)
from ..permissions import CanDeleteUpdateUser, UserRoleDeleteUpdateClientData
from externals.parser.resume_parser import ResumerParser
from externals.parser.resumeparser2 import process_resume
from core.permissions import (
    IsClientAdmin,
    IsClientOwner,
    IsClientUser,
    IsAgency,
    HasRole,
    IsSuperAdmin,
)
from core.models import Role
from hiringdogbackend.utils import validate_attachment
import tempfile
import os
from django.core.files.storage import default_storage
from ..tasks import send_schedule_engagement_email


@extend_schema(tags=["Client"])
class ClientUserView(APIView, LimitOffsetPagination):
    serializer_class = ClientUserSerializer
    permission_classes = [IsAuthenticated, HasRole, CanDeleteUpdateUser]
    roles_mapping = {
        "GET": [Role.CLIENT_ADMIN, Role.CLIENT_OWNER, Role.CLIENT_USER, Role.AGENCY],
        "POST": [Role.CLIENT_ADMIN, Role.CLIENT_OWNER],
        "PATCH": [Role.CLIENT_ADMIN, Role.CLIENT_OWNER],
        "DELETE": [Role.CLIENT_ADMIN, Role.CLIENT_OWNER],
    }

    def get(self, request, **kwargs):
        organization = request.user.clientuser.organization
        client_users = ClientUser.objects.filter(
            organization=organization
        ).select_related("user")

        if request.user.role == Role.CLIENT_USER:
            client_user = client_users.filter(user=request.user).first()
            serializer = self.serializer_class(client_user)
            return Response(
                {
                    "status": "success",
                    "message": "Client User retrieved successfully",
                    "data": serializer.data,
                }
            )

        client_users = client_users.prefetch_related("jobs")
        paginated_client_users = self.paginate_queryset(client_users, request)
        serializer = self.serializer_class(paginated_client_users, many=True)
        paginated_data = self.get_paginated_response(serializer.data)
        return Response(
            {
                "status": "success",
                "message": "Client users retrieved successfully.",
                "data": paginated_data.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"user": request.user}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(
            invited_by=request.user, organization=request.user.clientuser.organization
        )
        return Response(
            {
                "status": "success",
                "message": "Client user added successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request, **kwargs):
        return self._update_delete_client_user(
            request, kwargs.get("client_user_id"), partial=True
        )

    def delete(self, request, **kwargs):
        return self._update_delete_client_user(request, kwargs.get("client_user_id"))

    def _update_delete_client_user(self, request, client_user_id, partial=False):

        if not client_user_id:
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid client_user_id in URL.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        client_user_obj = ClientUser.objects.filter(
            organization=request.user.clientuser.organization, pk=client_user_id
        ).first()

        if not client_user_obj:
            return Response(
                {"status": "failed", "message": "Client user not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        self.check_object_permissions(request, client_user_obj)
        if partial:
            serializer = self.serializer_class(
                client_user_obj, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            message = "Client user updated successfully."
        else:
            client_user_obj.archived = True
            client_user_obj.user.is_active = False
            client_user_obj.user.save()
            client_user_obj.save()
            message = "Client user successfully deleted."

        response_data = {"status": "success", "message": message}
        if partial:
            response_data["data"] = serializer.data

        return Response(
            response_data,
            status=status.HTTP_200_OK if partial else status.HTTP_204_NO_CONTENT,
        )

    def finalize_response(self, request, response, *args, **kwargs):
        if response.data.get("errors"):
            response.data["status"] = "failed"
            response.data["message"] = response.data.get("message", "Invalid data")
            errors = response.data.pop("errors")
            response.data["errors"] = errors
        return super().finalize_response(request, response, *args, **kwargs)


@extend_schema(tags=["Client"])
class ClientInvitationActivateView(APIView):

    def patch(self, request, uid):
        try:
            decoded_data = force_str(urlsafe_base64_decode(uid))
            inviter_email, invitee_email = [
                item.split(":")[1] for item in decoded_data.split(";")
            ]

            client_user = ClientUser.objects.filter(
                invited_by__email=inviter_email, user__email=invitee_email
            ).first()

            if not client_user:
                return Response(
                    {"status": "failed", "message": "Invalid user"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if (
                datetime.now().timestamp()
                > (client_user.created_at + timedelta(days=2)).timestamp()
            ):
                return Response(
                    {"status": "failed", "message": "Invitation expired"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if client_user.status == "ACT":
                return Response(
                    {"status": "failed", "message": "User is already activated."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            client_user.status = "ACT"
            client_user.save()

            return Response(
                {"status": "success", "message": "User activated successfully."},
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {"status": "failed", "message": "Invalid UID"},
                status=status.HTTP_400_BAD_REQUEST,
            )


@extend_schema(tags=["Client"])
class JobView(APIView, LimitOffsetPagination):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, HasRole, UserRoleDeleteUpdateClientData]
    roles_mapping = {
        "GET": [Role.CLIENT_ADMIN, Role.CLIENT_OWNER, Role.CLIENT_USER],
        "POST": [Role.CLIENT_ADMIN, Role.CLIENT_OWNER],
        "PATCH": [Role.CLIENT_ADMIN, Role.CLIENT_OWNER, Role.CLIENT_USER],
        "DELETE": [Role.CLIENT_ADMIN, Role.CLIENT_OWNER, Role.CLIENT_USER],
    }

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"org": request.user.clientuser.organization}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Job created successfully.",
                    "data": serializer.data,
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

    def get(self, request, **kwargs):
        job_id = kwargs.get("job_id")
        job_ids = request.query_params.get("job_ids")
        try:
            job_ids = [int(i) for i in job_ids.split(",")] if job_ids else []
        except ValueError:
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid job_ids in query params. It should be comma seperated integer values.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        recruiter_ids = request.query_params.get("recruiter_ids")
        try:
            recruiter_ids = (
                [int(i) for i in recruiter_ids.split(",")] if recruiter_ids else []
            )
        except ValueError:
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid recruiter_ids in query params. It should be comma seperated integer values.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        hiring_manager_ids = request.query_params.get("hiring_manager_ids")
        try:
            hiring_manager_ids = (
                [int(i) for i in hiring_manager_ids.split(",")]
                if hiring_manager_ids
                else []
            )
        except ValueError:
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid hiring_manager_ids in query params. It should be comma seperated integer values.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        post_job_date = request.query_params.get("post_job_date")

        jobs = Job.objects.filter(
            hiring_manager__organization_id=request.user.clientuser.organization_id
        ).prefetch_related("clients")

        if (
            request.user.role == "client_user"
            and request.user.clientuser.accessibility == "AGJ"
        ):
            jobs = jobs.filter(clients=request.user.clientuser)

        if job_ids:
            jobs = jobs.filter(pk__in=job_ids)

        if recruiter_ids:
            jobs = jobs.filter(clients__in=recruiter_ids)

        if hiring_manager_ids:
            jobs = jobs.filter(hiring_manager__in=hiring_manager_ids)

        if post_job_date:
            try:
                post_job_date = (
                    datetime.strptime(post_job_date, "%d/%m/%Y")
                    .date()
                    .strftime("%Y-%m-%d")
                )
                jobs = jobs.filter(created_at__date=post_job_date)
            except ValueError:
                return Response(
                    {
                        "status": "failed",
                        "message": "Invalid post_job_date in query params. It should be in DD/MM/YYYY format.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if job_id:
            job = jobs.filter(pk=job_id).first()
            if not job:
                return Response(
                    {
                        "status": "failed",
                        "message": "Job not found.",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            serializer = self.serializer_class(job)
            return Response(
                {
                    "status": "success",
                    "message": "Job retrieved successfully.",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        paginated_jobs = self.paginate_queryset(jobs, request)
        serializer = self.serializer_class(paginated_jobs, many=True)
        response_data = self.get_paginated_response(serializer.data)

        return Response(
            {
                "status": "success",
                "message": "Jobs retrieved successfully.",
                **response_data.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, **kwargs):
        job_id = kwargs.get("job_id")
        if not job_id:
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid job_id in url.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            job = Job.objects.get(
                hiring_manager__organization_id=request.user.clientuser.organization_id,
                pk=job_id,
            )
            self.check_object_permissions(request, job)
        except Job.DoesNotExist:
            return Response(
                {
                    "status": "failed",
                    "message": "Job not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.serializer_class(
            job,
            data=request.data,
            partial=True,
            context={"org": request.user.clientuser.organization},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Job updated successfully.",
                    "data": serializer.data,
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

    def delete(self, request, **kwargs):
        job_id = kwargs.get("job_id")
        if not job_id:
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid job_id in url.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            job = Job.objects.get(
                hiring_manager__organization_id=request.user.clientuser.organization_id,
                pk=job_id,
            )
            self.check_object_permissions(request, job)
        except Job.DoesNotExist:
            return Response(
                {
                    "status": "failed",
                    "message": "Job not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        job.archived = True
        job.save()

        return Response(
            {
                "status": "success",
                "message": "Job deleted successfully.",
            },
            status=status.HTTP_204_NO_CONTENT,
        )


@extend_schema(tags=["Client"])
class ResumeParserView(APIView, LimitOffsetPagination):
    serializer_class = None
    permission_classes = [
        IsAuthenticated,
        IsClientAdmin | IsClientUser | IsClientOwner | IsAgency | IsSuperAdmin,
    ]

    def post(self, request):
        resume_files = request.FILES.getlist("resume")

        if not resume_files:
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid request.",
                    "error": {
                        "resume": [
                            "This field is required. It supports multiple resume files in PDF and DOCX formats."
                        ]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        for file in resume_files:
            errors = validate_attachment("resume", file, ["pdf", "docx"], 5)
            if errors:
                return Response(
                    {
                        "status": "failed",
                        "message": "Invalid File Format",
                        "error": errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        temp_dir = tempfile.mkdtemp()  # Create a persistent temp directory
        parsed_resumes = []

        try:
            for file in resume_files:
                temp_path = os.path.join(temp_dir, file.name)
                with open(temp_path, "wb") as temp_file:
                    for chunk in file.chunks():
                        temp_file.write(chunk)

                # Pass file paths to processing function
                parsed_data = process_resume(temp_path)
                if parsed_data:
                    parsed_resumes.append(parsed_data)

            return Response(
                {
                    "status": "success",
                    "message": "Resume parsed successfully.",
                    "data": parsed_resumes,
                },
                status=status.HTTP_200_OK,
            )
        finally:
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)


@extend_schema(tags=["Client"])
class CandidateView(APIView, LimitOffsetPagination):
    serializer_class = CandidateSerializer
    permission_classes = [
        IsAuthenticated,
        IsClientAdmin | IsClientUser | IsClientOwner | IsAgency,
        UserRoleDeleteUpdateClientData,
    ]

    def get(self, request, **kwargs):
        candidate_id = kwargs.get("candidate_id")
        job_id = request.query_params.get("job_id")
        status_ = request.query_params.get("status")
        search_term = request.query_params.get("q")

        if status_ and status_ not in dict(Candidate.STATUS_CHOICES).keys():
            return Response(
                {"status": "failed", "message": "Invalid Status."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        candidates = Candidate.objects.filter(
            organization=request.user.clientuser.organization,
        ).select_related("designation")

        if request.user.role in [Role.CLIENT_USER, Role.AGENCY]:
            candidates = candidates.filter(designation__clients=request.user.clientuser)

        total_candidates = candidates.count()
        scheduled = candidates.filter(status="SCH").count()
        inprocess = candidates.filter(status="NSCH").count()
        recommended = candidates.filter(Q(status="REC") | Q(status="HREC")).count()
        rejected = candidates.filter(Q(status="SNREC") | Q(status="NREC")).count()

        if job_id and job_id.isdigit():
            candidates = candidates.filter(designation__id=job_id)

        if status_:
            candidates = candidates.filter(status=status_)

        if search_term:
            candidates = candidates.filter(
                Q(name__icontains=search_term)
                | Q(email=search_term)
                | Q(phone=search_term)
            )

        if candidate_id:
            candidate = candidates.filter(pk=candidate_id).first()
            if not candidate:
                return Response(
                    {"status": "failed", "message": "Candidate not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            serializer = self.serializer_class(candidate)
            return Response(
                {
                    "status": "success",
                    "message": "Candidate retrieved successfully.",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        paginated_candidates = self.paginate_queryset(candidates, request)
        serializer = self.serializer_class(paginated_candidates, many=True)
        paginated_response = self.get_paginated_response(serializer.data)
        response_data = {
            "status": "success",
            "message": "Candidates retrieved successfully.",
            "total_candidates": total_candidates,
            "scheduled": scheduled,
            "inprocess": inprocess,
            "recommended": recommended,
            "rejected": rejected,
            **paginated_response.data,
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def post(self, request, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save(
                organization=request.user.clientuser.organization,
                designation_id=serializer.validated_data.pop("job_id"),
            )
            return Response(
                {
                    "status": "success",
                    "message": "Candidate stored successfully",
                    "data": serializer.data,
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

    def patch(self, request, **kwargs):
        candidate_id = kwargs.get("candidate_id")
        candidate_instance = self.get_candidate_instance(request, candidate_id)
        if isinstance(candidate_instance, Response):
            return candidate_instance
        serializer = self.serializer_class(
            candidate_instance, request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Successfully updated candidate profile",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        custom_errors = serializer.errors.pop("errors", None)
        return Response(
            {
                "status": "failed",
                "message": "Failed to update candidate profile",
                "errors": custom_errors if custom_errors else serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, **kwargs):
        candidate_id = kwargs.get("candidate_id")
        reason_for_dropping = request.data.get("reason")
        if (
            reason_for_dropping
            not in dict(Candidate.REASON_FOR_DROPPING_CHOICES).keys()
        ):
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid reason for dropping. Please choose from the following options: {}".format(
                        ", ".join(
                            [
                                "{} ({})".format(key, value)
                                for key, value in dict(
                                    Candidate.REASON_FOR_DROPPING_CHOICES
                                ).items()
                            ]
                        )
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        candidate_instance = self.get_candidate_instance(request, candidate_id)
        if isinstance(candidate_instance, Response):
            return candidate_instance

        if reason_for_dropping:
            candidate_instance.reason_for_dropping = reason_for_dropping

        candidate_instance.archived = True
        candidate_instance.save()
        return Response(
            {"status": "success", "message": "Candidate dropped successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )

    def get_candidate_instance(self, request, candidate_id):
        try:
            candidate_instance = Candidate.objects.get(
                organization=request.user.clientuser.organization, pk=candidate_id
            )
            self.check_object_permissions(request, candidate_instance)
        except Candidate.DoesNotExist:
            return Response(
                {"status": "failed", "message": "Candidate not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return candidate_instance


@extend_schema(tags=["Client"])
class PotentialInterviewerAvailabilityForCandidateView(APIView):
    serializer_class = None
    permission_classes = [
        IsAuthenticated,
        IsClientAdmin | IsClientOwner | IsClientUser | IsAgency,
    ]

    def get(self, request):
        date = request.query_params.get("date")
        time = request.query_params.get("time")
        specialization = request.query_params.get("specialization")
        experience = request.query_params.get("experience_year")
        company = request.query_params.get("company")
        designation_id = request.query_params.get("designation_id")

        required_fields = {
            "date": date,
            "time": time,
            "designation_id": designation_id,
            "experience_year": experience,
            "specialization": specialization,
            "company": company,
        }
        missing_fields = [
            field for field, value in required_fields.items() if not value
        ]
        if missing_fields:
            return Response(
                {
                    "status": "failed",
                    "message": f"{', '.join(missing_fields)} are required in query params.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            formatted_date = datetime.strptime(date, "%d/%m/%Y").date()
            if formatted_date < datetime.today().date():
                return Response(
                    {"status": "failed", "message": "Invalid date"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            formatted__start_time = datetime.strptime(time, "%H:%M").time()
            if (
                formatted_date == datetime.today().date()
                and formatted__start_time < datetime.now().time()
            ):
                return Response(
                    {"status": "failed", "message": "Invalid time"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            end_time = (datetime.strptime(time, "%H:%M") + timedelta(hours=1)).time()
        except ValueError:
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid date or time format. Use DD/MM/YYYY and HH:MM",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            experience = int(experience) if experience is not None else 0
        except ValueError:
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid experience format. It should be a valid integer",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if specialization not in dict(Candidate.SPECIALIZATION_CHOICES).keys():
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid specialization. Please choose from the following options: {}".format(
                        ", ".join(
                            "{} ({})".format(key, value)
                            for key, value in dict(
                                Candidate.SPECIALIZATION_CHOICES
                            ).items()
                        )
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            job = Job.objects.get(
                pk=designation_id,
                hiring_manager__organization=request.user.clientuser.organization,
            )
        except Job.DoesNotExist:
            return Response(
                {"status": "failed", "message": "Job not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        skills = job.mandatory_skills or []
        if not skills:
            return Response(
                {
                    "status": "failed",
                    "message": "No mandatory skills found for this job.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        query = Q()
        for skill in skills:
            query |= Q(interviewer__skills__icontains=f'"{skill}"')

        interviewer_availability = (
            InterviewerAvailability.objects.select_related("interviewer")
            .filter(
                date=formatted_date,
                start_time__lte=formatted__start_time,
                end_time__gte=end_time,
                interviewer__assigned_roles=job.name,
                interviewer__strength=specialization,
                interviewer__total_experience_years__gte=experience + 2,
                booked_by__isnull=True,
            )
            .filter(query)
            .exclude(interviewer__current_company__iexact=company)
            .values("id", "date", "start_time", "end_time")
        )

        if not interviewer_availability:
            return Response(
                {"status": "failed", "message": "No available slots on that date."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "status": "success",
                "message": "Available slots retrieved successfully.",
                "data": list(interviewer_availability),
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Client"])
class EngagementTemplateView(APIView, LimitOffsetPagination):
    permission_classes = [IsAuthenticated, IsClientOwner | IsClientAdmin | IsClientUser]
    serializer_class = EngagementTemplateSerializer

    def get(self, request, **kwrags):
        engagement_template_qs = EngagementTemplates.objects.filter(
            organization=request.user.clientuser.organization
        )
        paginated_queryset = self.paginate_queryset(engagement_template_qs, request)
        serializer = self.serializer_class(paginated_queryset, many=True)
        paginated_response = self.get_paginated_response(serializer.data)
        return Response(
            {
                "status": "success",
                "message": "Successfully retrieved templates",
                **paginated_response.data,
            }
        )

    def post(self, request, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"attachment": request.FILES.get("attachment")}
        )
        if serializer.is_valid():
            serializer.save(organization=request.user.clientuser.organization)
            return Response(
                {
                    "status": "success",
                    "message": "Successfully created template",
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        custom_errors = serializer.errors.pop("errors", None)
        return Response(
            {
                "status": "failed",
                "message": "Invalid data",
                "errors": custom_errors if custom_errors else serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def patch(self, request, pk):
        try:
            engagement_template = EngagementTemplates.objects.get(
                pk=pk, organization=request.user.clientuser.organization
            )
        except EngagementTemplates.DoesNotExist:
            return Response(
                {"status": "failed", "message": "Template not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.serializer_class(
            engagement_template, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Successfully updated template",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "status": "failed",
                "message": "Invalid data",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, pk):
        try:
            engagement_template = EngagementTemplates.objects.get(
                pk=pk, organization=request.user.clientuser.organization
            )
        except EngagementTemplates.DoesNotExist:
            return Response(
                {"status": "failed", "message": "Template not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        engagement_template.archived = True
        engagement_template.save(update_fields=["archived"])
        return Response(
            {"status": "success", "message": "Successfully deleted template"},
            status=status.HTTP_204_NO_CONTENT,
        )


@extend_schema(tags=["Client"])
class EngagementView(APIView, LimitOffsetPagination):
    serializer_class = EngagementSerializer
    permission_classes = [IsAuthenticated, IsClientAdmin | IsClientOwner | IsClientUser]

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Successfully created engagement",
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        custom_errors = serializer.errors.pop("errors", None)
        return Response(
            {
                "status": "failed",
                "message": "Invalid data",
                "errors": custom_errors if custom_errors else serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def get(self, request):
        query_params = request.query_params
        job_id = query_params.get("job_id")
        specialization = query_params.get("specialization")
        notice_period = query_params.get("np")
        search_filter = query_params.get("q")

        filters = {
            "client__organization_id": request.user.clientuser.organization_id,
        }
        if job_id:
            filters["job_id"] = job_id
        if specialization:
            filters["candidate__specialization"] = specialization
        if notice_period:
            filters["notice_period"] = notice_period

        engagement_summary = Engagement.objects.filter(
            client__organization=request.user.clientuser.organization
        ).aggregate(
            total_candidates=Count("id"),
            joined=Count("id", filter=Q(status="JND")),
            declined=Count("id", filter=Q(status="DCL")),
            pending=Count("id", filter=Q(status="YTJ")),
        )

        engagements = (
            Engagement.objects.select_related("client", "job", "candidate")
            .prefetch_related("engagementoperations")
            .filter(**filters)
        )

        if search_filter:
            engagements = engagements.filter(
                Q(candidate_name__icontains=search_filter)
                | Q(candidate__name__icontains=search_filter)
                | Q(candidate_email__icontains=search_filter)
                | Q(candidate__email__icontains=search_filter)
                | Q(candidate_phone__icontains=search_filter)
                | Q(candidate__phone__icontains=search_filter)
            )

        paginated_engagements = self.paginate_queryset(engagements, request)
        serializer = self.serializer_class(paginated_engagements, many=True)
        paginated_response = self.get_paginated_response(serializer.data)

        return Response(
            {
                "status": "success",
                "message": "Successfully retrieved engagements",
                **engagement_summary,
                **paginated_response.data,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Client"])
class EngagementOperationView(APIView, LimitOffsetPagination):
    serializer_class = EngagementOperationSerializer
    permission_classes = [IsAuthenticated, IsClientAdmin | IsClientOwner | IsClientUser]

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Engagement operation initiated successfully",
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

        custom_errors = serializer.errors.pop("errors", None)
        return Response(
            {
                "status": "failed",
                "message": "Failed to initiate the engagement operation",
                "errors": custom_errors if custom_errors else serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    """    --> keep it for future reference
    def get(self, request):
        organization = request.user.clientuser.organization
        engagement_operation = EngagementOperation.objects.filter(
            engagement__client__organization=organization
        )
        paginated_engagements = self.paginate_queryset(engagement_operation, request)
        serializer = self.serializer_class(paginated_engagements, many=True)
        paginated_response = self.get_paginated_response(serializer.data)
        return Response(
            {
                "status": "success",
                "message": "Successfully retrieved engagements",
                **paginated_response.data,
            },
            status=status.HTTP_200_OK,
        )
    """


@extend_schema(tags=["Client"])
class EngagementOperationUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsClientAdmin | IsClientOwner | IsClientUser]

    def patch(self, request, engagement_id):
        with transaction.atomic():
            engagement_operations = EngagementOperation.objects.filter(
                template__organization=request.user.clientuser.organization,
                engagement_id=engagement_id,
            )

            if not engagement_operations.exists():
                return Response(
                    {"status": "failed", "message": "Engagement not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if "template_data" not in request.data or not isinstance(
                request.data["template_data"], list
            ):
                return Response(
                    {
                        "status": "failed",
                        "message": "template_data is required",
                        "errors": {
                            "template_data": [
                                "This field must be a non-empty list of dictionaries with keys 'template_id' and 'date'.",
                                "Expected format: [{'template_id': <int>, 'operation_id': <int>(optional), 'week': <int>(optional), 'date': '<dd/mm/yyyy hh:mm:ss>'}]",
                            ]
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            template_data = request.data.get("template_data")
            for entry in template_data:
                if (
                    not isinstance(entry, dict)
                    or ("template_id" not in entry and "operation_id" not in entry)
                    or ("operation_id" not in entry and "week" not in entry)
                    or "date" not in entry
                ):
                    return Response(
                        {
                            "status": "failed",
                            "message": "Invalid template data",
                            "errors": {
                                "template_data": [
                                    "Each item must match the following schema:",
                                    "Expected format: {'template_id': <int>, 'operation_id': <int>(optional), 'week': <int>(optional), 'date': '<dd/mm/yyyy hh:mm:ss>'}",
                                ]
                            },
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            for template in template_data:
                try:
                    datetime.strptime(template["date"], "%d/%m/%Y %H:%M:%S")
                except ValueError:
                    return Response(
                        {
                            "status": "failed",
                            "message": "Invalid date format",
                            "errors": {
                                "template_data": [
                                    "Each item must have a 'date' in this format: '%d/%m/%Y %H:%M:%S'",
                                ]
                            },
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            invalid_dates = [
                template["date"]
                for template in template_data
                if datetime.strptime(
                    template["date"],
                    "%d/%m/%Y %H:%M:%S",
                )
                < datetime.strptime(
                    datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "%d/%m/%Y %H:%M:%S",
                )
            ]

            for template in template_data:
                template["date"] = datetime.strptime(
                    template["date"], "%d/%m/%Y %H:%M:%S"
                ).strftime("%Y-%m-%d %H:%M:%S")

            if invalid_dates:
                return Response(
                    {
                        "status": "failed",
                        "message": "Invalid dates in template data",
                        "errors": {
                            "template_data": [
                                f"Dates in the past are not allowed: {', '.join(invalid_dates)}"
                            ]
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            valid_template_ids = set(
                EngagementTemplates.objects.filter(
                    organization=request.user.clientuser.organization,
                    pk__in=[template["template_id"] for template in template_data],
                ).values_list("id", flat=True)
            )
            existing_template_ids = set(
                EngagementOperation.objects.filter(
                    engagement_id=engagement_id, template_id__in=valid_template_ids
                ).values_list("template_id", flat=True)
            )
            if existing_template_ids:
                return Response(
                    {
                        "status": "failed",
                        "message": "Template id already exists for the given engagement",
                        "errors": {
                            "template_data": [
                                "Template id already exists for the given engagement: {}".format(
                                    template_id
                                )
                                for template_id in existing_template_ids
                            ]
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            invalid_template_ids = (
                set(template["template_id"] for template in template_data)
                - valid_template_ids
            )

            if invalid_template_ids:
                return Response(
                    {
                        "status": "failed",
                        "message": "Invalid template IDs",
                        "errors": {
                            "template_data": [
                                "Invalid template_id: {}".format(
                                    ", ".join(map(str, invalid_template_ids))
                                )
                            ]
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            operation_ids = {
                entry.get("operation_id")
                for entry in template_data
                if "operation_id" in entry
            }
            valid_operation_ids = set(
                engagement_operations.values_list("id", flat=True)
            )
            invalid_operation_ids = operation_ids - valid_operation_ids

            if invalid_operation_ids:
                return Response(
                    {
                        "status": "failed",
                        "message": "Invalid operation IDs",
                        "errors": {
                            "template_data": [
                                f"operation_id {', '.join(map(str, invalid_operation_ids))} do not exist."
                            ]
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Prevent updating operations that are already successful
            locked_operations = engagement_operations.filter(
                pk__in=operation_ids, delivery_status="SUC"
            ).values_list("id", flat=True)

            if locked_operations:
                return Response(
                    {
                        "status": "failed",
                        "message": f"Cannot update operations: {', '.join(map(str, locked_operations))} as they are already successful.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Dictionary mapping operation_id -> data
            operation_data_map = {
                entry["operation_id"]: entry
                for entry in template_data
                if "operation_id" in entry
            }

            rescheduled_operations = []
            for operation in engagement_operations.filter(pk__in=operation_ids):
                template_entry = operation_data_map.get(operation.id)
                if template_entry:
                    if operation.date != template_entry["date"]:
                        # **Revoke old task if it exists**
                        if operation.task_id:
                            AsyncResult(operation.task_id).revoke(terminate=True)

                        # **Schedule a new task**
                        new_task = send_schedule_engagement_email.s(operation.id).set(
                            eta=template_entry["date"]
                        )
                        new_task_result = new_task.apply_async()

                        # **Update task ID with the new one**
                        operation.task_id = new_task_result.id

                    operation.template_id = template_entry["template_id"]
                    operation.date = template_entry["date"]
                    operation.week = template_entry.get("week", operation.week)
                    rescheduled_operations.append(operation)

            # Bulk update modified operations
            EngagementOperation.objects.bulk_update(
                rescheduled_operations, ["template_id", "date", "week", "task_id"]
            )

            # New operations (ones without operation_id)
            new_operations = [
                entry for entry in template_data if "operation_id" not in entry
            ]

            # Get engagement details
            engagement = Engagement.objects.filter(pk=engagement_id).first()
            if not engagement:
                return Response(
                    {"status": "failed", "message": "Engagement not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            notice_weeks = int(engagement.notice_period.split("-")[1]) / 7
            max_template_assign = notice_weeks * 2

            # Validate new template assignment limit
            existing_count = EngagementOperation.objects.filter(
                engagement=engagement
            ).count()
            if (
                new_operations
                and len(new_operations) + existing_count > max_template_assign
            ):
                return Response(
                    {
                        "status": "failed",
                        "message": "Max template assignment exceeded",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate max templates per week
            week_counts = (
                EngagementOperation.objects.filter(engagement=engagement)
                .values("week")
                .annotate(count=Count("week"))
            )
            week_count_map = {entry["week"]: entry["count"] for entry in week_counts}

            for template in new_operations:
                week = template.get("week")
                week_count_map[week] = week_count_map.get(week, 0) + 1
                print(week_count_map, week_count_map[week])
                if week is not None and week_count_map[week] > 2:
                    return Response(
                        {
                            "status": "failed",
                            "message": f"Week {week} has exceeded max templates (2).",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            if len(week_count_map) > notice_weeks:
                return Response(
                    {
                        "status": "failed",
                        "message": "Number of weeks with templates assigned exceeds the notice period weeks.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Bulk create new operations
            created_operations = EngagementOperation.objects.bulk_create(
                [
                    EngagementOperation(
                        engagement=engagement,
                        template_id=entry["template_id"],
                        date=entry["date"],
                        week=entry.get("week"),
                    )
                    for entry in new_operations
                ]
            )

            # Schedule emails
            task_group = group(
                send_schedule_engagement_email.s(operation.id).set(eta=operation.date)
                for operation in created_operations
            )
            result = task_group.apply_async()

            # Assign task IDs in bulk update
            for operation, task in zip(created_operations, result.children):
                operation.task_id = task.id

            EngagementOperation.objects.bulk_update(created_operations, ["task_id"])

        return Response(
            {
                "status": "success",
                "message": "Engagement operations updated successfully.",
            },
            status=status.HTTP_200_OK,
        )
