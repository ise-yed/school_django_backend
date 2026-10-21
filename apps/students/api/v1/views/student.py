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
from apps.students.api.v1.filters import EnrollmentFilter, StudentFilter
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
    filterset_class = StudentFilter
    permission_classes = [StudentAccessPermission]
    teacher_classroom_lookup = None
    parent_student_lookup = None
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # دسترسی معلم: فقط دانش‌آموزان فعال با ثبت‌نام فعال در کلاس‌های تخصیص‌یافته به معلم در سال تحصیلی جاری
        if user.role == User.Role.TEACHER:
            qs = qs.filter(
                is_active=True,
                enrollments__classroom__teacher_assignments__teacher=user,
                enrollments__is_active=True,
                enrollments__academic_year__is_current=True,
                enrollments__classroom__is_active=True,
            )

        # دسترسی ولی: فقط فرزندان فعال و تأییدشده‌ی خودش
        elif user.role == User.Role.PARENT:
            qs = qs.filter(
                is_active=True,
                parent_links__parent_user=user,
                parent_links__is_verified=True,
            )

        # فیلتر وضعیت فعال/غیرفعال برای ادمین مدرسه
        is_active_param = self.request.query_params.get("is_active")
        if is_active_param is not None:
            if is_active_param.lower() in ("true", "1"):
                qs = qs.filter(is_active=True)
            elif is_active_param.lower() in ("false", "0"):
                qs = qs.filter(is_active=False)

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
    filterset_class = EnrollmentFilter
    permission_classes = [IsSchoolAdminOrTeacherReadOnly]
    teacher_classroom_lookup = None

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == User.Role.TEACHER:
            qs = qs.filter(
                classroom__teacher_assignments__teacher=user,
                is_active=True,
                academic_year__is_current=True,
                student__is_active=True,
                classroom__is_active=True,
            )
        return qs