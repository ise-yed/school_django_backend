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