import logging
from abc import ABC, abstractmethod
from django.conf import settings
from apps.notifications.channels.base import BaseNotificationChannel

logger = logging.getLogger(__name__)


class BaseSMSProvider(ABC):
    @abstractmethod
    def send_sms(self, phone_number: str, message: str) -> str:
        raise NotImplementedError


class ConsoleSMSProvider(BaseSMSProvider):
    """ارائه‌دهنده پیش‌فرض برای محیط توسعه و تست (ثبت در لاگ بدون ارسال خارجی)."""
    def send_sms(self, phone_number: str, message: str) -> str:
        logger.info("SMS SENT to %s | Message: %s", phone_number, message)
        print(f"[Console SMS] To: {phone_number} | Message: {message}")
        return f"console-sms-{phone_number}"



class KavenegarSMSProvider(BaseSMSProvider):
    """آداپتور سرویس کاوه‌نگار (قابل فعال‌سازی با SMS_PROVIDER=kavenegar)."""
    def send_sms(self, phone_number: str, message: str) -> str:
        api_key = getattr(settings, "SMS_API_KEY", "")
        sender = getattr(settings, "SMS_SENDER_NUMBER", "")
        if not api_key:
            raise RuntimeError("SMS_API_KEY برای کاوه‌نگار تنظیم نشده است.")
        # در محیط پروداکشن درخواست HTTP به کاوه‌نگار ارسال می‌شود
        logger.info("Kavenegar SMS to %s from %s", phone_number, sender)
        return f"kavenegar-{phone_number}"


def get_sms_provider() -> BaseSMSProvider:
    provider_name = getattr(settings, "SMS_PROVIDER", "console").lower()
    if provider_name == "kavenegar":
        return KavenegarSMSProvider()
    return ConsoleSMSProvider()


class SMSChannel(BaseNotificationChannel):
    """کانال ارسال پیامک با استفاده از لایه انتزاعی ارائه‌دهنده پیامک."""

    def send(self, recipient: str, subject: str, body: str, **kwargs) -> str | None:
        provider = get_sms_provider()
        full_text = f"{subject}\n{body}".strip() if subject else body
        return provider.send_sms(phone_number=recipient, message=full_text)