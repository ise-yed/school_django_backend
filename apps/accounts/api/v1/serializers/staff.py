from rest_framework import serializers
from apps.accounts.models import User
from apps.core.normalizers import normalize_phone


class SchoolStaffSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=6)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "phone_number",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "password",
        ]
        read_only_fields = ["id"]

    def validate_phone_number(self, value):
        if not value:
            return None
        try:
            return normalize_phone(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_role(self, value):
        if value not in (User.Role.SCHOOL_ADMIN, User.Role.TEACHER):
            raise serializers.ValidationError("از این بخش فقط می‌توانید کادر آموزشی یا معلم تعریف کنید.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if password:
            instance.set_password(password)
        instance.save()
        return instance