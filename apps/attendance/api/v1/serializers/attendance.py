from rest_framework import serializers
from apps.attendance.models import AttendanceRecord
from apps.core.fields import JalaliDateField, SchoolScopedPrimaryKeyRelatedField
from apps.schools.models import Classroom
from apps.students.models import Enrollment, Student


class AttendanceRecordSerializer(serializers.ModelSerializer):
    date = JalaliDateField()
    student = SchoolScopedPrimaryKeyRelatedField(
        queryset=Student.objects.all(),
    )
    classroom = SchoolScopedPrimaryKeyRelatedField(
        queryset=Classroom.objects.all(),
    )
    student_full_name = serializers.SerializerMethodField()
    father_name = serializers.CharField(source="student.father_name", read_only=True)
    national_code = serializers.CharField(source="student.national_code", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "student",
            "student_full_name",
            "father_name",
            "national_code",
            "classroom",
            "classroom_name",
            "date",
            "session_number",
            "status",
            "note",
            "recorded_by",
            "recorded_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "recorded_by", "created_at", "updated_at"]

    def get_student_full_name(self, obj) -> str:
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def get_recorded_by_name(self, obj) -> str | None:
        if not obj.recorded_by:
            return None
        full = f"{obj.recorded_by.first_name} {obj.recorded_by.last_name}".strip()
        return full or obj.recorded_by.username

    def validate(self, attrs):
        request = self.context.get("request")
        school = getattr(request.user, "school", None) if (request and hasattr(request, "user")) else None

        student = attrs.get("student", getattr(self.instance, "student", None))
        classroom = attrs.get("classroom", getattr(self.instance, "classroom", None))

        if school:
            if student and student.school_id != school.id:
                raise serializers.ValidationError(
                    {"student": "دانش‌آموز انتخاب‌شده متعلق به مدرسه‌ی شما نیست."}
                )
            if classroom and classroom.school_id != school.id:
                raise serializers.ValidationError(
                    {"classroom": "کلاس انتخاب‌شده متعلق به مدرسه‌ی شما نیست."}
                )

        if student and classroom:
            is_enrolled = Enrollment.objects.filter(
                student=student,
                classroom=classroom,
                is_active=True,
            ).exists()
            if not is_enrolled:
                raise serializers.ValidationError(
                    {"student": "دانش‌آموز انتخاب‌شده در این کلاس ثبت‌نام نشده است."}
                )

        date = attrs.get("date", getattr(self.instance, "date", None))
        session_number = attrs.get(
            "session_number", getattr(self.instance, "session_number", 0)
        )
        if school and student and date is not None:
            existing_qs = AttendanceRecord.objects.filter(
                school=school,
                student=student,
                date=date,
                session_number=session_number,
            )
            if self.instance:
                existing_qs = existing_qs.exclude(pk=self.instance.pk)
            if existing_qs.exists():
                raise serializers.ValidationError(
                    "رکورد حضور و غیاب برای این دانش‌آموز در این تاریخ و شماره زنگ قبلاً ثبت شده است."
                )

        return attrs


class BulkAttendanceItemSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=AttendanceRecord.Status.choices)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class BulkAttendanceSubmitSerializer(serializers.Serializer):
    classroom_id = serializers.IntegerField()
    date = JalaliDateField()
    session_number = serializers.IntegerField(min_value=0, max_value=6, default=0)
    default_present_for_others = serializers.BooleanField(default=False)
    records = BulkAttendanceItemSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        request = self.context["request"]
        school = request.user.school

        try:
            attrs["classroom"] = Classroom.objects.for_school(school).get(
                pk=attrs["classroom_id"]
            )
        except Classroom.DoesNotExist:
            raise serializers.ValidationError(
                {"classroom_id": "کلاس موردنظر در مدرسه‌ی شما یافت نشد."}
            )
        return attrs


class AttendanceSheetQuerySerializer(serializers.Serializer):
    classroom = serializers.IntegerField()
    date = JalaliDateField()
    session_number = serializers.IntegerField(min_value=0, max_value=6, default=0)

    def validate(self, attrs):
        request = self.context["request"]
        school = request.user.school
        try:
            attrs["classroom_obj"] = Classroom.objects.for_school(school).get(
                pk=attrs["classroom"]
            )
        except Classroom.DoesNotExist:
            raise serializers.ValidationError(
                {"classroom": "کلاس موردنظر در مدرسه‌ی شما یافت نشد."}
            )
        return attrs