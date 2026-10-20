from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.core.fields import JalaliDateField
from apps.core.models import AuditLog
from apps.core.permissions import (
    IsParentReadOnly,
    IsSchoolAdmin,
    IsTeacherOrSchoolAdmin,
)
from apps.core.viewsets import BaseViewSet
from apps.discipline.api.v1.serializers.discipline import (
    AuditLogSerializer,
    DisciplinaryRecordSerializer,
)
from apps.discipline.models import DisciplinaryRecord
from apps.discipline.services import (
    create_disciplinary_record,
    delete_disciplinary_record,
    get_client_ip,
    update_disciplinary_record,
)


class DisciplineAccessPermission(IsTeacherOrSchoolAdmin):
    """
    - ادمین مدرسه و معلم: ثبت، مشاهده و ویرایش (معلم فقط برای کلاس‌های خودش)
    - ولی: فقط مشاهده (Read-only) برای فرزندان تأییدشده خودش
    """
    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True
        return IsParentReadOnly().has_permission(request, view)


class DisciplinaryRecordViewSet(BaseViewSet):
    queryset = DisciplinaryRecord.objects.select_related(
        "student", "classroom", "created_by", "updated_by"
    )
    serializer_class = DisciplinaryRecordSerializer
    permission_classes = [DisciplineAccessPermission]
    teacher_classroom_lookup = "classroom__teacher_assignments__teacher"
    parent_student_lookup = "student__parent_links__parent_user"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params

        if user.role == User.Role.PARENT:
            qs = qs.filter(
                student__parent_links__parent_user=user,
                student__parent_links__is_verified=True,
            )

        student_id = params.get("student")
        if student_id:
            qs = qs.filter(student_id=student_id)

        classroom_id = params.get("classroom")
        if classroom_id:
            qs = qs.filter(classroom_id=classroom_id)

        category = params.get("category")
        if category:
            qs = qs.filter(category=category)

        raw_date = params.get("date")
        if raw_date:
            greg_date = JalaliDateField().to_internal_value(raw_date)
            qs = qs.filter(date=greg_date)

        return qs.distinct()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = create_disciplinary_record(
            school=self.get_school(),
            user=request.user,
            validated_data=serializer.validated_data,
            ip_address=get_client_ip(request),
        )
        output = self.get_serializer(record).data
        return Response(output, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        record = update_disciplinary_record(
            record=instance,
            user=request.user,
            validated_data=serializer.validated_data,
            ip_address=get_client_ip(request),
        )
        return Response(self.get_serializer(record).data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        delete_disciplinary_record(
            record=instance,
            user=request.user,
            ip_address=get_client_ip(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["get"],
        url_path="history",
        permission_classes=[IsTeacherOrSchoolAdmin],
    )
    def history(self, request, pk=None):
        """
        مشاهده‌ی تاریخچه‌ی تغییرات (AuditLog) یک مورد انضباطی خاص توسط معلم همان کلاس یا کادر آموزشی.
        """
        record = self.get_object()
        logs = (
            AuditLog.objects.for_school(self.get_school())
            .filter(target_model="DisciplinaryRecord", target_id=str(record.id))
            .select_related("actor")
            .order_by("-created_at", "-id")
        )
        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DisciplinaryAuditLogViewSet(BaseViewSet):
    """مشاهده‌ی تمام لاگ‌های تغییرات پرونده‌های انضباطی مدرسه (مخصوص کادر آموزشی SCHOOL_ADMIN)."""
    queryset = AuditLog.objects.filter(target_model="DisciplinaryRecord").select_related("actor")
    serializer_class = AuditLogSerializer
    permission_classes = [IsSchoolAdmin]
    http_method_names = ["get", "head", "options"]