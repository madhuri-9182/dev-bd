from django.db import models


class SoftDelete(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(archived=False)
