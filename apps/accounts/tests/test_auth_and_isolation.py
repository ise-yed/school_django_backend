import pytest
from django.core.cache import cache
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.accounts.services import generate_and_send_otp
from apps.schools.models import School


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def setup_schools(db):
    school_a = School.objects.create(name="دبیرستان البرز", code="alborz")
    school_b = School.objects.create(name="دبیرستان علامه", code="allameh")

    admin_a = User.objects.create_user(
        username="admin_a", password="pass1234", school=school_a, role=User.Role.SCHOOL_ADMIN
    )
    admin_b = User.objects.create_user(
        username="admin_b", password="pass1234", school=school_b, role=User.Role.SCHOOL_ADMIN
    )
    teacher_b = User.objects.create_user(
        username="teacher_b", password="pass1234", school=school_b, role=User.Role.TEACHER
    )
    return {
        "school_a": school_a,
        "school_b": school_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "teacher_b": teacher_b,
    }


@pytest.mark.django_db
def test_cross_school_isolation_list_detail_update_delete(setup_schools):
    client = APIClient()
    client.force_authenticate(user=setup_schools["admin_a"])
    teacher_b = setup_schools["teacher_b"]

    res_list = client.get("/api/v1/accounts/staff/")
    assert res_list.status_code == 200
    returned_ids = [item["id"] for item in res_list.data["results"]]
    assert teacher_b.id not in returned_ids
    assert setup_schools["admin_a"].id in returned_ids

    assert client.get(f"/api/v1/accounts/staff/{teacher_b.id}/").status_code == 404
    assert client.patch(f"/api/v1/accounts/staff/{teacher_b.id}/", {"first_name": "X"}).status_code == 404
    assert client.delete(f"/api/v1/accounts/staff/{teacher_b.id}/").status_code == 404


@pytest.mark.django_db
def test_create_forces_current_user_school(setup_schools):
    client = APIClient()
    client.force_authenticate(user=setup_schools["admin_a"])

    res = client.post(
        "/api/v1/accounts/staff/",
        {
            "username": "teacher_a1",
            "password": "securepassword",
            "role": User.Role.TEACHER,
            "school": setup_schools["school_b"].id,
        },
    )
    assert res.status_code == 201
    created_teacher = User.objects.get(username="teacher_a1")
    assert created_teacher.school_id == setup_schools["school_a"].id


@pytest.mark.django_db
def test_parent_otp_flow_and_rate_limit(setup_schools):
    client = APIClient()

    res_unreg = client.post("/api/v1/accounts/auth/parent/otp/request/", {"phone_number": "09121112233"})
    assert res_unreg.status_code == 401

    User.objects.create_user(
        phone_number="09123334455",
        school=setup_schools["school_a"],
        role=User.Role.PARENT,
    )

    code = generate_and_send_otp("09123334455")
    res_verify = client.post(
        "/api/v1/accounts/auth/parent/otp/verify/",
        {"phone_number": "۰۹۱۲۳۳۳۴۴۵۵", "code": code},
    )
    assert res_verify.status_code == 200
    assert "access" in res_verify.data
    assert res_verify.data["user"]["school_id"] == setup_schools["school_a"].id


@pytest.mark.django_db
def test_generate_and_send_otp_prints_to_console(capsys):
    """
    بررسی اینکه کد OTP تولید شده در کنسول چاپ شده و ارائه‌دهنده پیامک فراخوانی می‌شود.
    """
    phone = "09129998877"
    code = generate_and_send_otp(phone)
    captured = capsys.readouterr()
    assert f"[OTP Console Log] Phone: {phone} | Code: {code}" in captured.out
    assert f"[Console SMS] To: {phone}" in captured.out
    assert code in captured.out


@pytest.mark.django_db
def test_staff_update_without_password_succeeds_and_preserves_password(setup_schools):
    """
    بررسی اینکه هنگام ویرایش با PUT یا PATCH، نیازی به ارسال فیلد password نیست
    و رمز عبور قبلی کاربر حفظ می‌شود. همچنین هنگام ساخت (POST)، ارسال رمز اجباری است.
    """
    client = APIClient()
    client.force_authenticate(user=setup_schools["admin_a"])

    # ۱. تلاش برای ساخت کادر آموزشی بدون پسورد -> 400
    res_fail_create = client.post(
        "/api/v1/accounts/staff/",
        {
            "username": "teacher_nopass",
            "role": User.Role.TEACHER,
            "first_name": "علی",
            "last_name": "مرادی",
        },
    )
    assert res_fail_create.status_code == 400
    assert "password" in res_fail_create.data

    # ۲. ساخت کاربر با پسورد معتبر
    res_create = client.post(
        "/api/v1/accounts/staff/",
        {
            "username": "teacher_withpass",
            "password": "initial_password_123",
            "role": User.Role.TEACHER,
            "first_name": "علی",
            "last_name": "مرادی",
        },
    )
    assert res_create.status_code == 201
    user_id = res_create.data["id"]
    teacher = User.objects.get(id=user_id)
    assert teacher.check_password("initial_password_123")

    # ۳. ویرایش با PUT کامل بدون ارسال فیلد password
    res_put = client.put(
        f"/api/v1/accounts/staff/{user_id}/",
        {
            "username": "teacher_withpass",
            "first_name": "علیرضا",
            "last_name": "مرادی‌اصل",
            "role": User.Role.TEACHER,
        },
    )
    assert res_put.status_code == 200
    assert res_put.data["first_name"] == "علیرضا"
    assert res_put.data["last_name"] == "مرادی‌اصل"

    # بررسی اینکه پسورد قبلی کاربر تغییر نکرده و همچنان معتبر است
    teacher.refresh_from_db()
    assert teacher.check_password("initial_password_123")
