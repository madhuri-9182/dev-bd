from django.db import models, IntegrityError
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, Group
from django.core.exceptions import ValidationError
from phonenumber_field.modelfields import PhoneNumberField
from organizations.models import Organization
from hiringdogbackend.ModelUtils import CreateUpdateDateTimeAndArchivedField


class Role(models.TextChoices):
    SUPER_ADMIN = ("super_admin", "Super Admin")
    MODERATOR = ("moderator", "Moderator")
    CLIENT_ADMIN = ("client_admin", "Client Admin")
    CLIENT_OWNER = ("client_owner", "Client Owner")
    CLIENT_USER = ("client_user", "Client User")
    USER = ("user", "User")
    INTERVIEWER = ("interviewer", "Interviewer")
    AGENCY = ("agency", "Agency")


class UserManager(BaseUserManager):
    def create_user(self, email, phone, password=None, **extra_field):
        if not email:
            raise ValueError("User must have an email address")
        if not phone:
            raise ValueError("User must have a phone number")

        user = self.model(
            email=self.normalize_email(email),
            phone=phone,
            **extra_field,
        )
        user.set_password(password)
        try:
            user.save(using=self._db)
        except IntegrityError as e:
            if "phone" in str(e):
                raise ValidationError("phone number already taken.")
            else:
                raise e
        return user

    def create_superuser(self, email, phone, password=None, **extra_field):
        if not email:
            raise ValueError("Admin must have an email address")
        if not phone:
            raise ValueError("Admin must have a phone number")
        user = self.create_user(email, phone, password, **extra_field)
        user.is_admin = True
        user.is_active = True
        user.role = Role.SUPER_ADMIN
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    email = models.EmailField(max_length=255, unique=True)
    phone = PhoneNumberField(region="IN", unique=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    role = models.CharField(max_length=15, choices=Role.choices, default=Role.USER)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone"]

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        if self.is_admin:
            return True
        return Group.objects.filter(
            name=self.role, permissions__codename=perm.split(".")[1]
        ).exists()

    def has_module_perms(self, app_label):
        return self.is_admin

    @property
    def is_staff(self):
        return self.is_admin

    class Meta:
        indexes = [models.Index(fields=["email", "phone"])]


class UserProfile(CreateUpdateDateTimeAndArchivedField):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="profiles", null=True
    )  # comment this when you run you first makemigration command
    name = models.CharField(max_length=100, help_text="User's Full Name")

    def __str__(self) -> str:
        return f"{self.name} ({self.user.email})"

    class Meta:
        indexes = [models.Index(fields=["name"])]


class ClientCustomRole(Group):
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="clientcustomrole"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="clientcustomrole"
    )  # comment this when you run you first makemigration command
