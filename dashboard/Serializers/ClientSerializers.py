from rest_framework import serializers
from organizations.utils import create_organization
from phonenumber_field.serializerfields import PhoneNumberField
from core.models import User, Role
from ..models import (
    ClientUser,
    InternalClient,
    ClientPointOfContact,
    InternalInterviewer,
)
from hiringdogbackend.utils import (
    validate_incoming_data,
    get_random_password,
    is_valid_gstin,
    is_valid_pan,
    get_boolean,
)


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
            raise serializers.ValidationError({"errors": errors})

        return data


class ClientPointOfContactSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d/%m/%Y", read_only=True)

    class Meta:
        model = ClientPointOfContact
        fields = ["id", "name", "email", "phone", "created_at"]
        read_only_fields = ["created_at"]

    def run_validation(self, data=...):
        errors = []
        email = data.get("email")
        phone = data.get("phone")
        if User.objects.filter(email=email).exists():
            errors.append({"email": "This email is already used."})
        if User.objects.filter(phone=phone).exists():
            errors.append({"phone": "This phone is already used."})
        if errors:
            raise serializers.ValidationError({"errors": errors})
        return super().run_validation(data)

    def validate(self, data):
        errors = validate_incoming_data(
            data,
            ["name", "email", "phone"],
            partial=self.partial,
        )
        if errors:
            raise serializers.ValidationError({"errors": errors})
        return data


class InternalClientSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d/%m/%Y", read_only=True)
    points_of_contact = ClientPointOfContactSerializer(many=True)

    class Meta:
        model = InternalClient
        fields = (
            "id",
            "name",
            "website",
            "domain",
            "gstin",
            "pan",
            "is_signed",
            "assigned_to",
            "address",
            "points_of_contact",
            "created_at",
        )

    def to_internal_value(self, data):
        request = self.context.get("request")
        points_of_contact = data.get("points_of_contact")
        if not points_of_contact:
            raise serializers.ValidationError(
                {
                    "errors": {
                        "points_of_contact": "This field is required and must contain list of objects."
                    }
                }
            )

        if not isinstance(points_of_contact, list):
            raise serializers.ValidationError(
                {
                    "errors": {
                        "points_of_contact": "This field must be a list of objects."
                    }
                }
            )
        if len(points_of_contact) > 3:
            raise serializers.ValidationError(
                {
                    "errors": {
                        "points_of_contact": "A maximum of 3 points of contact are allowed."
                    }
                }
            )
        errors = {}
        contact_ids = []
        for i, contact in enumerate(points_of_contact):
            if contact.get("id"):
                contact["email"] = ""
                contact["phone"] = ""
                contact_ids.append(contact.get("id"))
            serializer = ClientPointOfContactSerializer(data=contact)
            if not serializer.is_valid():
                errors[f"{i + 1}"] = serializer.errors["errors"]

        if errors:
            raise serializers.ValidationError(
                {"errors": {"points_of_contact": {**errors}}}
            )

        self.context["contact_ids"] = contact_ids

        return super().to_internal_value(data)

    def run_validation(self, data=...):
        if data.get("is_signed"):
            data["is_signed"] = get_boolean(data, "is_signed")
        return super().run_validation(data)

    def validate(self, data):
        errors = validate_incoming_data(
            self.initial_data,
            [
                "name",
                "website",
                "domain",
                "gstin",
                "pan",
                "is_signed",
                "assigned_to",
                "address",
                "points_of_contact",
            ],
            partial=self.partial,
        )
        if errors:
            raise serializers.ValidationError({"errors": errors})

        if data.get("gstin") and not is_valid_gstin(data.get("gstin")):
            errors.append({"gstin": "Invalid GSTIN."})

        if data.get("pan") and not is_valid_pan(data.get("pan")):
            errors.append({"pan": "Invalid PAN."})

        if errors:
            raise serializers.ValidationError({"errors": errors})

        return data

    def create(self, validated_data):
        points_of_contact_data = validated_data.pop("points_of_contact")
        name = validated_data.get("name")

        user_and_points_of_contact = []
        for _, point_of_contact in enumerate(points_of_contact_data):
            user = User.objects.create_user(
                point_of_contact.get("email"),
                point_of_contact.get("phone"),
                get_random_password(),
                role=Role.CLIENT,
            )
            if _ == 0:
                organization = create_organization(user, name, is_active=False)
            user_and_points_of_contact.append((user, organization, point_of_contact))

        client = InternalClient.objects.create(
            organization=organization, **validated_data
        )

        points_of_contact = []
        for user, _, point_of_contact in user_and_points_of_contact:
            points_of_contact.append(
                ClientPointOfContact(client=client, **point_of_contact)
            )
        ClientPointOfContact.objects.bulk_create(points_of_contact)

        return client

    def update(self, instance, validated_data):
        points_of_contact_data = validated_data.pop("points_of_contact")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        existing_contacts = ClientPointOfContact.objects.filter(client=instance)
        existing_contacts_dict = {contact.id: contact for contact in existing_contacts}
        contact_ids = self.context.get("contact_ids")

        to_archive = existing_contacts.exclude(id__in=contact_ids)
        for contact in to_archive:
            User.objects.filter(email=contact.email).update(is_active=False)
            contact.archived = True
            contact.save()

        for index, contact_data in enumerate(points_of_contact_data):
            contact_id = contact_ids[index] if index < len(contact_ids) else None

            if contact_id in existing_contacts_dict:
                contact = existing_contacts_dict[contact_id]
                contact_data.pop("email", None)
                contact_data.pop("phone", None)
                for key, value in contact_data.items():
                    setattr(contact, key, value)
                contact.save()
            else:
                user = User.objects.create_user(
                    contact_data.get("email"),
                    contact_data.get("phone"),
                    get_random_password(),
                    role=Role.CLIENT,
                )
                ClientPointOfContact.objects.create(client=instance, **contact_data)

        return instance


class InterviewerSerializer(serializers.ModelSerializer):

    class Meta:
        model = InternalInterviewer
        fields = (
            "id",
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
        )

    def run_validation(self, data=...):

        if self.partial:
            data.pop("email", None)
            data.pop("phone_number", None)

        errors = []
        email = data.get("email")
        phone = data.get("phone_number")
        strength = data.get("strength")
        if User.objects.filter(email=email).exists():
            errors.append({"email": "This email is already used."})
        if User.objects.filter(phone=phone).exists():
            errors.append({"phone": "This phone is already used."})
        if strength and strength not in [
            "frontend",
            "backend",
            "devops",
            "aiml",
            "data_engineer",
        ]:
            errors.append(
                {
                    "strength": "Invalid strength type. Valid types are frontend, backend, devops, aiml and data_engineer."
                }
            )
        if errors:
            raise serializers.ValidationError({"errors": errors})
        return super().run_validation(data)

    def validate(self, data):
        # Ensure total experience is logical
        errors = validate_incoming_data(
            self.initial_data,
            required_keys=[
                "name",
                "email",
                "phone_number",
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
            ],
            partial=self.partial,
            original_data=data,
            form=True,
        )
        if errors:
            raise serializers.ValidationError({"errors": errors})
        for key in ["total_experience_years", "interview_experience_years"]:
            if key in data and not 1 <= data[key] <= 50:
                errors.append({key: "Invalid Experience"})
        for key in ["total_experience_months", "interview_experience_months"]:
            if key in data and not 0 <= data[key] <= 12:
                errors.append({key: "Invalid Experience"})
        if "total_experience_years" < "interview_experience_years":
            errors.append(
                {"years": "Total experience must be greater than interview experience."}
            )
        if errors:
            raise serializers.ValidationError({"errors": errors})
        return data

    def create(self, validated_data):
        email = validated_data.get("email")
        phone = validated_data.get("phone_number")
        User.objects.create_user(
            email,
            phone,
            get_random_password(),
            role=Role.INTERVIEWER,
        )
        return super().create(validated_data)
