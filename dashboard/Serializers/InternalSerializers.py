import datetime
from rest_framework import serializers
from organizations.utils import create_organization
from django.conf import settings
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from core.models import User, Role
from ..models import (
    InternalClient,
    ClientPointOfContact,
    InternalInterviewer,
    ClientUser,
)
from hiringdogbackend.utils import (
    validate_incoming_data,
    get_random_password,
    is_valid_gstin,
    is_valid_pan,
    get_boolean,
    check_for_email_and_phone_uniqueness,
)
from ..tasks import send_mail

ONBOARD_EMAIL_TEMPLATE = "onboard.html"
WELCOME_MAIL_SUBJECT = "Welcome to Hiring Dog"


class ClientPointOfContactSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%d/%m/%Y", read_only=True)

    class Meta:
        model = ClientPointOfContact
        fields = ["id", "name", "email", "phone", "created_at"]
        read_only_fields = ["created_at"]

    def run_validation(self, data=...):
        email = data.get("email")
        phone = data.get("phone")

        errors = check_for_email_and_phone_uniqueness(email, phone, User)
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
    onboarded_at = serializers.DateTimeField(
        source="created_at", format="%d/%m/%Y", read_only=True
    )
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
            "onboarded_at",
        )

    def to_internal_value(self, data):
        request = self.context.get("request")
        points_of_contact = data.get("points_of_contact")
        errors = {}
        if not points_of_contact:
            errors.setdefault("points_of_contact", []).append(
                "This field is required and must contain list of objects."
            )

        if not isinstance(points_of_contact, list):
            errors.setdefault("points_of_contact", []).append(
                "This field must be a list of objects."
            )

        if points_of_contact and len(points_of_contact) > 3:
            errors.setdefault("points_of_contact", []).append(
                "A maximum of 3 points of contact are allowed."
            )

        if errors:
            raise serializers.ValidationError(errors)

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
            raise serializers.ValidationError(errors)

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
            errors.setdefault("gstin", []).append("Invalid gstin.")

        if data.get("pan") and not is_valid_pan(data.get("pan")):
            errors.setdefault("pan", []).append("Invalid PAN.")

        if errors:
            raise serializers.ValidationError({"errors": errors})

        return data

    def create(self, validated_data):
        points_of_contact_data = validated_data.pop("points_of_contact")
        organization_name = validated_data.get("name")

        with transaction.atomic():
            organization = None
            client_user_objs = []
            points_of_contact_objs = []

            for index, point_of_contact in enumerate(points_of_contact_data):
                email = point_of_contact.get("email")
                name_ = point_of_contact.get("name")
                password = get_random_password()

                role = Role.CLIENT_OWNER if index == 0 else Role.CLIENT_ADMIN
                user = User.objects.create_user(
                    email,
                    point_of_contact.get("phone"),
                    password,
                    role=role,
                )

                if index == 0:
                    organization = create_organization(
                        user, organization_name, is_active=False
                    )
                """ 
                else:
                    # Not using OrganizationUser for now, instead UserProfile works as a organization user
                    # because it has a foreign key with organization
                    OrganizationUser.objects.create(
                        organization=organization, user=user
                    )
                """

                points_of_contact_objs.append(
                    ClientPointOfContact(client=None, **point_of_contact)
                )
                client_user_objs.append(
                    ClientUser(organization=organization, user=user, name=name_)
                )
                user.profile.name = name_
                user.profile.organization = organization
                user.profile.save()

                point_of_contact["temporary_password"] = password

            client = InternalClient.objects.create(
                organization=organization, **validated_data
            )

            for poc in points_of_contact_objs:
                poc.client = client

            ClientPointOfContact.objects.bulk_create(points_of_contact_objs)
            ClientUser.objects.bulk_create(client_user_objs)

            def send_email_for_pocs():
                for point_of_contact in points_of_contact_data:
                    email = point_of_contact.get("email")
                    name_ = point_of_contact.get("name")
                    temporary_password = point_of_contact.get("temporary_password")

                    send_mail.delay(
                        email=email,
                        subject=WELCOME_MAIL_SUBJECT,
                        template=ONBOARD_EMAIL_TEMPLATE,
                        user_name=name_,
                        password=temporary_password,
                        login_url=settings.LOGIN_URL,
                    )

            # Queue the email sending after the transaction is committed
            transaction.on_commit(send_email_for_pocs)

        return client

    def update(self, instance, validated_data):
        point_of_contact_data = validated_data.pop("points_of_contact")

        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()

        existing_contacts = ClientPointOfContact.objects.filter(client=instance)
        existing_contacts_dict = {contact.id: contact for contact in existing_contacts}
        contact_ids = self.context.get("contact_ids")

        to_archive = existing_contacts.exclude(id__in=contact_ids)
        for contact in to_archive:
            User.objects.filter(email=contact.email).update(is_active=False)
            contact.archived = True
            contact.save()

        for index, point_of_contact in enumerate(point_of_contact_data):
            contact_id = contact_ids[index] if index < len(contact_ids) else None

            """ --> keep it for future reference.
                if not contact_id and len(existing_contacts_dict) >= 3:
                    raise serializers.ValidationError(
                        {
                            "errors": {
                                "points_of_contact": [
                                    "Maximum 3 points of contact are allowed"
                                ]
                            }
                        }
                    )
            """

            if contact_id in existing_contacts_dict:
                contact = existing_contacts_dict[contact_id]
                point_of_contact.pop("email", None)
                point_of_contact.pop("phone", None)
                for key, value in point_of_contact.items():
                    setattr(contact, key, value)
                contact.save()
            else:
                email = point_of_contact.get("email")
                name = point_of_contact.get("name")
                password = get_random_password()
                user = User.objects.create_user(
                    email,
                    point_of_contact.get("phone"),
                    password,
                    role=Role.CLIENT_ADMIN,
                )
                send_mail.delay(
                    email=email,
                    subject=WELCOME_MAIL_SUBJECT,
                    template=ONBOARD_EMAIL_TEMPLATE,
                    user_name=name,
                    password=password,
                    login_url=settings.LOGIN_URL,
                )
                user.profile.name = name
                user.profile.save()
                ClientPointOfContact.objects.create(client=instance, **point_of_contact)

        return instance


class InterviewerSerializer(serializers.ModelSerializer):
    assigned_roles = serializers.ChoiceField(
        choices=InternalInterviewer.ROLE_CHOICES,
        error_messages={
            "invalid_choice": f"This is an invalid choice. Valid choices are {', '.join([f'{key}({value})' for key, value in InternalInterviewer.ROLE_CHOICES])}"
        },
        required=False,
    )
    strength = serializers.ChoiceField(
        choices=InternalInterviewer.STRENGTH_CHOICES,
        error_messages={
            "invalid_choice": f"This is an invalid choice. Valid choices are {', '.join([f'{key}({value})' for key, value in InternalInterviewer.STRENGTH_CHOICES])}"
        },
        required=False,
    )

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

        email = data.get("email")
        phone = data.get("phone_number")
        errors = check_for_email_and_phone_uniqueness(email, phone, User)
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
            ],
            partial=self.partial,
            original_data=data,
            form=True,
        )
        if errors:
            raise serializers.ValidationError({"errors": errors})
        for key in ["total_experience_years", "interview_experience_years"]:
            if key in data and not 1 <= data[key] <= 50:
                errors.setdefault(key, []).append("Invalid Experience")
        for key in ["total_experience_months", "interview_experience_months"]:
            if key in data and not 0 <= data[key] <= 12:
                errors.setdefault(key, []).append("Invalid Experience")
        if "total_experience_years" < "interview_experience_years":
            errors.setdefault("years", []).append(
                "Total experience must be greater than interview experience."
            )
        if errors:
            raise serializers.ValidationError({"errors": errors})
        return data

    def create(self, validated_data):
        email = validated_data.get("email")
        phone = validated_data.get("phone_number")
        name = validated_data.get("name")
        password = get_random_password()
        with transaction.atomic():
            user = User.objects.create_user(
                email,
                phone,
                password,
                role=Role.INTERVIEWER,
            )
            interviewer_obj = InternalInterviewer.objects.create(
                user=user, **validated_data
            )
            verification_data = (
                f"{user.id}:{int(datetime.datetime.now().timestamp() + 86400)}"
            )
            verification_data_uid = urlsafe_base64_encode(
                force_bytes(verification_data)
            )
            send_mail.delay(
                email=email,
                user_name=name,
                template=ONBOARD_EMAIL_TEMPLATE,
                password=password,
                subject=WELCOME_MAIL_SUBJECT,
                login_url=settings.LOGIN_URL,
                site_domain=settings.SITE_DOMAIN,
                verification_link=f"/verification/{verification_data_uid}/",
            )
            user.profile.name = name
            user.profile.save()
        return interviewer_obj
