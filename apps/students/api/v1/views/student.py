from django.db.models import Prefetch
from rest_framework.permissions import SAFE_METHODS
from apps.accounts.models import User
from apps.core.permissions import (
    IsParentReadOnly,
    IsSchoolAdminOrTeacherReadOnly,
)
from apps.core.viewsets import BaseViewSet
from apps.students.api.v1.serializers.student import (
    EnrollmentSerializer,
    StudentSerializer,
)
from apps.students.models import Enrollment, Student


class StudentAccessPermission(IsSchoolAdminOrTeacherReadOnly):
    """
    - ادمین مدرسه: دسترسی کامل (CRUD)
    - معلم: دسترسی مشاهده (Read-only) فقط به دانش‌آموزان کلاس‌های خودش
    - ولی: دسترسی مشاهده (Read-only) فقط به فرزندان خودش
    """
    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True
        return IsParentReadOnly().has_permission(request, view)


class StudentViewSet(BaseViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [StudentAccessPermission]
    teacher_classroom_lookup = "enrollments__classroom__teacher_assignments__teacher"
    parent_student_lookup = "parent_links__parent_user"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # اگر ولی است، فقط لینک‌های تاییدشده یا ثبت‌شده برای او در همان مدرسه
        if user.role == User.Role.PARENT:
            qs = qs.filter(parent_links__parent_user=user, parent_links__is_verified=True)

        classroom_id = self.request.query_params.get("classroom")
        if classroom_id:
            qs = qs.filter(enrollments__classroom_id=classroom_id, enrollments__is_active=True)

        active_enrollments = Enrollment.objects.filter(
            is_active=True, academic_year__is_current=True
        ).select_related("classroom")

        return qs.prefetch_related(
            Prefetch("enrollments", queryset=active_enrollments, to_attr="prefetched_enrollments")
        ).distinct()


class EnrollmentViewSet(BaseViewSet):
    queryset = Enrollment.objects.select_related("student", "classroom", "academic_year")
    serializer_class = EnrollmentSerializer
    permission_classes = [IsSchoolAdminOrTeacherReadOnly]
    teacher_classroom_lookup = "classroom__teacher_assignments__teacher"

    def get_queryset(self):
        qs = super().get_queryset()
        classroom_id = self.request.query_params.get("classroom")
        academic_year_id = self.request.query_params.get("academic_year")
        if classroom_id:
            qs = qs.filter(classroom_id=classroom_id)
        if academic_year_id:
            qs = qs.filter(academic_year_id=academic_year_id)
        return qs