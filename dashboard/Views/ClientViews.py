from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from ..models import ClientUser
from ..serializer import ClientUserSerializer


class ClientUserView(APIView, LimitOffsetPagination):
    serializer_class = ClientUserSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        client_user_qs = ClientUser.objects.filter(user=request.user).order_by("-id")
        paginated_queryset = self.paginate_queryset(client_user_qs, request)
        serializer = self.serializer_class(paginated_queryset, many=True)
        paginated_data = self.get_paginated_response(serializer.data)
        return Response(
            {
                "status": "success",
                "message": "Client user retrieve successfully.",
                "data": paginated_data.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(
            {
                "status": "success",
                "message": "Client user added successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request):
        return self._update_delete_client_user(request, partial=True)

    def delete(self, request):
        return self._update_delete_client_user(request)

    def _update_delete_client_user(self, request, partial=False):
        """Update or delete a client user."""
        client_user_id = request.query_params.get("client_user_id")
        if not client_user_id or not client_user_id.isdigit():
            return Response(
                {
                    "status": "failed",
                    "message": "Invalid client_user_id in query_params.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        client_user_obj = ClientUser.objects.filter(
            user=request.user, pk=client_user_id
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
