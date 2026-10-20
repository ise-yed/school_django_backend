from abc import ABC, abstractmethod
from typing import Any


class BaseNotificationChannel(ABC):
    """کلاس پایه برای تمام کانال‌های ارسال اعلان (Push, SMS و غیره)."""

    @abstractmethod
    def send(self, recipient: str, subject: str, body: str, **kwargs) -> str | None:
        """
        ارسال اعلان به گیرنده و برگرداندن شناسه پیگیری ارائه‌دهنده (provider_message_id) در صورت وجود.
        """
        raise NotImplementedError

    def validate_recipient(self, recipient: str) -> bool:
        return bool(recipient)

    def get_backend_config(self) -> dict[str, Any]:
        return {}