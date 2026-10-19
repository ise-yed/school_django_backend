from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from apps.core.models import SchoolOwnedModel, TimeStampedModel


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


class AcademicYear(SchoolOwnedModel):
    title = models.CharField(max_length=50, verbose_name="عنوان سال تحصیلی")
    start_date = models.DateField(verbose_name="تاریخ شروع")
    end_date = models.DateField(verbose_name="تاریخ پایان")
    is_current = models.BooleanField(default=False, verbose_name="سال تحصیلی جاری")

    class Meta:
        verbose_name = "سال تحصیلی"
        verbose_name_plural = "سال‌های تحصیلی"
        ordering = ["-start_date", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "title"],
                name="uq_academicyear_school_title",
            ),
            models.UniqueConstraint(
                fields=["school"],
                condition=models.Q(is_current=True),
                name="uq_academicyear_single_current_per_school",
            ),
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_current and self.school_id:
                AcademicYear.objects.filter(
                    school_id=self.school_id, is_current=True
                ).exclude(pk=self.pk).update(is_current=False)
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.school.name})"


class Grade(SchoolOwnedModel):
    title = models.CharField(max_length=50, verbose_name="عنوان پایه")
    level_order = models.PositiveSmallIntegerField(default=1, verbose_name="ترتیب پایه")

    class Meta:
        verbose_name = "پایه تحصیلی"
        verbose_name_plural = "پایه‌های تحصیلی"
        ordering = ["level_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "title"],
                name="uq_grade_school_title",
            )
        ]

    def __str__(self):
        return f"{self.title} ({self.school.name})"


class Classroom(SchoolOwnedModel):
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="classrooms",
        verbose_name="سال تحصیلی",
    )
    grade = models.ForeignKey(
        Grade,
        on_delete=models.PROTECT,
        related_name="classrooms",
        verbose_name="پایه تحصیلی",
    )
    name = models.CharField(max_length=100, verbose_name="نام کلاس")

    class Meta:
        verbose_name = "کلاس"
        verbose_name_plural = "کلاس‌ها"
        ordering = ["grade__level_order", "name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year", "grade", "name"],
                name="uq_classroom_school_year_grade_name",
            )
        ]

    def __str__(self):
        return f"{self.grade.title} - {self.name}"


class TeacherAssignment(SchoolOwnedModel):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_assignments",
        verbose_name="معلم",
    )
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name="teacher_assignments",
        verbose_name="کلاس",
    )
    subject_name = models.CharField(max_length=100, verbose_name="نام درس")
    session_number = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(6)],
        verbose_name="شماره زنگ",
    )

    class Meta:
        verbose_name = "تخصیص معلم به کلاس"
        verbose_name_plural = "تخصیص‌های معلم به کلاس"
        ordering = ["classroom_id", "session_number", "id"]
        indexes = [
            models.Index(fields=["school", "teacher"]),
            models.Index(fields=["school", "classroom"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "classroom", "teacher", "subject_name", "session_number"],
                name="uq_teacher_assignment_full",
            )
        ]

    def __str__(self):
        return f"{self.teacher} - {self.classroom} ({self.subject_name} - زنگ {self.session_number})"