from .base import *

DEBUG = True

SECRET_KEY = "django-insecure-pn-#@uf@1!0lm!7p27d5^_)2)yw=6joel7qklh)8l(!p4fe_&_"

ALLOWED_HOSTS = []

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
