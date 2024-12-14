from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from ..models import ClientUser, InternalClient, ClientPointOfContact, InternalInterviewer
from ..serializer import ClientUserSerializer, InternalClientSerializer, ClientPointOfContactSerializer, InterviewerSerializer




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
# InternalClient Views
class InternalClientView(APIView , LimitOffsetPagination):
    internal_client_serializer = InternalClientSerializer
    permission_classes = [IsAuthenticated]
    
    
    def get(self, request):
        internal_clients = InternalClient.objects.filter(user=request.user).order_by("-id")
        paginated_queryset = self.paginate_queryset(internal_clients, request)
        serializer = self.internal_client_serializer(paginated_queryset, many=True)
        paginated_data = self.get_paginated_response(serializer.data)
        return Response(
            {
                "status" : "success",
                "message" : "client user retrieve successfully.",
                "data" : paginated_data.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = self.internal_client_serializer(data=request.data)
        serializer.is_valid(raise_exception= True)
        serializer.save(user = request.user)
        return Response(
            {
                "status": "success",
                "message": "Client user added successfully.",
                "data" : serializer.data,
            },
            status = status.HTTP_201_CREATED,
        )
        

        
class InternalClientDetailsView(APIView):
    def get(self, request, pk):
        try:
            client = InternalClient.objects.get(pk=pk)
        except InternalClient.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = InternalClientSerializer(client)
        return Response(
             {
                    "status": "success",
                    "message": "Client data retrieved successfully.",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK
                )

    def patch(self, request, pk):
        try:
            client = InternalClient.objects.get(pk=pk)
        except InternalClient.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InternalClientSerializer(client, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status": "success",
                    "message": "Client data updated successfully.",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            client = InternalClient.objects.get(pk=pk)
        except InternalClient.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        client.archived = True
        client.save()
        return Response({
                    "status": "success",
                    "message": "Client data deleted successfully.",    
                },
                status=status.HTTP_204_NO_CONTENT
                )

# ClientPointOfContact Views
class ClientPointOfContactView(APIView):
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, client_id):
        try:
            client = InternalClient.objects.get(pk=client_id)
        except InternalClient.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)
        
        contacts = client.points_of_contact.all()
        serializer = ClientPointOfContactSerializer(contacts, many=True)
        return Response(
            {
                "status" : "success",
                "message" : "contact successfully retrived",
                "data" : serializer.data,
                },
                status=status.HTTP_200_OK
        )
    
    
   

    def post(self, request, client_id):
        try:
            client = InternalClient.objects.get(pk=client_id)
        except InternalClient.DoesNotExist:
            return Response({'error': 'Client not found'}, status=status.HTTP_404_NOT_FOUND)

        request.data['client'] = client.id
        
        serializer = ClientPointOfContactSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status" : "success",
                    "message" : "contact created successfully.",
                    "data" : serializer.data,
                },
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    
    


class ClientPointOfContactDetailsView(APIView):
    def get(self, request, client_id, contact_id):
        try:
            client = InternalClient.objects.get(pk=client_id)
            contact = client.points_of_contact.get(pk=contact_id)
        except (ClientPointOfContact.DoesNotExist, ClientPointOfContact.DoesNotExist):
            return Response({'error': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ClientPointOfContactSerializer(contact)
        return Response(
            {
                "status" : "success",
                "message" : "contact successfully retrived",
                "data" : serializer.data,
                },
                status=status.HTTP_200_OK
            )
        

    def patch(self, request, client_id, contact_id):
        try:
            client = InternalClient.objects.get(pk=client_id)
            contact = client.points_of_contact.get(pk=contact_id)
        except (InternalClient.DoesNotExist, ClientPointOfContact.DoesNotExist):
            return Response({'error': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClientPointOfContactSerializer(contact, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "status" : "success",
                    "message" : "contact successfully edited",
                    "data" : serializer.data,
                },
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, client_id, contact_id):
        try:
            client = InternalClient.objects.get(pk=client_id)
            contact = client.points_of_contact.get(pk=contact_id)
        except (InternalClient.DoesNotExist, ClientPointOfContact.DoesNotExist):
            return Response({'error': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)

        contact.archived = True
        contact.save()
        return Response(
            {
                "status" : "success",
                "message" : "contact successfully deleted",
            },
                status=status.HTTP_204_NO_CONTENT
            )


class InterviewerView(APIView):
    
    
    def get(self, request):
        interviewers = InternalInterviewer.objects.all()
        serializer = InterviewerSerializer(interviewers, many=True)
        return Response(
            {
                "status": "success",
                "message": "Interviewer list retrieved successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
    

    def post(self, request):
        serializer = InterviewerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "status": "success",
                "message": "Interviewer added successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )
        
class InterviewerDetails(APIView):
        
    def get(self, request, pk):
        try:
            interviewer = InternalInterviewer.objects.get(pk=pk)
        except InternalInterviewer.DoesNotExist:
            return Response({"error": "Interviewer not found"}, status=status.HTTP_404_NOT_FOUND)

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
            return Response({"error": "Interviewer not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = InterviewerSerializer(interviewer, data=request.data, partial=True)
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
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            interviewer = InternalInterviewer.objects.get(pk=pk)
            interviewer.archived = True
            interviewer.save()
            return Response({"message": "Interviewer deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
        except InternalInterviewer.DoesNotExist:
            return Response({"error": "Interviewer not found"}, status=status.HTTP_404_NOT_FOUND)
