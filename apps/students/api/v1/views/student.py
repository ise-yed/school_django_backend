from django.db.models import Prefetch
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.accounts.models import User
from apps.core.permissions import (
    IsParentReadOnly,
    IsSchoolAdminOrTeacherReadOnly,
    IsTeacherOrSchoolAdmin,
)
from apps.core.viewsets import BaseViewSet
from apps.students.api.v1.serializers.student import (
    EnrollmentSerializer,
    StudentSearchResultSerializer,
    StudentSerializer,
)
from apps.students.models import Enrollment, Student
from apps.students.services import apply_student_search_and_filters


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

        # اگر ولی است، فقط فرزندان تأییدشده‌ی خودش را ببیند
        if user.role == User.Role.PARENT:
            qs = qs.filter(parent_links__parent_user=user, parent_links__is_verified=True)

        # اعمال فیلترهای جستجو و pg_trgm
        qs = apply_student_search_and_filters(qs, self.request.query_params)

        active_enrollments = Enrollment.objects.filter(
            is_active=True, academic_year__is_current=True
        ).select_related("classroom", "classroom__grade")

        # اگر کوئری با similarity مرتب نشده باشد، distinct عادی اعمال شود
        if "q" not in self.request.query_params:
            qs = qs.distinct()
        else:
            # در صورت وجود JOIN از سمت معلم یا فیلتر کلاس، جلوگیری از تکرار رکوردها با حفظ ترتیب امتیاز شباهت
            qs = qs.filter(pk__in=qs.values("pk"))
            qs = apply_student_search_and_filters(
                Student.objects.filter(pk__in=qs.values("pk")),
                self.request.query_params,
            )

        return qs.prefetch_related(
            Prefetch("enrollments", queryset=active_enrollments, to_attr="prefetched_enrollments")
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="search",
        permission_classes=[IsTeacherOrSchoolAdmin],
        serializer_class=StudentSearchResultSerializer,
    )
    def search(self, request):
        """
        جستجوی فازی دانش‌آموزان (مخصوص معلم و کادر آموزشی) با پشتیبانی از:
        ?q=...&first_name=...&last_name=...&father_name=...&national_code=...&classroom=...
        """
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


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