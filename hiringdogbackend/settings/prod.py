from .base import *

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = ["localhost"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("MYSQL_DATABASE"),
        "HOST": os.environ.get("MYSQL_DATABASE_HOST"),
        "USER": os.environ.get("MYSQL_DATABASE_USER_NAME"),
        "PASSWORD": os.environ.get("MYSQL_ROOT_PASSWORD"),  # "Sumit@Dey",
        "PORT": "3306",
    }
}
