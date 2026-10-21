import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.schools.models import AcademicYear, Classroom, Grade, School, TeacherAssignment
from apps.students.models import Enrollment, ParentStudentLink, Student

@pytest.fixture
def students_setup(db):
    school_a = School.objects.create(name="دبیرستان البرز", code="alborz")
    school_b = School.objects.create(name="دبیرستان علامه", code="allameh")

    admin_a = User.objects.create_user(
        username="admin_a", password="pass1234", school=school_a, role=User.Role.SCHOOL_ADMIN
    )
    teacher_a1 = User.objects.create_user(
        username="teacher_a1", password="pass1234", school=school_a, role=User.Role.TEACHER
    )
    parent_a1 = User.objects.create_user(
        phone_number="09121112233", school=school_a, role=User.Role.PARENT
    )

    year_a = AcademicYear.objects.create(
        school=school_a,
        title="۱۴۰۴-۱۴۰۵",
        start_date="2025-09-23",
        end_date="2026-06-21",
        is_current=True,
    )
    grade_a7 = Grade.objects.create(school=school_a, title="هفتم", level_order=7)
    class_a1 = Classroom.objects.create(
        school=school_a, academic_year=year_a, grade=grade_a7, name="هفتم الف"
    )
    class_a2 = Classroom.objects.create(
        school=school_a, academic_year=year_a, grade=grade_a7, name="هفتم ب"
    )

    # تخصیص معلم ۱ فقط به کلاس هفتم الف
    TeacherAssignment.objects.create(
        school=school_a,
        teacher=teacher_a1,
        classroom=class_a1,
        subject_name="ریاضی",
        session_number=1,
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

    Enrollment.objects.create(
        school=school_a, student=student_a1, academic_year=year_a, classroom=class_a1
    )
    Enrollment.objects.create(
        school=school_a, student=student_a2, academic_year=year_a, classroom=class_a2
    )

    ParentStudentLink.objects.create(
        school=school_a, parent_user=parent_a1, student=student_a1, is_verified=True
    )

    return {
        "admin_a": admin_a,
        "teacher_a1": teacher_a1,
        "parent_a1": parent_a1,
        "student_a1": student_a1,
        "student_a2": student_a2,
        "student_b1": student_b1,
    }


@pytest.mark.django_db
def test_student_isolation_for_admin_teacher_and_parent(students_setup):
    client = APIClient()

    # ۱. ادمین مدرسه A هر دو دانش‌آموز مدرسه A را می‌بیند ولی دانش‌آموز مدرسه B را نمی‌بیند
    client.force_authenticate(user=students_setup["admin_a"])
    res_admin = client.get("/api/v1/students/")
    assert res_admin.status_code == 200
    admin_ids = {item["id"] for item in res_admin.data["results"]}
    assert admin_ids == {students_setup["student_a1"].id, students_setup["student_a2"].id}
    assert client.get(f"/api/v1/students/{students_setup['student_b1'].id}/").status_code == 404

    # ۲. معلم ۱ فقط دانش‌آموز کلاس خودش (هفتم الف) را می‌بیند و به کلاس هفتم ب دسترسی ندارد
    client.force_authenticate(user=students_setup["teacher_a1"])
    res_teacher = client.get("/api/v1/students/")
    assert res_teacher.status_code == 200
    teacher_ids = [item["id"] for item in res_teacher.data["results"]]
    assert teacher_ids == [students_setup["student_a1"].id]
    assert client.get(f"/api/v1/students/{students_setup['student_a2'].id}/").status_code == 404

    # ۳. ولی فقط فرزند تاییدشده خودش را به صورت Read-only می‌بیند
    client.force_authenticate(user=students_setup["parent_a1"])
    res_parent = client.get("/api/v1/students/")
    assert res_parent.status_code == 200
    parent_ids = [item["id"] for item in res_parent.data["results"]]
    assert parent_ids == [students_setup["student_a1"].id]
    assert (
        client.patch(
            f"/api/v1/students/{students_setup['student_a1'].id}/",
            {"first_name": "تغییر"},
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_student_full_name_and_split_persian_name(students_setup):
    from apps.students.services import split_persian_full_name

    # ۱. بررسی تفکیک نام با قاعده کلمه آخر = نام خانوادگی
    assert split_persian_full_name("سهراب") == ("سهراب", "")
    assert split_persian_full_name("سهراب سپهری") == ("سهراب", "سپهری")
    assert split_persian_full_name("سید محمد حسینی") == ("سید محمد", "حسینی")
    assert split_persian_full_name("امیر علی کریمی زاده") == ("امیر علی کریمی", "زاده")

    # ۲. ذخیره full_name پیش‌فرض بر روی مدل Student
    st1 = Student.objects.create(
        school=students_setup["admin_a"].school,
        first_name="محمد",
        last_name="صادقی",
        national_code="0045678911",
    )
    assert st1.full_name == "محمد صادقی"

    # ۳. ذخیره full_name اصلی سفارشی
    st2 = Student.objects.create(
        school=students_setup["admin_a"].school,
        first_name="محمد مهدی",
        last_name="صادقی نژاد",
        full_name="محمد مهدی صادقی نژاد",
        national_code="0056789122",
    )
    assert st2.full_name == "محمد مهدی صادقی نژاد"

    # ۴. مشاهده فیلد full_name در خروجی API
    client = APIClient()
    client.force_authenticate(user=students_setup["admin_a"])
    res = client.get(f"/api/v1/students/{st2.id}/")
    assert res.status_code == 200
    assert res.data["full_name"] == "محمد مهدی صادقی نژاد"


@pytest.mark.django_db
def test_enrollment_cross_school_scoping(students_setup):
    """بررسی SchoolScopedPrimaryKeyRelatedField در EnrollmentSerializer برای student و classroom."""
    school_b = students_setup["student_b1"].school
    year_b = AcademicYear.objects.create(
        school=school_b,
        title="۱۴۰۴-۱۴۰۵",
        start_date="2025-09-23",
        end_date="2026-06-21",
        is_current=True,
    )
    grade_b = Grade.objects.create(school=school_b, title="هفتم", level_order=7)
    class_b = Classroom.objects.create(
        school=school_b, academic_year=year_b, grade=grade_b, name="هفتم ب"
    )

    client = APIClient()
    client.force_authenticate(user=students_setup["admin_a"])

    class_a = Classroom.objects.filter(school=students_setup["admin_a"].school).first()

    # ۱. تلاش برای ثبت‌نام دانش‌آموز مدرسه B در کلاس مدرسه A
    res1 = client.post(
        "/api/v1/students/enrollments/",
        {
            "student": students_setup["student_b1"].id,
            "classroom": class_a.id,
        },
        format="json",
    )
    assert res1.status_code == 400
    assert "student" in res1.data

    # ۲. تلاش برای ثبت‌نام دانش‌آموز مدرسه A در کلاس مدرسه B
    res2 = client.post(
        "/api/v1/students/enrollments/",
        {
            "student": students_setup["student_a1"].id,
            "classroom": class_b.id,
        },
        format="json",
    )
    assert res2.status_code == 400
    assert "classroom" in res2.data


@pytest.mark.django_db
def test_student_delete_is_blocked_and_is_active_supported(students_setup):
    """
    بررسی اینکه متد DELETE برای دانش‌آموز مسدود است (405) و غیرفعال‌سازی با PATCH انجام می‌شود
    و متد delete() مدل نیز soft-delete انجام می‌دهد تا سوابق حضور و غیاب و انضباطی با CASCADE پاک نشوند.
    """
    student = students_setup["student_a1"]
    admin_a = students_setup["admin_a"]

    client = APIClient()
    client.force_authenticate(user=admin_a)

    # ۱. متد DELETE در API برای دانش‌آموز مسدود است
    res_del = client.delete(f"/api/v1/students/{student.id}/")
    assert res_del.status_code == 405

    # ۲. غیرفعال‌سازی از طریق PATCH
    res_patch = client.patch(
        f"/api/v1/students/{student.id}/",
        {"is_active": False},
        format="json",
    )
    assert res_patch.status_code == 200
    student.refresh_from_db()
    assert student.is_active is False

    # ۳. متد .delete() در سطح مدل پایتون رکورد را پاک فیزیکی نمی‌کند بلکه غیرفعال می‌کند
    student.is_active = True
    student.save()
    student.delete()
    student.refresh_from_db()
    assert student.is_active is False


@pytest.mark.django_db
def test_teacher_cannot_see_past_years_or_transferred_students(students_setup):
    """
    بررسی اینکه معلم فقط دانش‌آموزان با ثبت‌نام فعال در سال تحصیلی جاری را می‌بیند
    و دانش‌آموزان سال‌های گذشته، منتقل‌شده (ثبت‌نام غیرفعال) یا غیرفعال‌شده را نمی‌بیند.
    """
    school_a = students_setup["admin_a"].school
    teacher = students_setup["teacher_a1"]
    current_class = Classroom.objects.get(name="هفتم الف", school=school_a)
    grade = current_class.grade

    # ۱. سال تحصیلی گذشته و کلاس قدیمی
    past_year = AcademicYear.objects.create(
        school=school_a,
        title="۱۴۰۳-۱۴۰۴",
        start_date="2024-09-23",
        end_date="2025-06-21",
        is_current=False,
    )
    old_class = Classroom.objects.create(
        school=school_a,
        academic_year=past_year,
        grade=grade,
        name="هفتم الف قدیم",
    )
    TeacherAssignment.objects.create(
        school=school_a,
        teacher=teacher,
        classroom=old_class,
        subject_name="ریاضی",
        session_number=1,
    )
    student_past_year = Student.objects.create(
        school=school_a,
        first_name="بهرام",
        last_name="قدیمی",
        father_name="کاظم",
        national_code="0034567895",
    )
    Enrollment.objects.create(
        school=school_a,
        student=student_past_year,
        academic_year=past_year,
        classroom=old_class,
        is_active=True,
    )

    # ۲. دانش‌آموز منتقل‌شده (ثبت‌نام سال جاری غیرفعال شده است)
    student_transferred = Student.objects.create(
        school=school_a,
        first_name="کامران",
        last_name="انتقالی",
        father_name="منصور",
        national_code="0045678901",
    )
    Enrollment.objects.create(
        school=school_a,
        student=student_transferred,
        academic_year=current_class.academic_year,
        classroom=current_class,
        is_active=False,
    )

    # ۳. دانش‌آموز غیرفعال‌شده (soft-deleted)
    student_deactivated = Student.objects.create(
        school=school_a,
        first_name="وحید",
        last_name="حذف‌شده",
        father_name="محمود",
        national_code="0056789017",
        is_active=False,
    )
    Enrollment.objects.create(
        school=school_a,
        student=student_deactivated,
        academic_year=current_class.academic_year,
        classroom=current_class,
        is_active=True,
    )

    client = APIClient()
    client.force_authenticate(user=teacher)

    # بررسی لیست دانش‌آموزان برای معلم
    res_list = client.get("/api/v1/students/")
    assert res_list.status_code == 200
    returned_ids = {s["id"] for s in res_list.data["results"]}

    # فقط دانش‌آموز فعال سال جاری باید دیده شود
    assert students_setup["student_a1"].id in returned_ids
    assert student_past_year.id not in returned_ids
    assert student_transferred.id not in returned_ids
    assert student_deactivated.id not in returned_ids

    # بررسی دسترسی جزئیات (Retrieve)
    assert client.get(f"/api/v1/students/{student_past_year.id}/").status_code == 404
    assert client.get(f"/api/v1/students/{student_transferred.id}/").status_code == 404
    assert client.get(f"/api/v1/students/{student_deactivated.id}/").status_code == 404

    # بررسی در اکشن جستجوی فازی (Search)
    res_search = client.get("/api/v1/students/search/?q=قدیمی")
    assert res_search.status_code == 200
    assert res_search.data["count"] == 0
    assert len(res_search.data["results"]) == 0

    # بررسی در لیست ثبت‌نام‌ها (Enrollments)
    res_enrollments = client.get("/api/v1/students/enrollments/")
    assert res_enrollments.status_code == 200
    enrollment_student_ids = {e["student"] for e in res_enrollments.data["results"]}
    assert students_setup["student_a1"].id in enrollment_student_ids
    assert student_past_year.id not in enrollment_student_ids
    assert student_transferred.id not in enrollment_student_ids
    assert student_deactivated.id not in enrollment_student_ids