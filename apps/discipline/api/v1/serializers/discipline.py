from rest_framework import serializers
from apps.core.fields import JalaliDateField
from apps.core.models import AuditLog
from apps.core.normalizers import normalize_persian_text
from apps.discipline.models import DisciplinaryRecord


class DisciplinaryRecordSerializer(serializers.ModelSerializer):
    date = JalaliDateField()
    classroom = serializers.PrimaryKeyRelatedField(
        queryset=DisciplinaryRecord._meta.get_field("classroom").related_model.objects.all(),
        required=False,
        allow_null=True,
    )
    student_full_name = serializers.SerializerMethodField()
    father_name = serializers.CharField(source="student.father_name", read_only=True)
    national_code = serializers.CharField(source="student.national_code", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DisciplinaryRecord
        fields = [
            "id",
            "student",
            "student_full_name",
            "father_name",
            "national_code",
            "classroom",
            "classroom_name",
            "date",
            "category",
            "category_display",
            "description",
            "score_impact",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def get_student_full_name(self, obj) -> str:
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def _user_display(self, user) -> str | None:
        if not user:
            return None
        full = f"{user.first_name} {user.last_name}".strip()
        return full or user.username or str(user.id)

    def get_created_by_name(self, obj) -> str | None:
        return self._user_display(obj.created_by)

    def get_updated_by_name(self, obj) -> str | None:
        return self._user_display(obj.updated_by)

    def validate_description(self, value):
        cleaned = normalize_persian_text(value)
        if not cleaned:
            raise serializers.ValidationError("شرح مورد انضباطی الزامی است.")
        return cleaned

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
        return attrs


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    actor_role = serializers.CharField(source="actor.role", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_name",
            "actor_role",
            "action",
            "target_model",
            "target_id",
            "changes",
            "ip_address",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj) -> str | None:
        if not obj.actor:
            return None
        full = f"{obj.actor.first_name} {obj.actor.last_name}".strip()
        return full or obj.actor.username or str(obj.actor.id)