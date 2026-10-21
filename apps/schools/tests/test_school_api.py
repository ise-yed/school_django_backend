import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.schools.models import School


@pytest.mark.django_db
def test_superuser_can_create_school_and_admin():
    superuser = User.objects.create_superuser(username="superadmin", password="superpassword")
    school_a = School.objects.create(name="دبیرستان البرز", code="alborz")
    admin_a = User.objects.create_user(
        username="admin_a", password="pass1234", school=school_a, role=User.Role.SCHOOL_ADMIN
    )

    client = APIClient()

    # ادمین مدرسه نباید بتواند مدرسه جدید بسازد
    client.force_authenticate(user=admin_a)
    res_forbidden = client.post("/api/v1/schools/manage/", {"name": "مدرسه جدید", "code": "new-s"})
    assert res_forbidden.status_code == 403

    # سوپریوزر مدرسه و ادمین آن را می‌سازد
    client.force_authenticate(user=superuser)
    res_school = client.post("/api/v1/schools/manage/", {"name": "فرزانگان", "code": "farzanegan"})
    assert res_school.status_code == 201
    school_id = res_school.data["id"]

    res_admin = client.post(
        f"/api/v1/schools/manage/{school_id}/create-admin/",
        {"username": "farzanegan_admin", "password": "adminpassword"},
    )
    assert res_admin.status_code == 201
    assert res_admin.data["school_id"] == school_id


@pytest.mark.django_db
def test_school_delete_is_blocked_and_soft_delete_supported():
    """
    بررسی اینکه متد DELETE برای مدرسه در API مسدود است (405)
    و غیرفعال‌سازی با PATCH is_active=False انجام می‌شود و متد .delete() پایتون هم soft-delete می‌کند.
    """
    superuser = User.objects.create_superuser(username="superadmin", password="superpassword")
    school = School.objects.create(name="مدرسه تست", code="test-school")

    client = APIClient()
    client.force_authenticate(user=superuser)

    # ۱. متد DELETE در API مسدود است
    res_del = client.delete(f"/api/v1/schools/manage/{school.id}/")
    assert res_del.status_code == 405

    # ۲. غیرفعال‌سازی با PATCH انجام می‌شود
    res_patch = client.patch(f"/api/v1/schools/manage/{school.id}/", {"is_active": False})
    assert res_patch.status_code == 200
    school.refresh_from_db()
    assert school.is_active is False

    # ۳. متد .delete() در سطح مدل پایتون رکورد را پاک فیزیکی نمی‌کند بلکه غیرفعال می‌کند
    school.is_active = True
    school.save()
    school.delete()
    school.refresh_from_db()
    assert school.is_active is False