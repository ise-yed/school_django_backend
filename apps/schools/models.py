from django.db import models
from apps.core.models import TimeStampedModel


class School(TimeStampedModel):
    name = models.CharField(max_length=150, verbose_name="نام مدرسه")
    code = models.SlugField(max_length=50, unique=True, verbose_name="کد یکتای مدرسه")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "مدرسه"
        verbose_name_plural = "مدارس"
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} ({self.code})"