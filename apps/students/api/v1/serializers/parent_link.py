from django.db import transaction
from rest_framework import serializers
from apps.accounts.models import User
from apps.core.fields import SchoolScopedPrimaryKeyRelatedField
from apps.core.normalizers import (
    normalize_and_validate_national_code,
    normalize_persian_text,
    normalize_phone,
)
from apps.students.models import ParentStudentLink, Student


class ParentStudentLinkSerializer(serializers.ModelSerializer):
    student = SchoolScopedPrimaryKeyRelatedField(
        queryset=Student.objects.all(),
    )
    parent_phone = serializers.CharField(source="parent_user.phone_number", read_only=True)
    parent_first_name = serializers.CharField(source="parent_user.first_name", read_only=True)
    parent_last_name = serializers.CharField(source="parent_user.last_name", read_only=True)
    student_full_name = serializers.SerializerMethodField()
    student_national_code = serializers.CharField(source="student.national_code", read_only=True)
    father_name = serializers.CharField(source="student.father_name", read_only=True)

    class Meta:
        model = ParentStudentLink
        fields = [
            "id",
            "parent_user",
            "parent_phone",
            "parent_first_name",
            "parent_last_name",
            "student",
            "student_full_name",
            "student_national_code",
            "father_name",
            "relation",
            "is_verified",
            "created_at",
        ]
        read_only_fields = ["id", "parent_user", "created_at"]

    def get_student_full_name(self, obj) -> str:
        return f"{obj.student.first_name} {obj.student.last_name}".strip()


class AssignParentByAdminSerializer(serializers.Serializer):
    """
    ثبت یا اتصال ولی به دانش‌آموز توسط کادر آموزشی (با شناسه دانش‌آموز یا کد ملی دانش‌آموز + موبایل ولی).
    """
    student_id = serializers.IntegerField(required=False)
    student_national_code = serializers.CharField(required=False)
    phone_number = serializers.CharField()
    relation = serializers.ChoiceField(
        choices=ParentStudentLink.Relation.choices,
        default=ParentStudentLink.Relation.GUARDIAN,
    )
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    is_verified = serializers.BooleanField(default=True)

    def validate_phone_number(self, value):
        try:
            return normalize_phone(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate(self, attrs):
        request = self.context["request"]
        school = request.user.school

        student_id = attrs.get("student_id")
        raw_nc = attrs.get("student_national_code")

        if not student_id and not raw_nc:
            raise serializers.ValidationError(
                "ارسال شناسه دانش‌آموز (student_id) یا کد ملی دانش‌آموز (student_national_code) الزامی است."
            )

        student = None
        if student_id:
            student = Student.objects.for_school(school).filter(pk=student_id).first()
        elif raw_nc:
            try:
                nc = normalize_and_validate_national_code(raw_nc)
            except ValueError as e:
                raise serializers.ValidationError({"student_national_code": str(e)})
            student = Student.objects.for_school(school).filter(national_code=nc).first()

        if not student:
            raise serializers.ValidationError("دانش‌آموز موردنظر در مدرسه‌ی شما یافت نشد.")

        attrs["student_obj"] = student
        return attrs

    def save(self):
        school = self.context["request"].user.school
        student = self.validated_data["student_obj"]
        phone = self.validated_data["phone_number"]
        relation = self.validated_data["relation"]
        first_name = normalize_persian_text(self.validated_data.get("first_name", ""))
        last_name = normalize_persian_text(self.validated_data.get("last_name", ""))
        is_verified = self.validated_data.get("is_verified", True)

        with transaction.atomic():
            parent_user, _ = User.objects.get_or_create(
                school=school,
                phone_number=phone,
                defaults={
                    "role": User.Role.PARENT,
                    "first_name": first_name or student.father_name,
                    "last_name": last_name or student.last_name,
                    "is_active": True,
                },
            )
            if first_name or last_name:
                if first_name:
                    parent_user.first_name = first_name
                if last_name:
                    parent_user.last_name = last_name
                parent_user.save(update_fields=["first_name", "last_name"])

            link, _ = ParentStudentLink.objects.update_or_create(
                school=school,
                parent_user=parent_user,
                student=student,
                defaults={
                    "relation": relation,
                    "is_verified": is_verified,
                },
            )
        return link


class ChangeParentPhoneSerializer(serializers.Serializer):
    """تغییر شماره موبایل ولی برای یک رکورد اتصال توسط کادر آموزشی."""
    phone_number = serializers.CharField()
    relation = serializers.ChoiceField(
        choices=ParentStudentLink.Relation.choices,
        required=False,
    )

    def validate_phone_number(self, value):
        try:
            return normalize_phone(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))


class BulkParentItemSerializer(serializers.Serializer):
    student_national_code = serializers.CharField()
    phone_number = serializers.CharField()
    relation = serializers.ChoiceField(
        choices=ParentStudentLink.Relation.choices,
        default=ParentStudentLink.Relation.GUARDIAN,
    )


class BulkAssignParentsSerializer(serializers.Serializer):
    """ثبت گروهی شماره موبایل اولیا در لیست کلاس توسط کادر آموزشی."""
    items = BulkParentItemSerializer(many=True, allow_empty=False)