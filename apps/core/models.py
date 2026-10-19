from django.conf import settings
from django.db import models


class SchoolQuerySet(models.QuerySet):
    def for_school(self, school):
        if school is None:
            return self.none()
        return self.filter(school=school)


class SchoolManager(models.Manager):
    def get_queryset(self):
        return SchoolQuerySet(self.model, using=self._db)

    def for_school(self, school):
        return self.get_queryset().for_school(school)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ ویرایش")

    class Meta:
        abstract = True


class SchoolOwnedModel(TimeStampedModel):
    school = models.ForeignKey(
        "schools.School",
        on_delete=models.CASCADE,
        db_index=True,
        related_name="%(class)ss",
        verbose_name="مدرسه",
    )

    objects = SchoolManager()

    class Meta:
        abstract = True


class AuditLog(SchoolOwnedModel):
    class Action(models.TextChoices):
        CREATE = "CREATE", "ایجاد"
        UPDATE = "UPDATE", "ویرایش"
        DELETE = "DELETE", "حذف"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_logs",
        verbose_name="انجام‌دهنده",
    )
    action = models.CharField(max_length=10, choices=Action.choices)
    target_model = models.CharField(max_length=100)
    target_id = models.CharField(max_length=64)
    changes = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "لاگ تغییرات"
        verbose_name_plural = "لاگ‌های تغییرات"
        indexes = [
            models.Index(fields=["school", "target_model", "target_id"]),
            models.Index(fields=["school", "created_at"]),
        ]