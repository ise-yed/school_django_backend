from rest_framework import serializers
from apps.attendance.models import AttendanceRecord
from apps.core.fields import JalaliDateField
from apps.schools.models import Classroom


class AttendanceRecordSerializer(serializers.ModelSerializer):
    date = JalaliDateField()
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