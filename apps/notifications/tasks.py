from celery import shared_task
from django.core.exceptions import ValidationError

from apps.notifications.channels import PushChannel, SMSChannel
from apps.notifications.enums import (
    NotificationChannel,
    NotificationDeliveryStatus,
)
from apps.notifications.models import NotificationDelivery
from apps.notifications.services import (
    mark_delivery_as_failed,
    mark_delivery_as_sent,
)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_delivery_task(self, delivery_id: int) -> None:
    """
    ارسال آسنکرون نوتیفیکیشن از طریق کانال تنظیم‌شده (PUSH یا SMS) با تلاش مجدد تا ۳ بار.
    """
    try:
        delivery = NotificationDelivery.objects.get(id=delivery_id)
    except (NotificationDelivery.DoesNotExist, ValidationError, ValueError):
        return

    if delivery.status != NotificationDeliveryStatus.PENDING:
        return

    try:
        if delivery.channel == NotificationChannel.PUSH:
            provider_msg_id = PushChannel().send(
                recipient=delivery.recipient,
                subject=delivery.subject,
                body=delivery.body,
                data=delivery.data,
                school_id=delivery.school_id,
            )
        elif delivery.channel == NotificationChannel.SMS:
            provider_msg_id = SMSChannel().send(
                recipient=delivery.recipient,
                subject=delivery.subject,
                body=delivery.body,
                data=delivery.data,
                school_id=delivery.school_id,
            )
        else:
            mark_delivery_as_failed(
                delivery=delivery,
                error_message=f"Unsupported notification channel: {delivery.channel}",
            )
            return

    except Exception as exc:
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            mark_delivery_as_failed(delivery=delivery, error_message=str(exc))
            return

    mark_delivery_as_sent(
        delivery=delivery, provider_message_id=provider_msg_id or ""
    )