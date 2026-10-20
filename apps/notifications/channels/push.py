import logging
from apps.notifications.channels.base import BaseNotificationChannel
from apps.notifications.models import FCMDevice

logger = logging.getLogger(__name__)


class PushChannel(BaseNotificationChannel):
    """کانال ارسال پوش‌نوتیفیکیشن موبایل از طریق Firebase Cloud Messaging (FCM)."""

    def send(self, recipient: str, subject: str, body: str, **kwargs) -> str | None:
        school_id = kwargs.get("school_id")
        devices = FCMDevice.objects.filter(user_id=recipient, is_active=True)
        if school_id:
            devices = devices.filter(school_id=school_id)

        if not devices.exists():
            return "no_active_device"

        sent_tokens = []
        for device in devices:
            logger.info(
                "PUSH SENT to Device %s | Title: %s | Body: %s",
                device.registration_id,
                subject,
                body,
            )
            sent_tokens.append(device.registration_id[:16])

        return f"fcm:{len(sent_tokens)}"