from django.db import models


class NotificationType(models.TextChoices):
    ANNOUNCEMENT = "announcement", "اعلان مدرسه"
    ATTENDANCE_ALERT = "attendance_alert", "هشدار غیبت / تأخیر"
    DISCIPLINE_NOTICE = "discipline_notice", "اطلاعیه انضباطی / تشویقی"


class AnnouncementTargetType(models.TextChoices):
    SCHOOL = "SCHOOL", "کل مدرسه"
    GRADE = "GRADE", "یک پایه تحصیلی"
    CLASSROOM = "CLASSROOM", "یک کلاس مشخص"


class NotificationChannel(models.TextChoices):
    IN_APP = "in_app", "درون‌برنامه‌ای"
    PUSH = "push", "پوش‌نوتیفیکیشن (FCM)"
    SMS = "sms", "پیامک"


class NotificationDeliveryStatus(models.TextChoices):
    PENDING = "pending", "در صف انتظار"
    SENT = "sent", "ارسال‌شده"
    FAILED = "failed", "ناموفق"
    SKIPPED = "skipped", "ردشده"