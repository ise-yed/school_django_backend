from apps.core.permissions import IsSchoolAdminOrTeacherReadOnly
from apps.core.viewsets import BaseViewSet
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
    """
    queryset = Classroom.objects.select_related("academic_year", "grade")
    serializer_class = ClassroomSerializer
    permission_classes = [IsSchoolAdminOrTeacherReadOnly]
    teacher_classroom_lookup = "teacher_assignments__teacher"

    def get_queryset(self):
        qs = super().get_queryset()
        academic_year_id = self.request.query_params.get("academic_year")
        grade_id = self.request.query_params.get("grade")
        if academic_year_id:
            qs = qs.filter(academic_year_id=academic_year_id)
        if grade_id:
            qs = qs.filter(grade_id=grade_id)
        return qs