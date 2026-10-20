from django.conf import settings
from django.db import models
from apps.core.models import SchoolOwnedModel


class ImportMapping(SchoolOwnedModel):
    name = models.CharField(max_length=100, default="پیش‌فرض", verbose_name="نام الگو")
    mapping_config = models.JSONField(default=dict, verbose_name="تنظیمات نگاشت ستون‌ها")

    class Meta:
        verbose_name = "الگوی نگاشت اکسل"
        verbose_name_plural = "الگوهای نگاشت اکسل"
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "name"],
                name="uq_importmapping_school_name",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.school.name})"


class ImportLog(SchoolOwnedModel):
    class Status(models.TextChoices):
        ANALYZED = "ANALYZED", "تحلیل اولیه"
        PREVIEWED = "PREVIEWED", "پیش‌نمایش"
        COMMITTED = "COMMITTED", "نهایی‌شده"
        FAILED = "FAILED", "خطا"

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="import_logs",
        verbose_name="آپلودکننده",
    )
    target_classroom = models.ForeignKey(
        "schools.Classroom",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_logs",
        verbose_name="کلاس مقصد",
    )
    file = models.FileField(upload_to="imports/%Y/%m/", verbose_name="فایل اکسل")
    original_filename = models.CharField(max_length=255, blank=True)
    sheet_name = models.CharField(max_length=100, blank=True)
    header_row = models.PositiveSmallIntegerField(default=1)
    mapping_used = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ANALYZED
    )
    total_rows = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    errors_detail = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "لاگ ایمپورت اکسل"
        verbose_name_plural = "لاگ‌های ایمپورت اکسل"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Import #{self.id} - {self.original_filename} ({self.status})"