from apps.core.permissions import IsSchoolAdminOrTeacherReadOnly
from apps.core.viewsets import BaseViewSet
from apps.schools.api.v1.filters import TeacherAssignmentFilter
from apps.schools.api.v1.serializers.assignment import TeacherAssignmentSerializer
from apps.schools.models import TeacherAssignment


class TeacherAssignmentViewSet(BaseViewSet):
    """
    تخصیص معلم/درس/زنگ به کلاس‌ها توسط ادمین مدرسه.
    معلم فقط لیست تخصیص‌ها و زنگ‌های خودش را می‌بیند.
    """
    queryset = TeacherAssignment.objects.select_related(
        "teacher", "classroom", "classroom__grade", "classroom__academic_year"
    )
    serializer_class = TeacherAssignmentSerializer
    filterset_class = TeacherAssignmentFilter
    permission_classes = [IsSchoolAdminOrTeacherReadOnly]
    teacher_classroom_lookup = "teacher"