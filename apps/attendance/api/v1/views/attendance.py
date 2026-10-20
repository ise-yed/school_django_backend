from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.attendance.api.v1.serializers.attendance import (
    AttendanceRecordSerializer,
    AttendanceSheetQuerySerializer,
    BulkAttendanceSubmitSerializer,
)
from apps.attendance.models import AttendanceRecord
from apps.attendance.services import (
    bulk_upsert_classroom_attendance,
    check_teacher_classroom_and_session_access,
    get_classroom_attendance_sheet,
)
from apps.core.fields import JalaliDateField
from apps.core.permissions import IsParentReadOnly, IsTeacherOrSchoolAdmin
from apps.core.viewsets import BaseViewSet


class AttendanceAccessPermission(IsTeacherOrSchoolAdmin):
    """
    - ادمین مدرسه و معلم: دسترسی ثبت، ویرایش و مشاهده (در محدوده کلاس‌های خودشان)
    - ولی: فقط دسترسی مشاهده (Read-only) برای فرزندان تأییدشده خودش
    """
    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True
        return IsParentReadOnly().has_permission(request, view)


class AttendanceRecordViewSet(BaseViewSet):
    queryset = AttendanceRecord.objects.select_related(
        "student", "classroom", "recorded_by"
    )
    serializer_class = AttendanceRecordSerializer
    permission_classes = [AttendanceAccessPermission]
    teacher_classroom_lookup = "classroom__teacher_assignments__teacher"
    parent_student_lookup = "student__parent_links__parent_user"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params

        # ولی فقط رکوردهای فرزندان تأییدشده‌ی خودش را می‌بیند
        if user.role == User.Role.PARENT:
            qs = qs.filter(
                student__parent_links__parent_user=user,
                student__parent_links__is_verified=True,
            )

        classroom_id = params.get("classroom")
        if classroom_id:
            qs = qs.filter(classroom_id=classroom_id)

        student_id = params.get("student")
        if student_id:
            qs = qs.filter(student_id=student_id)

        session_number = params.get("session_number")
        if session_number is not None and session_number != "":
            qs = qs.filter(session_number=session_number)

        status_filter = params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        raw_date = params.get("date")
        if raw_date:
            greg_date = JalaliDateField().to_internal_value(raw_date)
            qs = qs.filter(date=greg_date)

        return qs.distinct()

    def perform_update(self, serializer):
        instance = self.get_object()
        check_teacher_classroom_and_session_access(
            self.request.user, instance.classroom, instance.session_number
        )
        serializer.save(recorded_by=self.request.user)

    @action(
        detail=False,
        methods=["post"],
        url_path="bulk-submit",
        permission_classes=[IsTeacherOrSchoolAdmin],
    )
    def bulk_submit(self, request):
        """
        ثبت یا ویرایش یک‌جای حضور و غیاب کل دانش‌آموزان یک کلاس در یک درخواست واحد.
        """
        serializer = BulkAttendanceSubmitSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = bulk_upsert_classroom_attendance(
            school=self.get_school(),
            user=request.user,
            classroom=data["classroom"],
            date=data["date"],
            session_number=data["session_number"],
            records=data["records"],
            default_present_for_others=data["default_present_for_others"],
        )
        # برگرداندن تاریخ به فرمت شمسی در خروجی
        result["date"] = JalaliDateField().to_representation(data["date"])
        return Response(result, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["get"],
        url_path="sheet",
        permission_classes=[IsTeacherOrSchoolAdmin],
    )
    def sheet(self, request):
        """
        دریافت برگه‌ی حضور و غیاب یک کلاس در یک تاریخ و زنگ مشخص (لیست کل دانش‌آموزان کلاس + وضعیت فعلی).
        """
        serializer = AttendanceSheetQuerySerializer(
            data=request.query_params, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        items = get_classroom_attendance_sheet(
            school=self.get_school(),
            user=request.user,
            classroom=data["classroom_obj"],
            date=data["date"],
            session_number=data["session_number"],
        )
        return Response(
            {
                "classroom_id": data["classroom_obj"].id,
                "classroom_name": data["classroom_obj"].name,
                "date": JalaliDateField().to_representation(data["date"]),
                "session_number": data["session_number"],
                "students": items,
            },
            status=status.HTTP_200_OK,
        )