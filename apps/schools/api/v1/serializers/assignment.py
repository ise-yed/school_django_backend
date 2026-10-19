from rest_framework import serializers
from apps.accounts.models import User
from apps.schools.models import TeacherAssignment


class TeacherAssignmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    grade_title = serializers.CharField(source="classroom.grade.title", read_only=True)

    class Meta:
        model = TeacherAssignment
        fields = [
            "id",
            "teacher",
            "teacher_name",
            "classroom",
            "classroom_name",
            "grade_title",
            "subject_name",
            "session_number",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_teacher_name(self, obj) -> str:
        full = f"{obj.teacher.first_name} {obj.teacher.last_name}".strip()
        return full or obj.teacher.username or str(obj.teacher.id)

    def validate(self, attrs):
        request = self.context.get("request")
        school = getattr(request.user, "school", None) if request else None

        teacher = attrs.get("teacher", getattr(self.instance, "teacher", None))
        classroom = attrs.get("classroom", getattr(self.instance, "classroom", None))

        if school:
            if teacher:
                if teacher.school_id != school.id:
                    raise serializers.ValidationError(
                        {"teacher": "معلم انتخاب‌شده متعلق به مدرسه‌ی شما نیست."}
                    )
                if teacher.role != User.Role.TEACHER:
                    raise serializers.ValidationError(
                        {"teacher": "کاربر انتخاب‌شده باید دارای نقش معلم (TEACHER) باشد."}
                    )
            if classroom and classroom.school_id != school.id:
                raise serializers.ValidationError(
                    {"classroom": "کلاس انتخاب‌شده متعلق به مدرسه‌ی شما نیست."}
                )
        return attrs