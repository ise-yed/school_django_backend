from django.db import transaction
from django.utils import timezone

from apps.notifications.enums import (
    AnnouncementTargetType,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationType,
)
from apps.notifications.models import (
    Announcement,
    Notification,
    NotificationDelivery,
)
from apps.students.models import ParentStudentLink


@transaction.atomic
def mark_notification_as_read(*, notification: Notification) -> Notification:
    if notification.is_read:
        return notification
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=["is_read", "read_at", "updated_at"])
    return notification


@transaction.atomic
def mark_all_notifications_as_read(*, school, user) -> int:
    return (
        Notification.objects.for_school(school)
        .filter(user=user, is_read=False)
        .update(is_read=True, read_at=timezone.now())
    )


@transaction.atomic
def mark_delivery_as_sent(
    *, delivery: NotificationDelivery, provider_message_id: str = ""
) -> NotificationDelivery:
    delivery.status = NotificationDeliveryStatus.SENT
    delivery.sent_at = timezone.now()
    delivery.provider_message_id = provider_message_id or ""
    delivery.error_message = ""
    delivery.save(
        update_fields=[
            "status",
            "sent_at",
            "provider_message_id",
            "error_message",
            "updated_at",
        ]
    )
    return delivery


@transaction.atomic
def mark_delivery_as_failed(
    *, delivery: NotificationDelivery, error_message: str
) -> NotificationDelivery:
    delivery.status = NotificationDeliveryStatus.FAILED
    delivery.error_message = error_message
    delivery.save(update_fields=["status", "error_message", "updated_at"])
    return delivery


def enqueue_notification_delivery(*, delivery_id: int) -> None:
    from apps.notifications.tasks import send_notification_delivery_task

    transaction.on_commit(lambda: send_notification_delivery_task.delay(delivery_id))


def resolve_target_parent_links(school, announcement: Announcement):
    """
    پیدا کردن اولیای تأییدشده (ParentStudentLink با is_verified=True) بر اساس محدوده اعلان:
    - SCHOOL: کل دانش‌آموزان فعال مدرسه
    - GRADE: دانش‌آموزان فعال آن پایه در سال تحصیلی جاری
    - CLASSROOM: دانش‌آموزان فعال آن کلاس
    """
    qs = (
        ParentStudentLink.objects.for_school(school)
        .filter(
            is_verified=True,
            parent_user__is_active=True,
            student__is_active=True,
        )
        .select_related("parent_user", "student")
    )

    if announcement.target_type == AnnouncementTargetType.CLASSROOM:
        qs = qs.filter(
            student__enrollments__classroom_id=announcement.target_classroom_id,
            student__enrollments__is_active=True,
            student__enrollments__classroom__is_active=True,
        )
    elif announcement.target_type == AnnouncementTargetType.GRADE:
        qs = qs.filter(
            student__enrollments__classroom__grade_id=announcement.target_grade_id,
            student__enrollments__academic_year__is_current=True,
            student__enrollments__is_active=True,
            student__enrollments__classroom__is_active=True,
        )

    return qs.distinct()


@transaction.atomic
def create_and_dispatch_announcement(*, school, user, validated_data: dict) -> Announcement:
    """
    ساخت اعلان عمومی مدرسه و ایجاد دسته‌جمعی (Bulk) اعلان‌های درون‌برنامه‌ای و لاگ‌های ارسال
    برای تمام اولیای هدف، همراه با صف کردن تسک‌های Celery پس از Commit تراکنش.
    """
    channels = validated_data.get("channels") or [
        NotificationChannel.IN_APP,
        NotificationChannel.PUSH,
    ]

    announcement = Announcement.objects.create(
        school=school,
        title=validated_data["title"],
        body=validated_data["body"],
        target_type=validated_data["target_type"],
        target_grade=validated_data.get("target_grade"),
        target_classroom=validated_data.get("target_classroom"),
        channels=channels,
        created_by=user,
    )

    links = list(resolve_target_parent_links(school, announcement))
    # جلوگیری از ارسال پیام تکراری به ولی‌ای که دو فرزند در همان کلاس/مدرسه دارد
    unique_parent_map: dict[int, ParentStudentLink] = {}
    for link in links:
        if link.parent_user_id not in unique_parent_map:
            unique_parent_map[link.parent_user_id] = link

    in_app_notifications_by_user: dict[int, Notification] = {}
    if NotificationChannel.IN_APP in channels:
        notifs_to_create = [
            Notification(
                school=school,
                user=link.parent_user,
                student=link.student,
                announcement=announcement,
                type=NotificationType.ANNOUNCEMENT,
                title=announcement.title,
                message=announcement.body,
                data={"announcement_id": announcement.id},
            )
            for link in unique_parent_map.values()
        ]
        if notifs_to_create:
            created_notifs = Notification.objects.bulk_create(notifs_to_create)
            in_app_notifications_by_user = {n.user_id: n for n in created_notifs}

    deliveries_to_create = []
    for parent_id, link in unique_parent_map.items():
        parent_user = link.parent_user
        linked_notif = in_app_notifications_by_user.get(parent_id)

        if NotificationChannel.PUSH in channels:
            deliveries_to_create.append(
                NotificationDelivery(
                    school=school,
                    announcement=announcement,
                    notification=linked_notif,
                    user=parent_user,
                    student=link.student,
                    channel=NotificationChannel.PUSH,
                    type=NotificationType.ANNOUNCEMENT,
                    recipient=str(parent_user.id),
                    subject=announcement.title,
                    body=announcement.body,
                    status=NotificationDeliveryStatus.PENDING,
                    data={"announcement_id": announcement.id},
                )
            )

        if NotificationChannel.SMS in channels and parent_user.phone_number:
            deliveries_to_create.append(
                NotificationDelivery(
                    school=school,
                    announcement=announcement,
                    notification=linked_notif,
                    user=parent_user,
                    student=link.student,
                    channel=NotificationChannel.SMS,
                    type=NotificationType.ANNOUNCEMENT,
                    recipient=parent_user.phone_number,
                    subject=announcement.title,
                    body=announcement.body,
                    status=NotificationDeliveryStatus.PENDING,
                    data={"announcement_id": announcement.id},
                )
            )

    if deliveries_to_create:
        created_deliveries = NotificationDelivery.objects.bulk_create(deliveries_to_create)
        for d in created_deliveries:
            enqueue_notification_delivery(delivery_id=d.id)

    return announcement