from datetime import datetime, timedelta
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.db.models import Q, F, ExpressionWrapper, DurationField
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
    InternalInterviewer,
    InterviewerAvailability,
)
from ..serializer import ClientUserSerializer, JobSerializer, CandidateSerializer
from ..permissions import CanDeleteUpdateUser, UserRoleDeleteUpdateClientData
from externals.parser.resume_parser import ResumerParser
from externals.parser.resumeparser2 import ResumeParser2
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

        resume_parser = ResumeParser2()
        
        response = resume_parser.process_multiple_resumes(resume_files)

        return Response(
            {
                "status": "success",
                "message": "Resume parsed successfully.",
                "data": response,
            },
            status=status.HTTP_200_OK,
        )





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
