from .base import *

DEBUG = True

SECRET_KEY = "django-insecure-pn-#@uf@1!0lm!7p27d5^_)2)yw=6joel7qklh)8l(!p4fe_&_"

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
]
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


REGEX_GSTIN_BASIC = r"^(?=.*[a-zA-Z])(?=.*\d)[a-zA-Z\d]{15}$"
REGEX_GSTIN = "^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
REGEX_PAN = r"^[A-Za-z]{5}[0-9]{4}[A-Za-z]$"
REGEX_PAN_BASIC = r"^(?=.*[a-zA-Z])(?=.*\d)[a-zA-Z\d]{10}$"
