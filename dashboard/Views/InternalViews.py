from drf_spectacular.utils import extend_schema
from django.db.models import Count, Q
from organizations.models import Organization
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from core.permissions import IsSuperAdmin, IsModerator
from ..models import (
    InternalClient,
    InternalInterviewer,
    Agreement,
)
from ..serializer import (
    InternalClientSerializer,
    InterviewerSerializer,
    AgreementSerializer,
    OrganizationSerializer,
)


@extend_schema(tags=["Internal"])
class InternalClientView(APIView, LimitOffsetPagination):
    serializer_class = InternalClientSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin | IsModerator]

    def get(self, request):
        domain = request.query_params.get("domain")
        status_ = request.query_params.get("status")
        search_term = request.query_params.get("q")

        aggregation = InternalClient.objects.aggregate(
            active_jobs=Count(
                "organization__clientuser__jobs",
                filter=Q(organization__clientuser__jobs__archived=False),
                distinct=True,
            ),
            passive_jobs=Count(
                "organization__clientuser__jobs",
                filter=Q(organization__clientuser__jobs__archived=True),
                distinct=True,
            ),
            total_candidates=Count(
                "organization__candidate",
                distinct=True,
            ),
        )
        internal_clients = (
            InternalClient.objects.select_related("organization")
            .prefetch_related("points_of_contact")
            .order_by("id")
        )

        if domain:
            internal_clients = internal_clients.filter(domain__icontains=domain.lower())

        if search_term:
            internal_clients = internal_clients.filter(
                name__icontains=search_term.lower()
            )

        # remember to add the role based retreival after creating the hdip user functionality
        paginated_queryset = self.paginate_queryset(internal_clients, request)
        serializer = self.serializer_class(paginated_queryset, many=True)
        paginated_data = self.get_paginated_response(serializer.data)
        return Response(
            {
                "status": "success",
                "message": "Client user retrieve successfully.",
                **aggregation,
                **paginated_data.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Client user added successfully.",
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {
                "status": "failed",
                "message": "Invalid data.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def finalize_response(self, request, response, *args, **kwargs):
        if response.data.get("errors"):
            response.data["status"] = "failed"
            response.data["message"] = response.data.get("message", "Invalid data")
            errors = response.data["errors"]
            del response.data["errors"]
            response.data["errors"] = errors
        return super().finalize_response(request, response, *args, **kwargs)


@extend_schema(tags=["Internal"])
class InternalClientDetailsView(APIView):
    serializer_class = InternalClientSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin | IsModerator]

    def get(self, request, pk):

        try:
            client = InternalClient.objects.get(pk=pk)
        except InternalClient.DoesNotExist:
            return Response(
                {"errors": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(client)
        return Response(
            {
                "status": "success",
                "message": "Client data retrieved successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        try:
            client = InternalClient.objects.get(pk=pk)
        except InternalClient.DoesNotExist:
            return Response(
                {"errors": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(
            client, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Client data updated successfully.",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "status": "failed",
                "message": "Invalid data.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, pk):
        try:
            client = InternalClient.objects.get(pk=pk)
        except InternalClient.DoesNotExist:
            return Response(
                {"errors": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        client.archived = True
        client.save()
        return Response(
            {
                "status": "success",
                "message": "Client data deleted successfully.",
            },
            status=status.HTTP_204_NO_CONTENT,
        )

    def finalize_response(self, request, response, *args, **kwargs):
        if response.data.get("errors"):
            response.data["status"] = "failed"
            response.data["message"] = response.data.get("message", "Invalid data")
            errors = response.data["errors"]
            del response.data["errors"]
            response.data["errors"] = errors
        return super().finalize_response(request, response, *args, **kwargs)


@extend_schema(tags=["Internal"])
class InterviewerView(APIView, LimitOffsetPagination):
    serializer_class = InterviewerSerializer
    permission_classes = [IsAuthenticated, IsModerator | IsSuperAdmin]

    def get(self, request):
        strength = request.query_params.get("strength")
        experience = request.query_params.get("experience")
        search_terms = request.query_params.get("q")

        # Validate strength
        valid_strengths = dict(InternalInterviewer.STRENGTH_CHOICES).keys()
        if strength and strength not in valid_strengths:
            return Response(
                {
                    "status": "failed",
                    "message": f"This is an invalid strength. Valid strength are {', '.join([f'{key}({value})' for key, value in InternalInterviewer.STRENGTH_CHOICES])}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate experience
        experience_choices = {
            "0-4": ("lte", 4),
            "5-8": ("range", (5, 8)),
            "9-10": ("range", (9, 10)),
            "11": ("gt", 11),
        }
        if experience and experience not in experience_choices:
            valid_experience_choices = ", ".join(experience_choices.keys())
            return Response(
                {
                    "status": "failed",
                    "message": f"Invalid experience. Valid choices are {valid_experience_choices}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Filter interviewers based on query parameters
        filters = {}
        if experience:
            filters[f"total_experience_years__{experience_choices[experience][0]}"] = (
                experience_choices[experience][1]
            )
        if strength:
            filters["strength"] = strength

        interviewers_qs = InternalInterviewer.objects.filter(**filters)

        if search_terms:
            interviewers_qs = interviewers_qs.filter(
                Q(name__icontains=search_terms)
                | Q(email__icontains=search_terms)
                | Q(phone_number=search_terms)
            )

        # Aggregate interviewer data
        interviewers_aggregation = InternalInterviewer.objects.aggregate(
            total_interviewers=Count("id"),
            years_0_4=Count("id", filter=Q(total_experience_years__lte=4)),
            years_5_8=Count("id", filter=Q(total_experience_years__range=(5, 8))),
            years_9_10=Count("id", filter=Q(total_experience_years__range=(9, 10))),
            years_11=Count("id", filter=Q(total_experience_years__gt=11)),
        )

        # Paginate and serialize the results
        paginated_qs = self.paginate_queryset(interviewers_qs, request)
        serializer = self.serializer_class(paginated_qs, many=True)
        paginated_data = self.get_paginated_response(serializer.data)

        return Response(
            {
                "status": "success",
                "message": "Interviewer list retrieved successfully.",
                **interviewers_aggregation,
                **paginated_data.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Interviewer added successfully.",
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

    def finalize_response(self, request, response, *args, **kwargs):
        if response.data.get("errors"):
            response.data["status"] = "failed"
            response.data["message"] = response.data.get("message", "Invalid data")
            errors = response.data["errors"]
            del response.data["errors"]
            response.data["errors"] = errors
        return super().finalize_response(request, response, *args, **kwargs)


@extend_schema(tags=["Internal"])
class InterviewerDetails(APIView):
    serializer_class = InterviewerSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin | IsModerator]

    def get(self, request, pk):
        try:
            interviewer = InternalInterviewer.objects.get(pk=pk)
        except InternalInterviewer.DoesNotExist:
            return Response(
                {"errors": "Interviewer not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(interviewer)
        return Response(
            {
                "status": "success",
                "message": "Interviewer data successfully retrived.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        try:
            interviewer = InternalInterviewer.objects.get(pk=pk)
        except InternalInterviewer.DoesNotExist:
            return Response(
                {"errors": "Interviewer not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(interviewer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Interviewer added successfully.",
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

    def delete(self, request, pk):
        try:
            interviewer = InternalInterviewer.objects.get(pk=pk)
            interviewer.archived = True
            interviewer.user.is_active = False
            interviewer.user.save(update_fields=["is_active"])
            interviewer.save(update_fields=["archived"])
            return Response(
                {"status": "success", "message": "Interviewer deleted successfully"},
                status=status.HTTP_204_NO_CONTENT,
            )
        except InternalInterviewer.DoesNotExist:
            return Response(
                {"status": "failed", "messsage": "Interviewer not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    def finalize_response(self, request, response, *args, **kwargs):
        if response.data.get("errors"):
            response.data["status"] = "failed"
            response.data["message"] = response.data.get("message", "Invalid data")
            errors = response.data["errors"]
            del response.data["errors"]
            response.data["errors"] = errors
        return super().finalize_response(request, response, *args, **kwargs)


@extend_schema(tags=["Internal"])
class AgreementView(APIView, LimitOffsetPagination):
    serializer_class = AgreementSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin | IsModerator]

    def get(self, request):
        agreements_qs = Agreement.objects.all()
        paginated_qs = self.paginate_queryset(agreements_qs, request)
        serializer = self.serializer_class(paginated_qs, many=True)
        paginated_data = self.get_paginated_response(serializer.data)

        return Response(
            {
                "status": "success",
                "message": "Agreement list retrieved successfully.",
                **paginated_data.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Agreement added successfully.",
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


@extend_schema(tags=["Internal"])
class AgreementDetailView(APIView):
    serializer_class = AgreementSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin | IsModerator]

    def get(self, request, pk):
        try:
            agreement = Agreement.objects.get(pk=pk)
        except Agreement.DoesNotExist:
            return Response(
                {"errors": "Agreement not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(agreement)
        return Response(
            {
                "status": "success",
                "message": "Agreement successfully retrieved.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, pk):
        try:
            agreement = Agreement.objects.get(pk=pk)
        except Agreement.DoesNotExist:
            return Response(
                {
                    "status": "failed",
                    "message": "Agreement not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.serializer_class(
            agreement, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Agreement updated successfully.",
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

    def delete(self, request, pk):
        try:
            agreement = Agreement.objects.get(pk=pk)
        except Agreement.DoesNotExist:
            return Response(
                {
                    "status": "failed",
                    "message": "Agreement not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        agreement.archived = True
        agreement.save()
        return Response(
            {
                "status": "success",
                "message": "Agreement deleted successfully.",
            },
            status=status.HTTP_204_NO_CONTENT,
        )


class OrganizationView(APIView, LimitOffsetPagination):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, IsModerator | IsSuperAdmin]

    def get(self, request):
        organization = Organization.objects.all()
        paginated_queryset = self.paginate_queryset(organization, request)
        serializer = self.serializer_class(paginated_queryset, many=True)
        paginated_response = self.get_paginated_response(serializer.data)

        return Response(
            {
                "status": "success",
                "message": "Organization list retrieved successfully.",
                **paginated_response.data,
            },
            status=status.HTTP_200_OK,
        )
