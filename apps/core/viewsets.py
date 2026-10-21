from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from apps.accounts.models import User


def get_client_ip(request) -> str | None:
    if not request:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class BaseViewSet(viewsets.ModelViewSet):
    """
    پایه‌ی تمام ViewSetهای وابسته به مدرسه:
    ۱. فیلتر اجباری بر اساس request.user.school
    ۲. محدودسازی خودکار معلم فقط به کلاس‌های خودش
    ۳. محدودسازی خودکار ولی فقط به فرزندان خودش (Read-only)
    ۴. تزریق خودکار school هنگام ایجاد رکورد
    """
    teacher_classroom_lookup: str | None = None
    parent_student_lookup: str | None = None

    def get_client_ip(self) -> str | None:
        return get_client_ip(getattr(self, "request", None))

    def get_school(self):
        user = self.request.user
        if not user or not user.is_authenticated or not user.school_id:
            raise PermissionDenied("مدرسه‌ی کاربر مشخص نیست.")
        if not user.school.is_active:
            raise PermissionDenied("این مدرسه غیرفعال است.")
        return user.school

    def get_queryset(self):
        assert self.queryset is not None, "queryset باید در ViewSet تعریف شود."
        school = self.get_school()
        user = self.request.user

        # ۱. ایزولاسیون سطح مدرسه
        qs = self.queryset.filter(school=school)

        # ۲. محدودیت معلم فقط به کلاس‌های خودش
        if user.role == User.Role.TEACHER and self.teacher_classroom_lookup:
            qs = qs.filter(**{self.teacher_classroom_lookup: user}).distinct()

        # ۳. محدودیت ولی فقط به فرزندان خودش
        if user.role == User.Role.PARENT and self.parent_student_lookup:
            qs = qs.filter(**{self.parent_student_lookup: user}).distinct()

        return qs

    def perform_create(self, serializer):
        serializer.save(school=self.get_school())