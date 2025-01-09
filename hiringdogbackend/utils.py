import re
import string
import secrets
from django.conf import settings
from django.core.validators import EmailValidator
from django.core.exceptions import ValidationError
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from typing import Dict, List, Any


def validate_incoming_data(
    data: Dict[str, any],
    required_keys: List[str],
    allowed_keys: List[str] = [],
    partial: bool = False,
    original_data: Dict[str, any] = {},
    form: bool = False,
) -> List[Dict[str, str]]:

    errors: List[Dict[str, str]] = []
    if not partial:
        for key in required_keys:
            if key not in data or (form and original_data.get(key) == ""):
                errors.append({key: "This is a required key."})

    for key in data:
        if key not in required_keys + allowed_keys:
            errors.append({key: "Unexpected key"})

    return errors


def get_random_password(length: int = 10) -> str:
    characters = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(secrets.choice(characters) for _ in range(length))


def is_valid_gstin(value: str | None, exact_check: bool = True) -> bool:
    if exact_check:
        if not re.fullmatch(settings.REGEX_GSTIN, value.strip()):
            return False
    else:
        if not re.fullmatch(settings.REGEX_GSTIN_BASIC, value.strip()):
            return False
    return True


def is_valid_pan(
    value: str,
    exact_check: bool = True,
) -> bool:
    if exact_check:
        valid = re.search(settings.REGEX_PAN, value)
        if valid:
            return True
    else:
        valid = re.search(settings.REGEX_PAN_BASIC, value)
        if valid:
            return True
    return False


def get_boolean(data: dict, key: str) -> bool:
    return True if str(data.get(key)).lower() == "true" else False


def check_for_email_and_phone_uniqueness(
    email: str, phone: str, user
) -> List[Dict[str, str]]:
    errors = []
    if email:
        try:
            EmailValidator()(email)
        except ValidationError:
            errors.append({"email": "Invalid email"})
        if user.objects.filter(email=email).exists():
            errors.append({"email": "This email is already used."})

    if phone:
        if (
            not isinstance(phone, str)
            or len(phone) != 13
            or not phone.startswith("+91")
        ):
            errors.append({"phone": "Invalid phone number"})
        elif user.objects.filter(phone=phone).exists():
            errors.append({"phone": "This phone is already used."})

    return errors


def validate_attachment(
    field_name: str,
    file,
    allowed_extensions: List[str],
    max_size_mb: int,
) -> List[Dict[str, str]]:
    errors = []

    if file.size > max_size_mb * 1024 * 1024:
        errors.append(
            {field_name: f"File size must be less than or equal to {max_size_mb}MB"}
        )

    file_extension = file.name.split(".")[-1].lower()
    if file_extension not in allowed_extensions:
        errors.append(
            {field_name: f"File type must be one of {', '.join(allowed_extensions)}"}
        )

    return errors


def validate_json(
    json_data: Dict[str, Any], field_name: str, schema: Dict[str, Any]
) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []

    try:
        validate(instance=json_data, schema=schema)
    except ValidationError as e:
        errors.append({field_name: f"Invalid JSON: {str(e)}"})
    return errors
