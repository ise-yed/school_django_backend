import io
import openpyxl
import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import generate_and_send_otp
from apps.schools.models import School
from apps.students.models import ParentStudentLink, Student


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def parent_onboarding_setup(db):
    school_a = School.objects.create(name="دبیرستان البرز", code="alborz")
    school_b = School.objects.create(name="دبیرستان علامه", code="allameh")

    admin_a = User.objects.create_user(
        username="admin_a", password="pass1234", school=school_a, role=User.Role.SCHOOL_ADMIN
    )
    admin_b = User.objects.create_user(
        username="admin_b", password="pass1234", school=school_b, role=User.Role.SCHOOL_ADMIN
    )

    student_a1 = Student.objects.create(
        school=school_a,
        first_name="امیر",
        last_name="رضایی",
        father_name="حسن",
        national_code="0012345679",
    )
    student_a2 = Student.objects.create(
        school=school_a,
        first_name="سارا",
        last_name="کریمی",
        father_name="مهدی",
        national_code="0123456789",
    )
    student_b1 = Student.objects.create(
        school=school_b,
        first_name="کیان",
        last_name="علوی",
        father_name="رضا",
        national_code="0023456787",
    )

    return {
        "school_a": school_a,
        "school_b": school_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "student_a1": student_a1,
        "student_a2": student_a2,
        "student_b1": student_b1,
    }


@pytest.mark.django_db
def test_admin_manual_assign_and_change_parent_phone(parent_onboarding_setup):
    """ثبت دستی ولی و تغییر شماره موبایل ولی توسط کادر آموزشی + ایزولاسیون بین مدارس."""
    client = APIClient()
    client.force_authenticate(user=parent_onboarding_setup["admin_a"])

    # ۱. ثبت دستی ولی با کد ملی دانش‌آموز
    res_create = client.post(
        "/api/v1/students/parent-links/",
        {
            "student_national_code": "0012345679",
            "phone_number": "۰۹۱۲۱۱۱۲۲۳۳",
            "relation": "FATHER",
        },
    )
    assert res_create.status_code == 201
    assert res_create.data["parent_phone"] == "09121112233"
    assert res_create.data["is_verified"] is True
    link_id = res_create.data["id"]

    # ۲. تغییر شماره موبایل ولی توسط کادر آموزشی
    res_change = client.post(
        f"/api/v1/students/parent-links/{link_id}/change-phone/",
        {"phone_number": "09129998877", "relation": "MOTHER"},
    )
    assert res_change.status_code == 200
    assert res_change.data["parent_phone"] == "09129998877"
    assert res_change.data["relation"] == "MOTHER"

    # ۳. ادمین مدرسه B نباید به لینک‌های اولیای مدرسه A دسترسی داشته باشد
    client.force_authenticate(user=parent_onboarding_setup["admin_b"])
    assert client.get(f"/api/v1/students/parent-links/{link_id}/").status_code == 404


@pytest.mark.django_db
def test_second_excel_import_for_parent_phones(parent_onboarding_setup):
    """تست ایمپورت اکسل دوم شامل کد ملی دانش‌آموز و موبایل ولی."""
    client = APIClient()
    client.force_authenticate(user=parent_onboarding_setup["admin_a"])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["کد ملی دانش‌آموز", "موبایل ولی"])
    ws.append([12345679, "۰۹۱۲۳۳۳۴۴۵۵"])       # کد ملی ۸ رقمی بدون صفر ابتدایی (معتبر در مدرسه A)
    ws.append(["0123456789", "09123334455"])    # فرزند دوم همان ولی در همان مدرسه
    ws.append(["0023456787", "09127776655"])    # دانش‌آموز متعلق به مدرسه B -> باید خطا بخورد

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    excel_file = SimpleUploadedFile(
        "parents.xlsx",
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    res = client.post("/api/v1/imports/parents/", {"file": excel_file}, format="multipart")
    assert res.status_code == 200
    assert res.data["linked_count"] == 2
    assert res.data["error_count"] == 1

    # ولی باید به هر دو فرزندش در مدرسه A وصل شده باشد
    links = ParentStudentLink.objects.for_school(parent_onboarding_setup["school_a"]).filter(
        parent_user__phone_number="09123334455", is_verified=True
    )
    assert links.count() == 2


@pytest.mark.django_db
def test_parent_self_onboarding_with_national_code_and_unauthorized_protection(
    parent_onboarding_setup,
):
    """
    ۱. اگر شماره‌ای در اکسل یا توسط مدرسه ثبت نشده باشد و با کد ملی وارد شود:
       رکورد اتصال در انتظار تأیید کادر آموزشی (is_verified=False) ثبت شده و به کاربر خطای ۴۰۳ داده می‌شود
       تا از تصاحب غیرمجاز حساب دانش‌آموز توسط افراد غیرمجاز جلوگیری شود.
    ۲. پس از تأیید کادر آموزشی، ولی با OTP وارد می‌شود و توکن دریافت می‌کند.
    ۳. اگر شماره از قبل در اکسل یا توسط کادر آموزشی ثبت شده باشد (is_verified=True)، مستقیماً وارد می‌شود.
    """
    client = APIClient()

    # ۱. شماره‌ای که در اکسل نبوده، با کد ملی دانش‌آموز درخواست OTP می‌دهد
    res_req = client.post(
        "/api/v1/accounts/auth/parent/otp/request/",
        {
            "phone_number": "09124445566",
            "student_national_code": "0012345679",
        },
    )
    assert res_req.status_code == 200

    code1 = generate_and_send_otp("09124445566")
    res_verify1 = client.post(
        "/api/v1/accounts/auth/parent/otp/verify/",
        {
            "phone_number": "09124445566",
            "code": code1,
            "student_national_code": "0012345679",
        },
    )
    # باید 403 بگیرد و منتظر تأیید کادر آموزشی باشد (جلوگیری از تصاحب خودکار)
    assert res_verify1.status_code == 403

    unverified_link = ParentStudentLink.objects.get(
        student=parent_onboarding_setup["student_a1"],
        parent_user__phone_number="09124445566",
    )
    assert unverified_link.is_verified is False

    # ۲. کادر آموزشی مدرسه شماره را بررسی و تأیید می‌کند
    client.force_authenticate(user=parent_onboarding_setup["admin_a"])
    res_admin_verify = client.post(
        f"/api/v1/students/parent-links/{unverified_link.id}/verify/"
    )
    assert res_admin_verify.status_code == 200
    assert res_admin_verify.data["is_verified"] is True

    # ۳. پس از تأیید کادر آموزشی، ولی می‌تواند با OTP وارد شود و توکن بگیرد
    client.force_authenticate(user=None)
    code2 = generate_and_send_otp("09124445566")
    res_verify2 = client.post(
        "/api/v1/accounts/auth/parent/otp/verify/",
        {"phone_number": "09124445566", "code": code2},
    )
    assert res_verify2.status_code == 200
    assert "access" in res_verify2.data

    # ۴. شماره‌ای که از قبل در اکسل یا سیستم تأیید شده (مثلاً student_a2 با شماره 09127778899)
    parent_pre_user = User.objects.create_user(
        school=parent_onboarding_setup["school_a"],
        phone_number="09127778899",
        role=User.Role.PARENT,
    )
    ParentStudentLink.objects.create(
        school=parent_onboarding_setup["school_a"],
        parent_user=parent_pre_user,
        student=parent_onboarding_setup["student_a2"],
        is_verified=True,
    )

    code3 = generate_and_send_otp("09127778899")
    res_pre = client.post(
        "/api/v1/accounts/auth/parent/otp/verify/",
        {"phone_number": "09127778899", "code": code3},
    )
    assert res_pre.status_code == 200
    assert "access" in res_pre.data


@pytest.mark.django_db
def test_parent_and_teacher_same_phone_coexistence(parent_onboarding_setup):
    """
    بررسی اینکه اگر شماره موبایل یک ولی با شماره یک معلم در یک مدرسه یکسان باشد:
    ۱. رکورد معلم بازنویسی یا مخدوش نشود (نام و نقش حفظ شود).
    ۲. رکورد جداگانه با نقش PARENT ایجاد شود.
    ۳. ParentStudentLink به کاربر ولی متصل شود نه کاربر معلم.
    ۴. ولی بتواند با OTP لاگین کند و توکن دریافت کند.
    """
    client = APIClient()
    school_a = parent_onboarding_setup["school_a"]
    admin_a = parent_onboarding_setup["admin_a"]
    student_a1 = parent_onboarding_setup["student_a1"]

    # معلمی با این شماره در مدرسه A ثبت است
    shared_phone = "09125556677"
    teacher = User.objects.create_user(
        username="teacher_alborz",
        phone_number=shared_phone,
        first_name="محمد",
        last_name="استاد",
        school=school_a,
        role=User.Role.TEACHER,
    )

    # ادمین مدرسه ولی دانش‌آموز را با همان شماره موبایل ثبت می‌کند
    client.force_authenticate(user=admin_a)
    res_assign = client.post(
        "/api/v1/students/parent-links/",
        {
            "student_national_code": student_a1.national_code,
            "phone_number": shared_phone,
            "relation": "FATHER",
        },
    )
    assert res_assign.status_code == 201

    # بازخوانی معلم از دیتابیس: نام و نقش نباید تغییر کرده باشد
    teacher.refresh_from_db()
    assert teacher.role == User.Role.TEACHER
    assert teacher.first_name == "محمد"
    assert teacher.last_name == "استاد"

    # کاربر ولی جداگانه‌ای ساخته شده است
    parent_user = User.objects.get(
        school=school_a,
        phone_number=shared_phone,
        role=User.Role.PARENT,
    )
    assert parent_user.id != teacher.id
    assert parent_user.role == User.Role.PARENT

    # پیوند به ولی متصل است نه معلم
    link = ParentStudentLink.objects.get(student=student_a1, school=school_a)
    assert link.parent_user_id == parent_user.id
    assert link.parent_user_id != teacher.id

    # ورود ولی با OTP و بررسی توکن
    client.force_authenticate(user=None)
    res_req = client.post(
        "/api/v1/accounts/auth/parent/otp/request/",
        {"phone_number": shared_phone},
    )
    assert res_req.status_code == 200

    otp_code = generate_and_send_otp(shared_phone)
    res_ver = client.post(
        "/api/v1/accounts/auth/parent/otp/verify/",
        {"phone_number": shared_phone, "code": otp_code},
    )
    assert res_ver.status_code == 200
    assert "access" in res_ver.data