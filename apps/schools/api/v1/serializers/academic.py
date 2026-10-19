from rest_framework import serializers
from apps.core.fields import JalaliDateField
from apps.schools.models import AcademicYear, Classroom, Grade


class AcademicYearSerializer(serializers.ModelSerializer):
    start_date = JalaliDateField()
    end_date = JalaliDateField()

    class Meta:
        model = AcademicYear
        fields = ["id", "title", "start_date", "end_date", "is_current", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError("تاریخ پایان باید بعد از تاریخ شروع باشد.")
        return attrs


class GradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ["id", "title", "level_order", "created_at"]
        read_only_fields = ["id", "created_at"]


class ClassroomSerializer(serializers.ModelSerializer):
    grade_title = serializers.CharField(source="grade.title", read_only=True)
    academic_year_title = serializers.CharField(source="academic_year.title", read_only=True)

    class Meta:
        model = Classroom
        fields = [
            "id",
            "academic_year",
            "academic_year_title",
            "grade",
            "grade_title",
            "name",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        request = self.context.get("request")
        school = getattr(request.user, "school", None) if request else None

        academic_year = attrs.get("academic_year", getattr(self.instance, "academic_year", None))
        grade = attrs.get("grade", getattr(self.instance, "grade", None))

        if school:
            if academic_year and academic_year.school_id != school.id:
                raise serializers.ValidationError(
                    {"academic_year": "سال تحصیلی انتخاب‌شده متعلق به مدرسه‌ی شما نیست."}
                )
            if grade and grade.school_id != school.id:
                raise serializers.ValidationError(
                    {"grade": "پایه‌ی تحصیلی انتخاب‌شده متعلق به مدرسه‌ی شما نیست."}
                )
        return attrs