from rest_framework import serializers
from ..models import ClientUser, InternalClient, ClientPointOfContact, InternalInterviewer
from hiringdogbackend.utils import validate_incoming_data



class ClientUserSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d/%m/%Y", read_only=True)
    job_assigned = serializers.CharField()

    class Meta:
        model = ClientUser
        fields = (
            "id",
            "user",
            "name",
            "email",
            "user_type",
            "job_assigned",
            "created_at",
        )

    def validate(self, data):
        errors = []
        if not self.partial:
            errors = validate_incoming_data(
                data, ["name", "email", "user_type", "job_assigned"]
            )

        valid_job_choices = {"sde3", "pe", "sde2", "devops1", "em", "sdet2", "sdet1"}
        job_assigned = data.get("job_assigned")

        if job_assigned and job_assigned not in valid_job_choices:
            errors.append(
                {
                    "job_assigned": "Invalid choice. Choices are sde3, pe, sde2, devops1, em, sdet2, sdet1."
                }
            )

        if errors:
            raise serializers.ValidationError({"error": errors})

        return data
    
    



class ClientPointOfContactSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d/%m/%Y", read_only=True)
    
    #archived = serializers.BooleanField(read_only=True)
    class Meta:
        model = ClientPointOfContact
        fields = ['id', 'name', 'email_id', 'mobile_no', 'created_at']
        read_only_fields = ['id', 'created_at'] 

    

class InternalClientSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d/%m/%Y", read_only=True)
    points_of_contact = ClientPointOfContactSerializer(many=True, required=True)
    #archived = serializers.BooleanField(read_only=True)

    class Meta:
        model = InternalClient
        fields = [
            'id',
            'user',
            'client_registered_name',
            'website',
            'domain',
            'gstin',
            'pan',
            'signed_or_not',
            'assigned_to',
            'address',
            'points_of_contact',
            'created_at',
           
        ]

    
    def validate_points_of_contact(self, value):
        
        #Ensure at least one point of contact is provided.
        
        if not value:
            raise serializers.ValidationError("Each client must have at least one point of contact.")
        return value


    def create(self, validated_data):
        
        #  Override the create method to handle nested points of contact.
        
        points_of_contact_data = validated_data.pop('points_of_contact')
        client = InternalClient.objects.create(**validated_data)

        # Create Point of Contact records
        for contact_data in points_of_contact_data:
            ClientPointOfContact.objects.create(client=client, **contact_data)
        return client

    def update(self, instance, validated_data):
        
        #Override the update method to handle nested points of contact.
        
        points_of_contact_data = validated_data.pop('points_of_contact', None)
        instance.client_registered_name = validated_data.get('client_registered_name', instance.client_registered_name)
        instance.website = validated_data.get('website', instance.website)
        instance.domain = validated_data.get('domain', instance.domain)
        instance.gstin = validated_data.get('gstin', instance.gstin)
        instance.pan = validated_data.get('pan', instance.pan)
        instance.signed_or_not = validated_data.get('signed_or_not', instance.signed_or_not)
        instance.assigned_to = validated_data.get('assigned_to', instance.assigned_to)
        instance.address = validated_data.get('address', instance.address)
        instance.archived = validated_data.get('archived', instance.archived)
        instance.save()

        if points_of_contact_data is not None:
            # Update or create points of contact
            for contact_data in points_of_contact_data:
                contact_id = contact_data.get('id', None)
                if contact_id:
                    contact = ClientPointOfContact.objects.get(id=contact_id, client=instance)
                    for attr, value in contact_data.items():
                        setattr(contact, attr, value)
                    contact.save()
                else:
                    ClientPointOfContact.objects.create(client=instance, **contact_data)
        return instance




        
    

class InterviewerSerializer(serializers.ModelSerializer):
    
    created_at = serializers.DateTimeField(format="%d/%m/%Y", read_only=True)
    updated_at = serializers.DateTimeField(format="%d/%m/%Y", read_only=True)

    class Meta:
        model = InternalInterviewer
        fields = (
            
            "name",
            "email",
            "phone_number",
            "current_company",
            "previous_company",
            "current_designation",
            "total_experience_years",
            "total_experience_months",
            "interview_experience_years",
            "interview_experience_months",
            "assigned_roles",
            "skills",
            "strength",
            "cv",
            "created_at",
            "updated_at",
        )

    def validate(self, data):
        # Ensure total experience is logical
        if "total_experience_years" < "interview_experience_years":
            raise serializers.ValidationError("Total experience must be greater than interview experience.")
        return data
