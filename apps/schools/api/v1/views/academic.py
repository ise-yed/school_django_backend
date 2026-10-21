from apps.core.permissions import IsSchoolAdminOrTeacherReadOnly
from apps.core.viewsets import BaseViewSet
from apps.schools.api.v1.filters import ClassroomFilter
from apps.schools.api.v1.serializers.academic import (
    AcademicYearSerializer,
    ClassroomSerializer,
    GradeSerializer,
)
from apps.schools.models import AcademicYear, Classroom, Grade


class AcademicYearViewSet(BaseViewSet):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer
    permission_classes = [IsSchoolAdminOrTeacherReadOnly]


class GradeViewSet(BaseViewSet):
    queryset = Grade.objects.all()
    serializer_class = GradeSerializer
    permission_classes = [IsSchoolAdminOrTeacherReadOnly]


class ClassroomViewSet(BaseViewSet):
    """
    ادمین مدرسه همه‌ی کلاس‌های مدرسه را می‌بیند و مدیریت می‌کند.
    معلم فقط کلاس‌هایی را می‌بیند که در TeacherAssignment به او تخصیص داده شده‌اند.
    حذف فیزیکی (DELETE) به دلیل حفظ سوابق مسدود شده و غیرفعال‌سازی با is_active انجام می‌شود.
    """
    queryset = Classroom.objects.select_related("academic_year", "grade")
    serializer_class = ClassroomSerializer
    filterset_class = ClassroomFilter
    permission_classes = [IsSchoolAdminOrTeacherReadOnly]
    teacher_classroom_lookup = "teacher_assignments__teacher"
    http_method_names = ["get", "post", "put", "patch", "head", "options"]