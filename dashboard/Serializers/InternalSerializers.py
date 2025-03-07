import datetime
from rest_framework import serializers
from organizations.utils import create_organization
from organizations.models import Organization
from django.conf import settings
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from phonenumber_field.serializerfields import PhoneNumberField
from core.models import User, Role
from ..models import (
    InternalClient,
    ClientPointOfContact,
    InternalInterviewer,
    ClientUser,
    Agreement,
    HDIPUsers,
    DesignationDomain,
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


class InternalClientDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternalClient
        fields = ("id", "name", "domain")


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


class HDIPUserForInterClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = HDIPUsers
        fields = ("id", "name")


class InternalClientStatSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(max_length=155)
    active_jobs = serializers.IntegerField()
    passive_jobs = serializers.IntegerField()
    total_candidates = serializers.IntegerField()


class InternalClientSerializer(serializers.ModelSerializer):
    onboarded_at = serializers.DateTimeField(
        source="created_at", format="%d/%m/%Y", read_only=True
    )
    points_of_contact = ClientPointOfContactSerializer(many=True)
    assigned_to = HDIPUserForInterClientSerializer(read_only=True)

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


class DesignationDomainSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = DesignationDomain
        fields = ("id", "name", "full_name")

    def get_full_name(self, obj):
        role_choice = dict(InternalInterviewer.ROLE_CHOICES)
        return role_choice.get(obj.name)


class InterviewerSerializer(serializers.ModelSerializer):
    strength = serializers.ChoiceField(
        choices=InternalInterviewer.STRENGTH_CHOICES,
        error_messages={
            "invalid_choice": f"This is an invalid choice. Valid choices are {', '.join([f'{key}({value})' for key, value in InternalInterviewer.STRENGTH_CHOICES])}"
        },
        required=False,
    )
    assigned_domains = DesignationDomainSerializer(many=True, read_only=True)
    assigned_domain_ids = serializers.CharField(
        max_length=100,
        required=False,
        write_only=True,
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
            "assigned_domains",
            "assigned_domain_ids",
            "skills",
            "strength",
            "cv",
        )

    def run_validation(self, data=...):
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
                "assigned_domain_ids",
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
        if (
            "total_experience_years" in data
            and "interview_experience_years" in data
            and data["total_experience_years"] < data["interview_experience_years"]
        ):
            errors.setdefault("years", []).append(
                "Total experience must be greater than interview experience."
            )

        if "assigned_domain_ids" in data and isinstance(
            data["assigned_domain_ids"], str
        ):
            try:
                data["assigned_domain_ids"] = list(
                    map(int, data["assigned_domain_ids"].split(","))
                )
            except ValueError:
                raise serializers.ValidationError(
                    {
                        "assigned_domain_ids": [
                            "Assigned domain IDs must be comma-separated and consist of valid IDs."
                        ]
                    }
                )

        assigned_domain_ids = set(data.get("assigned_domain_ids", []))
        existing_domain_ids = set(
            DesignationDomain.objects.values_list("id", flat=True)
        )
        invalid_domain_ids = assigned_domain_ids - existing_domain_ids
        if invalid_domain_ids:
            errors.setdefault("assigned_domain_ids", []).append(
                f"Invalid domain IDs: {', '.join(map(str, invalid_domain_ids))}"
            )

        if errors:
            raise serializers.ValidationError({"errors": errors})
        return data

    def create(self, validated_data):
        email = validated_data.get("email")
        phone = validated_data.get("phone_number")
        name = validated_data.get("name")
        domain_ids = validated_data.pop("assigned_domain_ids", [])
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
            interviewer_obj.assigned_domains.add(*domain_ids)
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

    def update(self, instance, validated_data):
        email = validated_data.get("email", instance.email)
        phone = validated_data.get("phone_number", instance.phone_number)
        assigned_domain_ids = set(validated_data.get("assigned_domain_ids", []))

        with transaction.atomic():
            changes = {}

            if instance.email != email:
                instance.user.email = email
                changes["email"] = email

            if instance.phone_number != phone:
                instance.user.phone = phone
                changes["phone"] = phone

            if changes:
                instance.user.email_verified = False
                instance.user.phone_verified = False
                instance.user.save(
                    update_fields=["email", "phone", "email_verified", "phone_verified"]
                )

            instance.assigned_domains.set(assigned_domain_ids)
            instance = super().update(instance, validated_data)

            if changes:
                verification_data = f"{instance.user.id}:{int(datetime.datetime.now().timestamp() + 86400)}"
                verification_data_uid = urlsafe_base64_encode(
                    force_bytes(verification_data)
                )
                send_mail.delay(
                    email=email,
                    user_name=instance.name,
                    template=ONBOARD_EMAIL_TEMPLATE,
                    subject=WELCOME_MAIL_SUBJECT,
                    login_url=settings.LOGIN_URL,
                    site_domain=settings.SITE_DOMAIN,
                    verification_link=f"/verification/{verification_data_uid}/",
                )

        return instance


class AgreementSerializer(serializers.ModelSerializer):
    years_of_experience = serializers.ChoiceField(
        choices=Agreement.YEARS_OF_EXPERIENCE_CHOICES,
        error_messages={
            "invalid_choice": f"This is an invalid choice. Valid choices are {', '.join([f'{key}({value})' for key, value in Agreement.YEARS_OF_EXPERIENCE_CHOICES])}"
        },
        required=False,
    )
    organization_id = serializers.IntegerField(min_value=1, required=False)

    class Meta:
        model = Agreement
        fields = [
            "id",
            "organization_id",
            "years_of_experience",
            "rate",
        ]

    def validate(self, data):
        errors = validate_incoming_data(
            self.initial_data,
            required_keys=[
                "years_of_experience",
                "organization_id",
                "rate",
            ],
            partial=self.partial,
            original_data=data,
        )

        if "rate" in data and data["rate"] <= 0:
            errors.setdefault("rate", []).append("Rate must be a positive value.")

        if organization_id := data.get("organization_id"):
            if (
                not self.partial
                and Agreement.objects.filter(organization_id=organization_id).exists()
            ):
                errors.setdefault("organization_id", []).append(
                    "Organization already existed"
                )
            elif not Organization.objects.filter(id=organization_id).exists():
                errors.setdefault("organization_id", []).append(
                    "Invalid organization_id"
                )

        if errors:
            raise serializers.ValidationError({"errors": errors})

        return data


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
        )


class UserInternalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "phone", "role")


class ClientUserInternalSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternalClient
        fields = ("id", "name", "domain")


class InternalClientUserSerializer(serializers.ModelSerializer):

    email = serializers.EmailField(write_only=True, required=False)
    phone = PhoneNumberField(write_only=True, required=False)
    client = ClientUserInternalSerializer(
        source="organization.internal_client", read_only=True
    )
    user = UserInternalSerializer(read_only=True)
    internal_client_id = serializers.IntegerField(write_only=True, required=False)
    role = serializers.ChoiceField(
        choices=[
            ("client_user", "Client User"),
            ("client_admin", "Client Admin"),
        ],
        error_messages={
            "invalid_choice": (
                "This is an invalid choice. Valid choices are "
                "client_user(Client User), client_admin(Client Admin), "
            )
        },
        required=False,
    )
    accessibility = serializers.ChoiceField(
        choices=ClientUser.ACCESSIBILITY_CHOICES,
        error_messages={
            "invalid_choice": f"This is an invalid choice. Valid choices are {', '.join([f'{key}({value})' for key, value in ClientUser.ACCESSIBILITY_CHOICES])}"
        },
        required=False,
    )

    class Meta:
        model = ClientUser
        fields = [
            "id",
            "internal_client_id",
            "client",
            "user",
            "email",
            "phone",
            "name",
            "role",
            "accessibility",
        ]

    def run_validation(self, data):
        email = data.get("email")
        phone = data.get("phone")

        errors = check_for_email_and_phone_uniqueness(email, phone, User)
        if errors:
            raise serializers.ValidationError({"errors": errors})

        return super().run_validation(data)

    def validate(self, data):
        required_keys = [
            "email",
            "phone",
            "role",
            "accessibility",
            "internal_client_id",
            "name",
        ]
        allowed_keys = []
        if self.partial:
            required_keys = []
            allowed_keys = ["role", "accessibility", "name"]
        errors = validate_incoming_data(
            self.initial_data,
            required_keys=required_keys,
            allowed_keys=allowed_keys,
            partial=self.partial,
        )

        internal_client_id = data.pop("internal_client_id", None)
        if internal_client_id:
            internal_client = InternalClient.objects.filter(
                pk=internal_client_id
            ).first()
            if not internal_client:
                errors.setdefault("internal_client_id", []).append(
                    "Invalid internal_client_id"
                )
            self.context["internal_client"] = internal_client

        if errors:
            raise serializers.ValidationError({"errors": errors})

        return data

    def create(self, validated_data):
        email = validated_data.pop("email")
        phone = validated_data.pop("phone")
        role = validated_data.pop("role")
        internal_client = self.context["internal_client"]
        request = self.context["request"]
        password = get_random_password()

        with transaction.atomic():
            user = User.objects.create_user(email, phone, password, role=role)
            user.profile.name = validated_data.get("name")
            user.profile.save()
            validated_data["user"] = user
            validated_data["organization"] = internal_client.organization
            validated_data["invited_by"] = request.user
            client_user = super().create(validated_data)

            send_mail.delay(
                email=email,
                subject=WELCOME_MAIL_SUBJECT,
                template=ONBOARD_EMAIL_TEMPLATE,
                user_name=validated_data.get("name"),
                password=password,
                login_url=settings.LOGIN_URL,
            )
        return client_user

    def update(self, instance, validated_data):
        validated_data.pop("email", None)
        validated_data.pop("phone", None)
        role = validated_data.pop("role", None)

        with transaction.atomic():
            if role:
                instance.user.role = role
                instance.user.save()

            if "name" in validated_data:
                instance.user.profile.name = validated_data["name"]
                instance.user.profile.save()

            instance = super().update(instance, validated_data)

        return instance


class HDIPUsersSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(
        choices=[("moderator", "Moderator"), ("admin", "Admin")],
        error_messages={
            "invalid_choice": (
                "This is an invalid choice. Valid choices are "
                "moderator(Moderator), admin(Admin)"
            )
        },
        required=False,
    )
    email = serializers.EmailField(write_only=True, required=False)
    phone = PhoneNumberField(write_only=True, required=False)
    client_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        write_only=True,
        required=False,
    )
    user = UserInternalSerializer(read_only=True)
    client = ClientUserInternalSerializer(
        source="internalclients", many=True, read_only=True
    )

    class Meta:
        model = HDIPUsers
        fields = [
            "id",
            "name",
            "user",
            "client",
            "role",
            "email",
            "phone",
            "client_ids",
        ]

    def run_validation(self, data):
        email = data.get("email")
        phone = data.get("phone")

        errors = check_for_email_and_phone_uniqueness(email, phone, User)
        if errors:
            raise serializers.ValidationError({"errors": errors})

        return super().run_validation(data)

    def validate(self, data):
        required_keys = ["name", "email", "phone", "role"]
        allowed_keys = ["client_ids"]
        if self.partial:
            required_keys = []
            allowed_keys.extend(["role", "name"])

        errors = validate_incoming_data(
            self.initial_data,
            required_keys=required_keys,
            allowed_keys=allowed_keys,
            partial=self.partial,
        )

        client_ids = data.get("client_ids")
        if client_ids:
            existing_client_ids = set(
                InternalClient.objects.filter(pk__in=client_ids).values_list(
                    "id", flat=True
                )
            )
            already_assign_client_ids = set(
                HDIPUsers.objects.filter(internalclients__in=client_ids).values_list(
                    "internalclients", flat=True
                )
            )
            if self.partial:
                already_assign_client_ids -= set(
                    self.instance.internalclients.values_list("id", flat=True)
                )
            if not existing_client_ids:
                errors.setdefault("client_ids", []).append("Invalid client ids")
            elif already_assign_client_ids & existing_client_ids:
                errors.setdefault("client_ids", []).append(
                    f"These client ids are {', '.join(map(str, already_assign_client_ids & existing_client_ids))} already assigned to others."
                )
            else:
                invalid_ids = set(client_ids) - existing_client_ids
                if invalid_ids:
                    errors.setdefault("client_ids", []).append(
                        f"Invalid client ids: {', '.join(map(str, invalid_ids))}"
                    )

        if errors:
            raise serializers.ValidationError({"errors": errors})

        return data

    def create(self, validated_data):
        email = validated_data.pop("email")
        phone_number = validated_data.pop("phone")
        role = validated_data.pop("role")
        client_ids = validated_data.pop("client_ids", None)
        password = get_random_password()

        with transaction.atomic():
            user = User.objects.create_user(email, phone_number, password, role=role)
            user.profile.name = validated_data.get("name")
            user.profile.save()
            validated_data["user"] = user
            hdip_user = super().create(validated_data)
            if client_ids:
                InternalClient.objects.filter(pk__in=client_ids).update(
                    assigned_to=hdip_user
                )
            send_mail.delay(
                email=email,
                subject=WELCOME_MAIL_SUBJECT,
                template=ONBOARD_EMAIL_TEMPLATE,
                user_name=validated_data.get("name"),
                password=password,
                login_url=settings.LOGIN_URL,
            )
        return hdip_user

    def update(self, instance, validated_data):
        validated_data.pop("email", None)
        validated_data.pop("phone", None)
        role = validated_data.pop("role", None)
        client_ids = validated_data.pop("client_ids", None)

        with transaction.atomic():

            if role is not None:
                instance.user.role = role
                instance.user.save()

            if validated_data.get("name"):
                instance.user.profile.name = validated_data["name"]
                instance.user.profile.save()

            if client_ids is not None:
                current_client_ids = set(
                    InternalClient.objects.filter(assigned_to=instance).values_list(
                        "id", flat=True
                    )
                )
                new_client_ids = set(client_ids)
                clients_to_assign = new_client_ids - current_client_ids
                clients_to_unassign = current_client_ids - new_client_ids

                if clients_to_assign:
                    InternalClient.objects.filter(pk__in=clients_to_assign).update(
                        assigned_to=instance
                    )
                if clients_to_unassign:
                    InternalClient.objects.filter(pk__in=clients_to_unassign).update(
                        assigned_to=None
                    )

            super().update(instance, validated_data)

        return instance
