from rest_framework import serializers
from apps.core.normalizers import (
    normalize_and_validate_national_code,
    normalize_persian_text,
)
from apps.students.models import Enrollment, Student


class StudentSerializer(serializers.ModelSerializer):
    current_classroom_id = serializers.SerializerMethodField()
    current_classroom_name = serializers.SerializerMethodField()
    current_grade_title = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id",
            "first_name",
            "last_name",
            "father_name",
            "national_code",
            "student_code",
            "is_active",
            "current_classroom_id",
            "current_classroom_name",
            "current_grade_title",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def _get_active_enrollment(self, obj):
        enrollments = getattr(obj, "prefetched_enrollments", None)
        if enrollments is not None:
            return enrollments[0] if enrollments else None
        return (
            obj.enrollments.filter(is_active=True, academic_year__is_current=True)
            .select_related("classroom", "classroom__grade")
            .first()
        )

    def get_current_classroom_id(self, obj) -> int | None:
        enrollment = self._get_active_enrollment(obj)
        return enrollment.classroom_id if enrollment else None

    def get_current_classroom_name(self, obj) -> str | None:
        enrollment = self._get_active_enrollment(obj)
        return enrollment.classroom.name if enrollment else None

    def get_current_grade_title(self, obj) -> str | None:
        enrollment = self._get_active_enrollment(obj)
        return enrollment.classroom.grade.title if enrollment else None

    def validate_national_code(self, value):
        try:
            code = normalize_and_validate_national_code(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

        request = self.context.get("request")
        school = getattr(request.user, "school", None) if request else None
        if school:
            qs = Student.objects.filter(school=school, national_code=code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "دانش‌آموزی با این کد ملی قبلاً در این مدرسه ثبت شده است."
                )
        return code

    def validate_first_name(self, value):
        cleaned = normalize_persian_text(value)
        if not cleaned:
            raise serializers.ValidationError("نام الزامی است.")
        return cleaned

    def validate_last_name(self, value):
        cleaned = normalize_persian_text(value)
        if not cleaned:
            raise serializers.ValidationError("نام خانوادگی الزامی است.")
        return cleaned


class StudentSearchResultSerializer(StudentSerializer):
    """سریالایزر نتایج جستجوی دانش‌آموز (شامل نام پدر، کلاس و امتیاز شباهت فازی)."""
    full_name = serializers.SerializerMethodField()
    similarity = serializers.FloatField(read_only=True, required=False)

    class Meta(StudentSerializer.Meta):
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "father_name",
            "national_code",
            "student_code",
            "current_classroom_id",
            "current_classroom_name",
            "current_grade_title",
            "similarity",
        ]

    def get_full_name(self, obj) -> str:
        return f"{obj.first_name} {obj.last_name}".strip()


class EnrollmentSerializer(serializers.ModelSerializer):
    student_full_name = serializers.SerializerMethodField()
    student_national_code = serializers.CharField(source="student.national_code", read_only=True)
    father_name = serializers.CharField(source="student.father_name", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    academic_year_title = serializers.CharField(source="academic_year.title", read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "student",
            "student_full_name",
            "student_national_code",
            "father_name",
            "academic_year",
            "academic_year_title",
            "classroom",
            "classroom_name",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "academic_year", "created_at"]

    def get_student_full_name(self, obj) -> str:
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def validate(self, attrs):
        request = self.context.get("request")
        school = getattr(request.user, "school", None) if request else None

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
        if classroom:
            attrs["academic_year"] = classroom.academic_year
        return attrs