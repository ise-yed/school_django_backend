from rest_framework import serializers

from apps.core.fields import SchoolScopedPrimaryKeyRelatedField
from apps.core.normalizers import normalize_persian_text
from apps.notifications.enums import AnnouncementTargetType, NotificationChannel
from apps.schools.models import Classroom, Grade
from apps.notifications.models import (
    Announcement,
    FCMDevice,
    Notification,
    NotificationDelivery,
)


class FCMDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMDevice
        fields = ["id", "registration_id", "device_type", "is_active", "created_at"]
        read_only_fields = ["id", "is_active", "created_at"]
        extra_kwargs = {
            "registration_id": {"validators": []},  # برای پشتیبانی از update_or_create
        }


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "title",
            "message",
            "student",
            "announcement",
            "is_read",
            "read_at",
            "data",
            "created_at",
        ]
        read_only_fields = fields


class NotificationDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDelivery
        fields = [
            "id",
            "announcement",
            "user",
            "student",
            "channel",
            "type",
            "recipient",
            "subject",
            "status",
            "provider_message_id",
            "error_message",
            "sent_at",
            "created_at",
        ]
        read_only_fields = fields


class AnnouncementSerializer(serializers.ModelSerializer):
    target_grade = SchoolScopedPrimaryKeyRelatedField(
        queryset=Grade.objects.all(),
        required=False,
        allow_null=True,
    )
    target_classroom = SchoolScopedPrimaryKeyRelatedField(
        queryset=Classroom.objects.all(),
        required=False,
        allow_null=True,
    )
    target_grade_title = serializers.CharField(source="target_grade.title", read_only=True)
    target_classroom_name = serializers.CharField(
        source="target_classroom.name", read_only=True
    )
    channels = serializers.ListField(
        child=serializers.ChoiceField(choices=NotificationChannel.choices),
        required=False,
        default=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
    )

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "body",
            "target_type",
            "target_grade",
            "target_grade_title",
            "target_classroom",
            "target_classroom_name",
            "channels",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]

    def validate_title(self, value):
        cleaned = normalize_persian_text(value)
        if not cleaned:
            raise serializers.ValidationError("عنوان اعلان الزامی است.")
        return cleaned

    def validate_body(self, value):
        cleaned = normalize_persian_text(value)
        if not cleaned:
            raise serializers.ValidationError("متن اعلان الزامی است.")
        return cleaned

    def validate(self, attrs):
        request = self.context.get("request")
        school = getattr(request.user, "school", None) if request else None

        target_type = attrs.get("target_type", AnnouncementTargetType.SCHOOL)
        target_grade = attrs.get("target_grade")
        target_classroom = attrs.get("target_classroom")

        if target_type == AnnouncementTargetType.GRADE and not target_grade:
            raise serializers.ValidationError(
                {"target_grade": "برای ارسال اعلان به یک پایه، انتخاب پایه الزامی است."}
            )
        if target_type == AnnouncementTargetType.CLASSROOM and not target_classroom:
            raise serializers.ValidationError(
                {"target_classroom": "برای ارسال اعلان به یک کلاس، انتخاب کلاس الزامی است."}
            )

        if school:
            if target_grade and target_grade.school_id != school.id:
                raise serializers.ValidationError(
                    {"target_grade": "پایه انتخاب‌شده متعلق به مدرسه‌ی شما نیست."}
                )
            if target_classroom and target_classroom.school_id != school.id:
                raise serializers.ValidationError(
                    {"target_classroom": "کلاس انتخاب‌شده متعلق به مدرسه‌ی شما نیست."}
                )

        return attrs