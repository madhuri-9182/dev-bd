from drf_spectacular.utils import extend_schema
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
)


@extend_schema(tags=["Internal"])
class InternalClientView(APIView, LimitOffsetPagination):
    serializer_class = InternalClientSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin | IsModerator]

    def get(self, request):
        internal_clients = InternalClient.objects.prefetch_related(
            "points_of_contact"
        ).all()
        paginated_queryset = self.paginate_queryset(internal_clients, request)
        serializer = self.serializer_class(paginated_queryset, many=True)
        paginated_data = self.get_paginated_response(serializer.data)
        return Response(
            {
                "status": "success",
                "message": "Client user retrieve successfully.",
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
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
        interviewers_qs = InternalInterviewer.objects.all()
        paginated_qs = self.paginate_queryset(interviewers_qs, request)
        serializer = self.serializer_class(paginated_qs, many=True)
        paginated_data = self.get_paginated_response(serializer.data)

        return Response(
            {
                "status": "success",
                "message": "Interviewer list retrieved successfully.",
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
            interviewer.save()
            return Response(
                {"message": "Interviewer deleted successfully"},
                status=status.HTTP_204_NO_CONTENT,
            )
        except InternalInterviewer.DoesNotExist:
            return Response(
                {"errors": "Interviewer not found"}, status=status.HTTP_404_NOT_FOUND
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
