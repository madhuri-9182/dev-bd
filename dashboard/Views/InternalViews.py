from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from ..models import (
    InternalClient,
    InternalInterviewer,
)
from ..serializer import (
    InternalClientSerializer,
    InterviewerSerializer,
)


class InternalClientView(APIView, LimitOffsetPagination):
    serializer_class = InternalClientSerializer
    permission_classes = [IsAuthenticated]

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
            response.data["message"] = "Invalid data"
            errors = response.data["errors"]
            del response.data["errors"]
            response.data["errors"] = errors
        return super().finalize_response(request, response, *args, **kwargs)


class InternalClientDetailsView(APIView):
    def get(self, request, pk):
        try:
            client = InternalClient.objects.get(pk=pk)
        except InternalClient.DoesNotExist:
            return Response(
                {"errors": "Client not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = InternalClientSerializer(client)
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

        serializer = InternalClientSerializer(
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
            response.data["message"] = "Invalid data"
            errors = response.data["errors"]
            del response.data["errors"]
            response.data["errors"] = errors
        return super().finalize_response(request, response, *args, **kwargs)


class InterviewerView(APIView, LimitOffsetPagination):

    def get(self, request):
        interviewers_qs = InternalInterviewer.objects.all()
        paginated_qs = self.paginate_queryset(interviewers_qs, request)
        serializer = InterviewerSerializer(paginated_qs, many=True)
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
        serializer = InterviewerSerializer(data=request.data)
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
            response.data["message"] = "Invalid data"
            errors = response.data["errors"]
            del response.data["errors"]
            response.data["errors"] = errors
        return super().finalize_response(request, response, *args, **kwargs)


class InterviewerDetails(APIView):

    def get(self, request, pk):
        try:
            interviewer = InternalInterviewer.objects.get(pk=pk)
        except InternalInterviewer.DoesNotExist:
            return Response(
                {"errors": "Interviewer not found"}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = InterviewerSerializer(interviewer)
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

        serializer = InterviewerSerializer(interviewer, data=request.data, partial=True)
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
            response.data["message"] = "Invalid data"
            errors = response.data["errors"]
            del response.data["errors"]
            response.data["errors"] = errors
        return super().finalize_response(request, response, *args, **kwargs)
