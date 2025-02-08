from datetime import datetime, timedelta
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from ..models import ClientUser, Job, Candidate
from ..serializer import ClientUserSerializer, JobSerializer, CandidateSerializer
from externals.parser.resume_parser import ResumerParser
from core.permissions import IsClientAdmin, IsClientOwner, IsClientUser, HasRole
from core.models import Role
from hiringdogbackend.utils import validate_attachment


@extend_schema(tags=["Client"])
class ClientUserView(APIView, LimitOffsetPagination):
    serializer_class = ClientUserSerializer
    permission_classes = [IsAuthenticated, HasRole]
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

        if partial:
            serializer = self.serializer_class(
                client_user_obj, data=request.data, partial=partial
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            message = "Client user updated successfully."
        else:
            client_user_obj.archived = True
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
    permission_classes = [IsAuthenticated, HasRole]
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
            job = Job.objects.get(pk=job_id)
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
            job = Job.objects.get(pk=job_id)
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
class ResumePraserView(APIView, LimitOffsetPagination):
    serializer_class = None
    permission_classes = [IsAuthenticated]

    def post(self, request):
        resume_files = request.FILES.getlist("resume")

        if not resume_files:
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid request.",
                    "error": {
                        "resume": [
                            "This field is required. It support list to upload multiple resume files in the format of pdf and docx."
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
                    }
                )

        resume_parser = ResumerParser()

        response = resume_parser.parse_resume(resume_files)

        return Response(
            {
                "status": "success",
                "message": "Resume parsed Successfully.",
                "data": response,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Client"])
class CandidateView(APIView, LimitOffsetPagination):
    serializer_class = CandidateSerializer
    permission_classes = [IsAuthenticated, IsClientAdmin | IsClientUser | IsClientOwner]

    def get(self, request, **kwargs):
        candidate_id = kwargs.get("candidate_id")
        candidates = Candidate.objects.filter(
            organization=request.user.clientuser.organization
        ).select_related("designation")

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
