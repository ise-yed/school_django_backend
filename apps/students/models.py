from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from apps.core.models import SchoolOwnedModel
from apps.core.normalizers import (
    normalize_and_validate_national_code,
    normalize_persian_text,
)
from apps.students.services import build_normalized_search_name


class Student(SchoolOwnedModel):
    first_name = models.CharField(max_length=100, verbose_name="نام")
    last_name = models.CharField(max_length=100, verbose_name="نام خانوادگی")
    full_name = models.CharField(
        max_length=200, blank=True, default="", verbose_name="نام کامل اصلی"
    )
    father_name = models.CharField(max_length=100, blank=True, default="", verbose_name="نام پدر")
    national_code = models.CharField(max_length=10, verbose_name="کد ملی")
    student_code = models.CharField(
        max_length=30, null=True, blank=True, verbose_name="کد دانش‌آموزی"
    )
    normalized_search_name = models.CharField(
        max_length=320, editable=False, verbose_name="نام نرمال‌شده برای جستجو"
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "دانش‌آموز"
        verbose_name_plural = "دانش‌آموزان"
        ordering = ["last_name", "first_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "national_code"],
                name="uq_student_school_national_code",
            )
        ]
        indexes = [
            models.Index(fields=["school", "is_active"]),
            GinIndex(
                fields=["normalized_search_name"],
                name="idx_student_search_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ]

    def save(self, *args, **kwargs):
        self.first_name = normalize_persian_text(self.first_name)
        self.last_name = normalize_persian_text(self.last_name)
        self.father_name = normalize_persian_text(self.father_name)
        if self.full_name:
            self.full_name = normalize_persian_text(self.full_name)
        else:
            self.full_name = f"{self.first_name} {self.last_name}".strip()
        self.national_code = normalize_and_validate_national_code(self.national_code)
        self.normalized_search_name = build_normalized_search_name(
            self.first_name, self.last_name, self.father_name, self.full_name
        )
        super().save(*args, **kwargs)

    def __str__(self):
        display_name = self.full_name or f"{self.first_name} {self.last_name}".strip()
        return f"{display_name} ({self.national_code})"

    def delete(self, using=None, keep_parents=False):
        self.is_active = False
        self.save(update_fields=["is_active"])
        return 1, {self._meta.label: 1}


class Enrollment(SchoolOwnedModel):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="دانش‌آموز",
    )
    academic_year = models.ForeignKey(
        "schools.AcademicYear",
        on_delete=models.PROTECT,
        related_name="enrollments",
        verbose_name="سال تحصیلی",
    )
    classroom = models.ForeignKey(
        "schools.Classroom",
        on_delete=models.PROTECT,
        related_name="enrollments",
        verbose_name="کلاس",
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "ثبت‌نام کلاس"
        verbose_name_plural = "ثبت‌نام‌های کلاس"
        ordering = ["student__last_name", "student__first_name", "id"]
        indexes = [
            models.Index(fields=["school", "classroom"], name="idx_enrollment_school_class"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "student", "academic_year"],
                name="uq_enrollment_school_student_year",
            )
        ]

    def __str__(self):
        return f"{self.student} -> {self.classroom}"


class ParentStudentLink(SchoolOwnedModel):
    class Relation(models.TextChoices):
        FATHER = "FATHER", "پدر"
        MOTHER = "MOTHER", "مادر"
        GUARDIAN = "GUARDIAN", "سرپرست"

    parent_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="children_links",
        verbose_name="کاربر ولی",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="parent_links",
        verbose_name="دانش‌آموز",
    )
    relation = models.CharField(
        max_length=20,
        choices=Relation.choices,
        default=Relation.GUARDIAN,
        verbose_name="نسبت",
    )
    is_verified = models.BooleanField(default=False, verbose_name="تأیید شده توسط مدرسه")

    class Meta:
        verbose_name = "اتصال ولی به دانش‌آموز"
        verbose_name_plural = "اتصالات اولیا به دانش‌آموزان"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["school", "parent_user", "is_verified"]),
            models.Index(fields=["school", "student"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "parent_user", "student"],
                name="uq_parent_student_school",
            )
        ]

    def __str__(self):
        return f"{self.parent_user} -> {self.student}"