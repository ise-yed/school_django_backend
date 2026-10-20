from django.conf import settings
from django.db import models
from apps.core.models import SchoolOwnedModel


class DisciplinaryRecord(SchoolOwnedModel):
    class Category(models.TextChoices):
        BEHAVIORAL = "BEHAVIORAL", "تذکر انضباطی / رفتاری"
        TARDINESS = "TARDINESS", "تأخیر یا غیبت مکرر"
        ACADEMIC = "ACADEMIC", "عدم انجام تکالیف / آموزشی"
        DRESS_CODE = "DRESS_CODE", "پوشش و شئونات مدرسه"
        MERIT = "MERIT", "تشویقی / اخلاقی و علمی"
        OTHER = "OTHER", "سایر موارد"

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="disciplinary_records",
        verbose_name="دانش‌آموز",
    )
    classroom = models.ForeignKey(
        "schools.Classroom",
        on_delete=models.CASCADE,
        related_name="disciplinary_records",
        verbose_name="کلاس",
    )
    date = models.DateField(verbose_name="تاریخ ثبت")
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.BEHAVIORAL,
        verbose_name="دسته‌بندی",
    )
    description = models.TextField(verbose_name="شرح مورد انضباطی / تشویقی")
    score_impact = models.SmallIntegerField(
        default=0,
        verbose_name="تأثیر نمره (مثبت یا منفی)",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_disciplinary_records",
        verbose_name="ایجادکننده",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_disciplinary_records",
        verbose_name="آخرین ویرایش‌کننده",
    )

    class Meta:
        verbose_name = "مورد انضباطی"
        verbose_name_plural = "پرونده‌های انضباطی"
        ordering = ["-date", "-id"]
        indexes = [
            models.Index(
                fields=["school", "student", "date"],
                name="idx_discipline_school_stu_date",
            ),
            models.Index(
                fields=["school", "classroom", "date"],
                name="idx_discipline_school_cls_date",
            ),
        ]

    def __str__(self):
        return f"{self.student} - {self.get_category_display()} ({self.date})"