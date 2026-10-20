from rest_framework import permissions, status, views
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.permissions import IsSchoolAdmin
from apps.core.viewsets import BaseViewSet
from apps.notifications.api.v1.serializers.notifications import (
    AnnouncementSerializer,
    FCMDeviceSerializer,
    NotificationDeliverySerializer,
    NotificationSerializer,
)
from apps.notifications.models import (
    Announcement,
    FCMDevice,
    Notification,
    NotificationDelivery,
)
from apps.notifications.services import (
    create_and_dispatch_announcement,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)


class AnnouncementViewSet(BaseViewSet):
    """مدیریت و ارسال اعلان توسط کادر آموزشی مدرسه (SCHOOL_ADMIN) برای اولیا."""
    queryset = Announcement.objects.select_related(
        "target_grade", "target_classroom", "created_by"
    )
    serializer_class = AnnouncementSerializer
    permission_classes = [IsSchoolAdmin]
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = create_and_dispatch_announcement(
            school=self.get_school(),
            user=request.user,
            validated_data=serializer.validated_data,
        )
        return Response(
            self.get_serializer(announcement).data,
            status=status.HTTP_201_CREATED,
        )


class NotificationInboxViewSet(BaseViewSet):
    """
    صندوق اعلان‌های درون‌برنامه‌ای کاربر لاگین‌شده (ولی یا کادر مدرسه)
    به همراه اکشن‌های mark-read و mark-all-read.
    """
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(user=self.request.user)
        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            if is_read.lower() in ("true", "1"):
                qs = qs.filter(is_read=True)
            elif is_read.lower() in ("false", "0"):
                qs = qs.filter(is_read=False)
        return qs

    def create(self, request, *args, **kwargs):
        raise PermissionDenied("ایجاد مستقیم از این مسیر مجاز نیست.")

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification = mark_notification_as_read(notification=notification)
        return Response(self.get_serializer(notification).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        updated_count = mark_all_notifications_as_read(
            school=self.get_school(), user=request.user
        )
        return Response({"marked_as_read": updated_count}, status=status.HTTP_200_OK)


class FCMDeviceRegisterView(views.APIView):
    """ثبت یا به‌روزرسانی توکن FCM دستگاه موبایل برای دریافت پوش‌نوتیفیکیشن."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.school_id:
            raise PermissionDenied("کاربر باید متعلق به یک مدرسه باشد.")
        serializer = FCMDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        FCMDevice.objects.update_or_create(
            registration_id=serializer.validated_data["registration_id"],
            defaults={
                "school": request.user.school,
                "user": request.user,
                "device_type": serializer.validated_data.get(
                    "device_type", FCMDevice.DeviceType.ANDROID
                ),
                "is_active": True,
            },
        )
        return Response({"status": "Device registered"}, status=status.HTTP_200_OK)


class NotificationDeliveryLogViewSet(BaseViewSet):
    """مشاهده لاگ‌های ارسال پیامک و پوش‌نوتیفیکیشن توسط کادر آموزشی مدرسه (SCHOOL_ADMIN)."""
    queryset = NotificationDelivery.objects.select_related("user", "student", "announcement")
    serializer_class = NotificationDeliverySerializer
    permission_classes = [IsSchoolAdmin]
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        channel = self.request.query_params.get("channel")
        status_filter = self.request.query_params.get("status")
        announcement_id = self.request.query_params.get("announcement")
        if channel:
            qs = qs.filter(channel=channel)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if announcement_id:
            qs = qs.filter(announcement_id=announcement_id)
        return qs