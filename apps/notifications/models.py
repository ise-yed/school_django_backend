from django.conf import settings
from django.db import models

from apps.core.models import SchoolOwnedModel
from apps.notifications.enums import (
    AnnouncementTargetType,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationType,
)


class FCMDevice(SchoolOwnedModel):
    class DeviceType(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fcm_devices",
        verbose_name="کاربر",
    )
    registration_id = models.CharField(max_length=255, unique=True, verbose_name="توکن FCM")
    device_type = models.CharField(
        max_length=20,
        choices=DeviceType.choices,
        default=DeviceType.ANDROID,
        verbose_name="نوع دستگاه",
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "دستگاه FCM"
        verbose_name_plural = "دستگاه‌های FCM"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["school", "user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.device_type} - {self.user}"


class Announcement(SchoolOwnedModel):
    title = models.CharField(max_length=255, verbose_name="عنوان اعلان")
    body = models.TextField(verbose_name="متن اعلان")
    target_type = models.CharField(
        max_length=20,
        choices=AnnouncementTargetType.choices,
        default=AnnouncementTargetType.SCHOOL,
        verbose_name="محدوده مخاطبان",
    )
    target_grade = models.ForeignKey(
        "schools.Grade",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
        verbose_name="پایه هدف",
    )
    target_classroom = models.ForeignKey(
        "schools.Classroom",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
        verbose_name="کلاس هدف",
    )
    channels = models.JSONField(
        default=list,
        verbose_name="کانال‌های ارسال",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_announcements",
        verbose_name="ایجادکننده",
    )

    class Meta:
        verbose_name = "اعلان عمومی مدرسه"
        verbose_name_plural = "اعلان‌های عمومی مدرسه"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["school", "-created_at"]),
            models.Index(fields=["school", "target_type"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_target_type_display()})"


class Notification(SchoolOwnedModel):
    """پیام درون‌برنامه‌ای (In-App Inbox) برای نمایش در اپ موبایل ولی."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="گیرنده",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name="دانش‌آموز مرتبط",
    )
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name="اعلان مرتبط",
    )
    type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        default=NotificationType.ANNOUNCEMENT,
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "اعلان درون‌برنامه‌ای"
        verbose_name_plural = "اعلان‌های درون‌برنامه‌ای"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["school", "user", "-created_at"]),
            models.Index(fields=["school", "user", "is_read", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.title}"


class NotificationDelivery(SchoolOwnedModel):
    """لاگ ارسال نوتیفیکیشن از طریق کانال‌های پیامک (SMS) و پوش (PUSH)."""
    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="deliveries",
    )
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="deliveries",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_deliveries",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_deliveries",
    )
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices)
    type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        default=NotificationType.ANNOUNCEMENT,
    )
    recipient = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=NotificationDeliveryStatus.choices,
        default=NotificationDeliveryStatus.PENDING,
    )
    provider_message_id = models.CharField(max_length=100, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True)
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "لاگ ارسال اعلان"
        verbose_name_plural = "لاگ‌های ارسال اعلان"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["school", "channel", "status", "-created_at"]),
            models.Index(fields=["school", "user", "-created_at"]),
            models.Index(fields=["school", "announcement"]),
        ]

    def __str__(self):
        return f"{self.channel} - {self.recipient} - {self.status}"