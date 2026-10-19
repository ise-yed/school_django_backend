import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.schools.models import AcademicYear, Classroom, Grade, School, TeacherAssignment


@pytest.fixture
def school_setup(db):
    school_a = School.objects.create(name="دبیرستان البرز", code="alborz")
    school_b = School.objects.create(name="دبیرستان علامه", code="allameh")

    admin_a = User.objects.create_user(
        username="admin_a", password="pass1234", school=school_a, role=User.Role.SCHOOL_ADMIN
    )
    teacher_a1 = User.objects.create_user(
        username="teacher_a1",
        password="pass1234",
        first_name="رضا",
        last_name="علوی",
        school=school_a,
        role=User.Role.TEACHER,
    )
    teacher_a2 = User.objects.create_user(
        username="teacher_a2",
        password="pass1234",
        first_name="سعید",
        last_name="کریمی",
        school=school_a,
        role=User.Role.TEACHER,
    )
    teacher_b = User.objects.create_user(
        username="teacher_b",
        password="pass1234",
        school=school_b,
        role=User.Role.TEACHER,
    )

    year_a = AcademicYear.objects.create(
        school=school_a,
        title="۱۴۰۴-۱۴۰۵",
        start_date="2025-09-23",
        end_date="2026-06-21",
        is_current=True,
    )
    grade_a7 = Grade.objects.create(school=school_a, title="هفتم", level_order=7)
    grade_b7 = Grade.objects.create(school=school_b, title="هفتم", level_order=7)

    class_a_alef = Classroom.objects.create(
        school=school_a, academic_year=year_a, grade=grade_a7, name="هفتم الف"
    )
    class_a_be = Classroom.objects.create(
        school=school_a, academic_year=year_a, grade=grade_a7, name="هفتم ب"
    )

    # تخصیص معلم ۱ فقط به کلاس «هفتم الف» (زنگ ۱ ریاضی و زنگ ۲ فیزیک)
    TeacherAssignment.objects.create(
        school=school_a,
        teacher=teacher_a1,
        classroom=class_a_alef,
        subject_name="ریاضی",
        session_number=1,
    )
    TeacherAssignment.objects.create(
        school=school_a,
        teacher=teacher_a1,
        classroom=class_a_alef,
        subject_name="فیزیک",
        session_number=2,
    )

    # تخصیص معلم ۲ به کلاس «هفتم ب» (زنگ ۱ ادبیات)
    TeacherAssignment.objects.create(
        school=school_a,
        teacher=teacher_a2,
        classroom=class_a_be,
        subject_name="ادبیات",
        session_number=1,
    )

    return {
        "school_a": school_a,
        "school_b": school_b,
        "admin_a": admin_a,
        "teacher_a1": teacher_a1,
        "teacher_a2": teacher_a2,
        "teacher_b": teacher_b,
        "year_a": year_a,
        "grade_a7": grade_a7,
        "grade_b7": grade_b7,
        "class_a_alef": class_a_alef,
        "class_a_be": class_a_be,
    }


@pytest.mark.django_db
def test_academic_year_jalali_dates_and_single_current(school_setup):
    """ثبت سال تحصیلی با تاریخ شمسی و غیرفعال شدن خودکار سال جاری قبلی."""
    client = APIClient()
    client.force_authenticate(user=school_setup["admin_a"])

    res = client.post(
        "/api/v1/schools/academic-years/",
        {
            "title": "۱۴۰۵-۱۴۰۶",
            "start_date": "۱۴۰۵/۰۷/۰۱",
            "end_date": "۱۴۰۶/۰۳/۳۱",
            "is_current": True,
        },
    )
    assert res.status_code == 201
    assert res.data["start_date"] == "1405-07-01"

    # سال تحصیلی قبلی باید خودکار is_current=False شده باشد
    school_setup["year_a"].refresh_from_db()
    assert school_setup["year_a"].is_current is False


@pytest.mark.django_db
def test_teacher_only_sees_assigned_classrooms_and_read_only(school_setup):
    """
    معلم ۱ که دو زنگ در کلاس «هفتم الف» دارد:
    - در لیست کلاس‌ها فقط «هفتم الف» را(بدون تکرار) می‌بیند.
    - به «هفتم ب» در همان مدرسه دسترسی ندارد (404).
    - اجازه ساخت یا حذف کلاس را ندارد (403).
    """
    client = APIClient()
    client.force_authenticate(user=school_setup["teacher_a1"])

    res_list = client.get("/api/v1/schools/classrooms/")
    assert res_list.status_code == 200
    results = res_list.data["results"]
    assert len(results) == 1
    assert results[0]["id"] == school_setup["class_a_alef"].id

    # عدم دسترسی معلم ۱ به کلاس هفتم ب در همان مدرسه
    res_other_class = client.get(f"/api/v1/schools/classrooms/{school_setup['class_a_be'].id}/")
    assert res_other_class.status_code == 404

    # عدم مجوز معلم برای ساخت کلاس جدید
    res_create = client.post(
        "/api/v1/schools/classrooms/",
        {
            "academic_year": school_setup["year_a"].id,
            "grade": school_setup["grade_a7"].id,
            "name": "هفتم ج",
        },
    )
    assert res_create.status_code == 403


@pytest.mark.django_db
def test_cross_school_foreign_key_injection_blocked(school_setup):
    """ادمین مدرسه A نمی‌تواند پایه یا معلم مدرسه B را به کلاس خود وصل کند."""
    client = APIClient()
    client.force_authenticate(user=school_setup["admin_a"])

    # تلاش برای ساخت کلاس در مدرسه A با پایه متعلق به مدرسه B
    res_class = client.post(
        "/api/v1/schools/classrooms/",
        {
            "academic_year": school_setup["year_a"].id,
            "grade": school_setup["grade_b7"].id,
            "name": "کلاس غیرمجاز",
        },
    )
    assert res_class.status_code == 400
    assert "grade" in res_class.data

    # تلاش برای تخصیص معلمِ مدرسه B به کلاسِ مدرسه A
    res_assign = client.post(
        "/api/v1/schools/assignments/",
        {
            "teacher": school_setup["teacher_b"].id,
            "classroom": school_setup["class_a_alef"].id,
            "subject_name": "شیمی",
            "session_number": 3,
        },
    )
    assert res_assign.status_code == 400
    assert "teacher" in res_assign.data