from apps.core.permissions import IsSchoolAdminOrTeacherReadOnly
from apps.core.viewsets import BaseViewSet
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
    permission_classes = [IsSchoolAdminOrTeacherReadOnly]
    teacher_classroom_lookup = "teacher"

    def get_queryset(self):
        qs = super().get_queryset()
        classroom_id = self.request.query_params.get("classroom")
        teacher_id = self.request.query_params.get("teacher")
        day_of_week = self.request.query_params.get("day_of_week")
        if classroom_id:
            qs = qs.filter(classroom_id=classroom_id)
        if teacher_id:
            qs = qs.filter(teacher_id=teacher_id)
        if day_of_week is not None and day_of_week != "":
            qs = qs.filter(day_of_week=day_of_week)
        return qs