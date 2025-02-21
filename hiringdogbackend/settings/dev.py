from .base import *
import sys

DEBUG = len(sys.argv) > 1 and sys.argv[1] == "runserver"

SECRET_KEY = "django-insecure-pn-#@uf@1!0lm!7p27d5^_)2)yw=6joel7qklh)8l(!p4fe_&_"

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


GOOGLE_API_KEY = "AIzaSyBIi5-B03yNolwRaQeWzy4n-XFpSUdzJBo"
