from unittest.mock import patch
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.notifications.enums import (
    AnnouncementTargetType,
    NotificationChannel,
    NotificationDeliveryStatus,
)
from apps.notifications.models import (
    FCMDevice,
    Notification,
    NotificationDelivery,
)
from apps.notifications.tasks import send_notification_delivery_task
from apps.schools.models import AcademicYear, Classroom, Grade, School
from apps.students.models import Enrollment, ParentStudentLink, Student


@pytest.fixture
def notifications_setup(db):
    school_a = School.objects.create(name="دبیرستان البرز", code="alborz")
    school_b = School.objects.create(name="دبیرستان علامه", code="allameh")

    admin_a = User.objects.create_user(
        username="admin_a", password="pass1234", school=school_a, role=User.Role.SCHOOL_ADMIN
    )
    admin_b = User.objects.create_user(
        username="admin_b", password="pass1234", school=school_b, role=User.Role.SCHOOL_ADMIN
    )

    parent_a1 = User.objects.create_user(
        phone_number="09121112233", school=school_a, role=User.Role.PARENT
    )
    parent_a2 = User.objects.create_user(
        phone_number="09124445566", school=school_a, role=User.Role.PARENT
    )
    parent_b1 = User.objects.create_user(
        phone_number="09127778899", school=school_b, role=User.Role.PARENT
    )

    year_a = AcademicYear.objects.create(
        school=school_a,
        title="۱۴۰۴-۱۴۰۵",
        start_date="2025-09-23",
        end_date="2026-06-21",
        is_current=True,
    )
    grade7 = Grade.objects.create(school=school_a, title="هفتم", level_order=7)
    grade8 = Grade.objects.create(school=school_a, title="هشتم", level_order=8)

    class_a7 = Classroom.objects.create(
        school=school_a, academic_year=year_a, grade=grade7, name="هفتم الف"
    )
    class_a8 = Classroom.objects.create(
        school=school_a, academic_year=year_a, grade=grade8, name="هشتم الف"
    )

    st_a7 = Student.objects.create(
        school=school_a,
        first_name="امیر",
        last_name="رضایی",
        father_name="حسن",
        national_code="0012345679",
    )
    st_a8 = Student.objects.create(
        school=school_a,
        first_name="سهراب",
        last_name="علوی",
        father_name="رضا",
        national_code="0123456789",
    )
    st_b = Student.objects.create(
        school=school_b,
        first_name="کیان",
        last_name="کریمی",
        father_name="مهدی",
        national_code="0023456787",
    )

    Enrollment.objects.create(
        school=school_a, student=st_a7, academic_year=year_a, classroom=class_a7
    )
    Enrollment.objects.create(
        school=school_a, student=st_a8, academic_year=year_a, classroom=class_a8
    )

    ParentStudentLink.objects.create(
        school=school_a, parent_user=parent_a1, student=st_a7, is_verified=True
    )
    ParentStudentLink.objects.create(
        school=school_a, parent_user=parent_a2, student=st_a8, is_verified=True
    )
    ParentStudentLink.objects.create(
        school=school_b, parent_user=parent_b1, student=st_b, is_verified=True
    )

    return {
        "school_a": school_a,
        "school_b": school_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "parent_a1": parent_a1,
        "parent_a2": parent_a2,
        "parent_b1": parent_b1,
        "grade7": grade7,
        "grade8": grade8,
        "class_a7": class_a7,
        "class_a8": class_a8,
    }


@pytest.mark.django_db
def test_classroom_and_school_announcement_targeting_and_celery_delivery(
    notifications_setup, django_capture_on_commit_callbacks
):
    """
    ۱. ارسال اعلان فقط به کلاس «هفتم الف» -> فقط ولیِ دانش‌آموز هفتم الف (parent_a1) دریافت می‌کند.
    ۲. ارسال اعلان به کل مدرسه A -> هر دو ولیِ مدرسه A دریافت می‌کنند ولی ولیِ مدرسه B دریافت نمی‌کند.
    ۳. اجرای تسک Celery وضعیت NotificationDelivery را به SENT تغییر می‌دهد.
    """
    client = APIClient()
    client.force_authenticate(user=notifications_setup["parent_a1"])

    # ثبت دستگاه FCM توسط ولی ۱
    res_dev = client.post(
        "/api/v1/notifications/devices/register/",
        {"registration_id": "fcm_token_parent_a1", "device_type": "android"},
    )
    assert res_dev.status_code == 200
    assert FCMDevice.objects.filter(
        user=notifications_setup["parent_a1"], registration_id="fcm_token_parent_a1"
    ).exists()

    # ارسال اعلان توسط ادمین مدرسه A فقط برای کلاس «هفتم الف» با کانال‌های IN_APP, PUSH, SMS
    client.force_authenticate(user=notifications_setup["admin_a"])
    with patch("apps.notifications.tasks.send_notification_delivery_task.delay") as mock_delay:
        with django_capture_on_commit_callbacks(execute=True):
            res_ann = client.post(
                "/api/v1/notifications/announcements/",
                {
                    "title": "جلسه اولیا و مربیان کلاس هفتم الف",
                    "body": "جلسه روز چهارشنبه ساعت ۱۶ برگزار می‌شود.",
                    "target_type": AnnouncementTargetType.CLASSROOM,
                    "target_classroom": notifications_setup["class_a7"].id,
                    "channels": [
                        NotificationChannel.IN_APP,
                        NotificationChannel.PUSH,
                        NotificationChannel.SMS,
                    ],
                },
                format="json",
            )
    assert res_ann.status_code == 201
    assert mock_delay.call_count == 2  # یکی برای PUSH و یکی برای SMS ولیِ هفتم الف

    # ولیِ کلاس هشتم الف و ولیِ مدرسه B نباید این اعلان را گرفته باشند
    assert Notification.objects.filter(user=notifications_setup["parent_a1"]).count() == 1
    assert Notification.objects.filter(user=notifications_setup["parent_a2"]).count() == 0
    assert Notification.objects.filter(user=notifications_setup["parent_b1"]).count() == 0

    # اجرای واقعی تسک Celery روی لاگ‌های ایجادشده
    deliveries = NotificationDelivery.objects.for_school(notifications_setup["school_a"])
    assert deliveries.count() == 2
    for d in deliveries:
        send_notification_delivery_task(d.id)
        d.refresh_from_db()
        assert d.status == NotificationDeliveryStatus.SENT
        assert d.sent_at is not None


@pytest.mark.django_db
def test_parent_inbox_mark_read_and_cross_school_isolation(notifications_setup):
    """
    بررسی صندوق پیام ولی (inbox)، اکشن‌های mark-read و mark-all-read و ایزولاسیون بین مدارس.
    """
    client = APIClient()
    client.force_authenticate(user=notifications_setup["admin_a"])

    # ارسال اعلان به کل مدرسه A
    client.post(
        "/api/v1/notifications/announcements/",
        {
            "title": "تعطیلی روز شنبه",
            "body": "به علت آلودگی هوا مدرسه روز شنبه غیرحضوری است.",
            "target_type": AnnouncementTargetType.SCHOOL,
            "channels": [NotificationChannel.IN_APP],
        },
        format="json",
    )

    # ۱. بررسی صندوق پیام ولی ۱ (parent_a1)
    client.force_authenticate(user=notifications_setup["parent_a1"])
    res_inbox = client.get("/api/v1/notifications/inbox/")
    assert res_inbox.status_code == 200
    assert len(res_inbox.data["results"]) == 1
    notif_id = res_inbox.data["results"][0]["id"]
    assert res_inbox.data["results"][0]["is_read"] is False

    # علامت‌گذاری به عنوان خوانده‌شده
    res_read = client.post(f"/api/v1/notifications/inbox/{notif_id}/mark-read/")
    assert res_read.status_code == 200
    assert res_read.data["is_read"] is True

    # ۲. ولی ۲ هم پیام کل مدرسه را دریافت کرده و با mark-all-read آن را می‌خواند
    client.force_authenticate(user=notifications_setup["parent_a2"])
    res_all = client.post("/api/v1/notifications/inbox/mark-all-read/")
    assert res_all.status_code == 200
    assert res_all.data["marked_as_read"] == 1

    # ۳. ایزولاسیون بین مدارس: ادمین مدرسه B هیچ اعلانی از مدرسه A نمی‌بیند
    client.force_authenticate(user=notifications_setup["admin_b"])
    res_b = client.get("/api/v1/notifications/announcements/")
    assert res_b.status_code == 200
    assert res_b.data["results"] == []


@pytest.mark.django_db
def test_announcement_cross_school_scoping(notifications_setup):
    """بررسی SchoolScopedPrimaryKeyRelatedField در AnnouncementSerializer برای target_grade و target_classroom."""
    school_b = notifications_setup["school_b"]
    grade_b = Grade.objects.create(school=school_b, title="نهم", level_order=9)
    year_b = AcademicYear.objects.create(
        school=school_b,
        title="۱۴۰۴-۱۴۰۵",
        start_date="2025-09-23",
        end_date="2026-06-21",
        is_current=True,
    )
    class_b = Classroom.objects.create(
        school=school_b, academic_year=year_b, grade=grade_b, name="نهم الف"
    )

    client = APIClient()
    client.force_authenticate(user=notifications_setup["admin_a"])

    # ۱. تلاش برای ارسال اعلان به پایه مدرسه B
    res1 = client.post(
        "/api/v1/notifications/announcements/",
        {
            "title": "اعلان غیرمجاز پایه",
            "body": "تست",
            "target_type": AnnouncementTargetType.GRADE,
            "target_grade": grade_b.id,
        },
        format="json",
    )
    assert res1.status_code == 400
    assert "target_grade" in res1.data

    # ۲. تلاش برای ارسال اعلان به کلاس مدرسه B
    res2 = client.post(
        "/api/v1/notifications/announcements/",
        {
            "title": "اعلان غیرمجاز کلاس",
            "body": "تست",
            "target_type": AnnouncementTargetType.CLASSROOM,
            "target_classroom": class_b.id,
        },
        format="json",
    )
    assert res2.status_code == 400
    assert "target_classroom" in res2.data