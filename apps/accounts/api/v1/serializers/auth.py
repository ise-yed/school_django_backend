from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken
from apps.accounts.models import User
from apps.core.normalizers import (
    normalize_and_validate_national_code,
    normalize_digits,
    normalize_phone,
)


def get_tokens_for_user(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["school_id"] = user.school_id
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user": {
            "id": user.id,
            "username": user.username,
            "phone_number": user.phone_number,
            "full_name": f"{user.first_name} {user.last_name}".strip(),
            "role": user.role,
            "school_id": user.school_id,
        },
    }


class StaffLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if not user or not user.is_active:
            raise AuthenticationFailed("نام کاربری یا رمز عبور اشتباه است.")
        if user.role == User.Role.PARENT:
            raise AuthenticationFailed("اولیا باید از طریق شماره موبایل و کد یک‌بارمصرف وارد شوند.")
        if user.school and not user.school.is_active:
            raise AuthenticationFailed("مدرسه‌ی شما غیرفعال است.")
        return get_tokens_for_user(user)


class OTPRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    student_national_code = serializers.CharField(required=False, allow_blank=True)

    def validate_phone_number(self, value):
        try:
            return normalize_phone(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_student_national_code(self, value):
        if not value:
            return ""
        try:
            return normalize_and_validate_national_code(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))


class OTPVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField(max_length=6)
    student_national_code = serializers.CharField(required=False, allow_blank=True)
    school_id = serializers.IntegerField(required=False)

    def validate_phone_number(self, value):
        try:
            return normalize_phone(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_code(self, value):
        return normalize_digits(value)

    def validate_student_national_code(self, value):
        if not value:
            return ""
        try:
            return normalize_and_validate_national_code(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))