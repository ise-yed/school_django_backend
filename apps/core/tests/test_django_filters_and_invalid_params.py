import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.schools.models import AcademicYear, Classroom, Grade, School
from apps.students.models import Enrollment, Student


@pytest.fixture
def filter_test_setup(db):
    school = School.objects.create(name="مدرسه نمونه", code="sample")
    admin = User.objects.create_user(
        username="admin_sample",
        password="password123",
        school=school,
        role=User.Role.SCHOOL_ADMIN,
    )
    year = AcademicYear.objects.create(
        school=school,
        title="۱۴۰۴-۱۴۰۵",
        start_date="2025-09-23",
        end_date="2026-06-21",
        is_current=True,
    )
    grade = Grade.objects.create(school=school, title="هفتم", level_order=7)
    classroom = Classroom.objects.create(
        school=school,
        academic_year=year,
        grade=grade,
        name="هفتم الف",
    )
    student = Student.objects.create(
        school=school,
        first_name="علی",
        last_name="احمدی",
        father_name="محمد",
        national_code="0012345679",
    )
    Enrollment.objects.create(
        school=school,
        student=student,
        academic_year=year,
        classroom=classroom,
        is_active=True,
    )

    return {
        "school": school,
        "admin": admin,
        "year": year,
        "classroom": classroom,
        "student": student,
    }


@pytest.mark.django_db
def test_invalid_filter_param_returns_400_instead_of_500(filter_test_setup):
    """
    بررسی اینکه ارسال پارامترهای نامعتبر مثل ?classroom=abc به جای خطای سرور (500)،
    خطای اعتبارسنجی فرم (400 Bad Request) برمی‌گرداند.
    """
    client = APIClient()
    client.force_authenticate(user=filter_test_setup["admin"])

    # ۱. فیلتر دانش‌آموز با شناسه کلاس نامعتبر
    res_st = client.get("/api/v1/students/?classroom=abc")
    assert res_st.status_code == 400
    assert "classroom" in res_st.data

    # ۲. جستجوی فازی دانش‌آموز با شناسه کلاس نامعتبر
    res_search = client.get("/api/v1/students/search/?classroom=xyz")
    assert res_search.status_code == 400
    assert "classroom" in res_search.data

    # ۳. فیلتر کلاس‌ها با سال تحصیلی نامعتبر
    res_class = client.get("/api/v1/schools/classrooms/?academic_year=invalid")
    assert res_class.status_code == 400
    assert "academic_year" in res_class.data

    # ۴. فیلتر ثبت‌نام‌ها با شناسه کلاس نامعتبر
    res_enr = client.get("/api/v1/students/enrollments/?classroom=not_a_number")
    assert res_enr.status_code == 400
    assert "classroom" in res_enr.data

    # ۵. فیلتر حضور و غیاب با شناسه کلاس نامعتبر
    res_att = client.get("/api/v1/attendance/records/?classroom=abc")
    assert res_att.status_code == 400
    assert "classroom" in res_att.data

    # ۶. فیلتر انضباطی با شناسه دانش‌آموز نامعتبر
    res_disc = client.get("/api/v1/discipline/records/?student=invalid_id")
    assert res_disc.status_code == 400
    assert "student" in res_disc.data

    # ۷. فیلتر اتصال اولیا با شناسه کلاس نامعتبر
    res_link = client.get("/api/v1/students/parent-links/?classroom=bad")
    assert res_link.status_code == 400
    assert "classroom" in res_link.data


@pytest.mark.django_db
def test_valid_filter_params_work_as_expected(filter_test_setup):
    """
    بررسی اینکه فیلترهای صحیح بدون مشکل اجرا شده و کد ۲۰۰ با خروجی مناسب می‌دهند.
    """
    client = APIClient()
    client.force_authenticate(user=filter_test_setup["admin"])

    c_id = filter_test_setup["classroom"].id
    y_id = filter_test_setup["year"].id

    res_st = client.get(f"/api/v1/students/?classroom={c_id}")
    assert res_st.status_code == 200
    assert len(res_st.data["results"]) == 1

    res_class = client.get(f"/api/v1/schools/classrooms/?academic_year={y_id}")
    assert res_class.status_code == 200
    assert len(res_class.data["results"]) == 1

    res_enr = client.get(f"/api/v1/students/enrollments/?classroom={c_id}")
    assert res_enr.status_code == 200
    assert len(res_enr.data["results"]) == 1
