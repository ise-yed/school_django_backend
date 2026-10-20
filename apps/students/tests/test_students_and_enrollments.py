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