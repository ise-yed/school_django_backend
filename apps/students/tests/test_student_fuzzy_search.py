import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.schools.models import AcademicYear, Classroom, Grade, School, TeacherAssignment
from apps.students.models import Enrollment, Student


@pytest.fixture
def search_setup(db):
    school_a = School.objects.create(name="دبیرستان البرز", code="alborz")
    school_b = School.objects.create(name="دبیرستان علامه", code="allameh")

    admin_a = User.objects.create_user(
        username="admin_a", password="pass1234", school=school_a, role=User.Role.SCHOOL_ADMIN
    )
    teacher_a1 = User.objects.create_user(
        username="teacher_a1", password="pass1234", school=school_a, role=User.Role.TEACHER
    )
    parent_a = User.objects.create_user(
        phone_number="09121112233", school=school_a, role=User.Role.PARENT
    )

    year_a = AcademicYear.objects.create(
        school=school_a,
        title="۱۴۰۴-۱۴۰۵",
        start_date="2025-09-23",
        end_date="2026-06-21",
        is_current=True,
    )
    grade7 = Grade.objects.create(school=school_a, title="هفتم", level_order=7)
    class_a1 = Classroom.objects.create(
        school=school_a, academic_year=year_a, grade=grade7, name="هفتم الف"
    )
    class_a2 = Classroom.objects.create(
        school=school_a, academic_year=year_a, grade=grade7, name="هفتم ب"
    )

    # معلم ۱ فقط به کلاس «هفتم الف» دسترسی دارد (۲ زنگ مختلف در همان کلاس)
    TeacherAssignment.objects.create(
        school=school_a,
        teacher=teacher_a1,
        classroom=class_a1,
        subject_name="ریاضی",
        session_number=1,
    )
    TeacherAssignment.objects.create(
        school=school_a,
        teacher=teacher_a1,
        classroom=class_a1,
        subject_name="فیزیک",
        session_number=2,
    )

    # دانش‌آموزان کلاس هفتم الف (مدرسه A)
    st_tahmasebi = Student.objects.create(
        school=school_a,
        first_name="امیرحسین",
        last_name="طهماسبی",
        father_name="اسماعیل",
        national_code="0012345679",
    )
    st_ebrahimi = Student.objects.create(
        school=school_a,
        first_name="محمد",
        last_name="ابراهیمی",
        father_name="منوچهر",
        national_code="0123456789",
    )
    Enrollment.objects.create(
        school=school_a, student=st_tahmasebi, academic_year=year_a, classroom=class_a1
    )
    Enrollment.objects.create(
        school=school_a, student=st_ebrahimi, academic_year=year_a, classroom=class_a1
    )

    # دانش‌آموز کلاس هفتم ب (مدرسه A - خارج از دسترسی معلم ۱)
    st_other_class = Student.objects.create(
        school=school_a,
        first_name="محمد",
        last_name="کریمی",
        father_name="داوود",
        national_code="0034567895",
    )
    Enrollment.objects.create(
        school=school_a, student=st_other_class, academic_year=year_a, classroom=class_a2
    )

    # دانش‌آموز مدرسه B (برای تست ایزولاسیون بین مدارس در جستجو)
    st_school_b = Student.objects.create(
        school=school_b,
        first_name="امیرحسین",
        last_name="طهماسبی",
        father_name="اسماعیل",
        national_code="0023456787",
    )

    return {
        "school_a": school_a,
        "school_b": school_b,
        "admin_a": admin_a,
        "teacher_a1": teacher_a1,
        "parent_a": parent_a,
        "class_a1": class_a1,
        "class_a2": class_a2,
        "st_tahmasebi": st_tahmasebi,
        "st_ebrahimi": st_ebrahimi,
        "st_other_class": st_other_class,
        "st_school_b": st_school_b,
    }


@pytest.mark.django_db
def test_fuzzy_search_persian_spelling_variations_and_father_name(search_setup):
    """
    تست تحمل تفاوت املایی فارسی با pg_trgm (تهماسبی -> طهماسبی، ابراهمی -> ابراهیمی)
    و نمایش حتمی نام پدر و کلاس در نتایج جستجو.
    """
    client = APIClient()
    client.force_authenticate(user=search_setup["admin_a"])

    # ۱. جستجو با غلط املایی «تهماسبی» به جای «طهماسبی»
    res1 = client.get("/api/v1/students/search/", {"q": "تهماسبی"})
    assert res1.status_code == 200
    results1 = res1.data["results"]
    assert len(results1) >= 1
    assert results1[0]["id"] == search_setup["st_tahmasebi"].id
    assert results1[0]["father_name"] == "اسماعیل"
    assert results1[0]["current_classroom_name"] == "هفتم الف"

    # ۲. جستجو با غلط املایی «ابراهمی» به جای «ابراهیمی»
    res2 = client.get("/api/v1/students/search/", {"q": "ابراهمی"})
    assert res2.status_code == 200
    ids2 = [r["id"] for r in res2.data["results"]]
    assert search_setup["st_ebrahimi"].id in ids2

    # ۳. جستجو با نام پدر («منوچهر») و حروف عربی («كريمي»)
    res_father = client.get("/api/v1/students/search/", {"father_name": "منوچهر"})
    assert res_father.status_code == 200
    assert [r["id"] for r in res_father.data["results"]] == [search_setup["st_ebrahimi"].id]

    res_arabic = client.get("/api/v1/students/search/", {"q": "كريمي"})
    assert res_arabic.status_code == 200
    assert res_arabic.data["results"][0]["id"] == search_setup["st_other_class"].id

    # ۴. جستجو با بخشی از کد ملی به صورت ارقام فارسی
    res_nc = client.get("/api/v1/students/search/", {"q": "۰۰۱۲۳۴"})
    assert res_nc.status_code == 200
    assert [r["id"] for r in res_nc.data["results"]] == [search_setup["st_tahmasebi"].id]


@pytest.mark.django_db
def test_teacher_search_restricted_to_own_classrooms_and_school_isolation(search_setup):
    """
    ۱. معلم ۱ فقط در بین دانش‌آموزان کلاس‌های خودش («هفتم الف») جستجو می‌کند
       و دانش‌آموز کلاس «هفتم ب» («محمد کریمی») را در نتایج جستجو نمی‌بیند.
    ۲. با اینکه معلم ۱ دو زنگ در کلاس هفتم الف دارد، هر دانش‌آموز فقط یک‌بار در نتایج می‌آید.
    ۳. دانش‌آموز هم‌نام در مدرسه B هرگز در نتایج مدرسه A دیده نمی‌شود.
    """
    client = APIClient()
    client.force_authenticate(user=search_setup["teacher_a1"])

    # جستجوی «محمد»: در مدرسه A دو «محمد» داریم (یکی در هفتم الف، یکی در هفتم ب)
    # معلم ۱ فقط باید محمدِ کلاس هفتم الف را ببیند
    res = client.get("/api/v1/students/search/", {"q": "محمد"})
    assert res.status_code == 200
    returned_ids = [r["id"] for r in res.data["results"]]
    assert returned_ids == [search_setup["st_ebrahimi"].id]
    assert search_setup["st_other_class"].id not in returned_ids

    # حتی اگر معلم ۱ کد ملی دقیق دانش‌آموز کلاس «هفتم ب» را سرچ کند، نباید چیزی ببیند
    res_other = client.get("/api/v1/students/search/", {"q": "0034567895"})
    assert res_other.status_code == 200
    assert res_other.data["results"] == []

    # بررسی ایزولاسیون بین مدارس: دانش‌آموز هم‌نام در مدرسه B نباید در جستجوی ادمین مدرسه A بیاید
    client.force_authenticate(user=search_setup["admin_a"])
    res_school_a = client.get("/api/v1/students/search/", {"q": "طهماسبی"})
    school_a_ids = [r["id"] for r in res_school_a.data["results"]]
    assert search_setup["st_school_b"].id not in school_a_ids


@pytest.mark.django_db
def test_parent_cannot_use_staff_search_endpoint(search_setup):
    """ولی نباید به اندپوینت جستجوی دانش‌آموزان مدرسه دسترسی داشته باشد."""
    client = APIClient()
    client.force_authenticate(user=search_setup["parent_a"])
    res = client.get("/api/v1/students/search/", {"q": "طهماسبی"})
    assert res.status_code == 403


@pytest.mark.django_db
def test_search_without_pagination(search_setup, monkeypatch):
    """
    بررسی اینکه اگر صفحه‌بندی غیرفعال باشد، متد search دچار NameError ناشی از عدم ایمپورت Response نمی‌شود.
    """
    from apps.students.api.v1.views.student import StudentViewSet

    monkeypatch.setattr(StudentViewSet, "pagination_class", None)

    client = APIClient()
    client.force_authenticate(user=search_setup["admin_a"])
    res = client.get("/api/v1/students/search/", {"q": "طهماسبی"})
    assert res.status_code == 200
    assert isinstance(res.data, list)
    assert len(res.data) >= 1
    assert res.data[0]["id"] == search_setup["st_tahmasebi"].id