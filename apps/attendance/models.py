from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from apps.core.models import SchoolOwnedModel


class AttendanceRecord(SchoolOwnedModel):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "حاضر"
        EXCUSED_ABSENCE = "EXCUSED_ABSENCE", "غایب موجه"
        UNEXCUSED_ABSENCE = "UNEXCUSED_ABSENCE", "غایب غیرموجه"
        LATE = "LATE", "تأخیر"

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="attendance_records",
        verbose_name="دانش‌آموز",
    )
    classroom = models.ForeignKey(
        "schools.Classroom",
        on_delete=models.CASCADE,
        related_name="attendance_records",
        verbose_name="کلاس",
    )
    date = models.DateField(verbose_name="تاریخ")
    session_number = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        verbose_name="شماره زنگ (۰ = روزانه)",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PRESENT,
        verbose_name="وضعیت حضور",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_attendances",
        verbose_name="ثبت‌کننده",
    )
    note = models.CharField(max_length=255, blank=True, default="", verbose_name="توضیحات")

    class Meta:
        verbose_name = "رکورد حضور و غیاب"
        verbose_name_plural = "رکوردهای حضور و غیاب"
        ordering = ["-date", "session_number", "student__last_name", "student__first_name"]
        indexes = [
            models.Index(fields=["school", "date"], name="idx_attendance_school_date"),
            models.Index(
                fields=["school", "classroom", "date"],
                name="idx_attendance_school_cls_date",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "student", "date", "session_number"],
                name="uq_attendance_school_student_date_session",
            )
        ]

    def __str__(self):
        return f"{self.student} - {self.date} (زنگ {self.session_number}): {self.status}"