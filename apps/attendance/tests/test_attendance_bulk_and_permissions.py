import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord
from apps.schools.models import AcademicYear, Classroom, Grade, School, TeacherAssignment
from apps.students.models import Enrollment, ParentStudentLink, Student


@pytest.fixture
def attendance_setup(db):
    school_a = School.objects.create(name="دبیرستان البرز", code="alborz")
    school_b = School.objects.create(name="دبیرستان علامه", code="allameh")

    admin_a = User.objects.create_user(
        username="admin_a", password="pass1234", school=school_a, role=User.Role.SCHOOL_ADMIN
    )
    admin_b = User.objects.create_user(
        username="admin_b", password="pass1234", school=school_b, role=User.Role.SCHOOL_ADMIN
    )
    teacher_a1 = User.objects.create_user(
        username="teacher_a1", password="pass1234", school=school_a, role=User.Role.TEACHER
    )
    teacher_a2 = User.objects.create_user(
        username="teacher_a2", password="pass1234", school=school_a, role=User.Role.TEACHER
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
    grade7 = Grade.objects.create(school=school_a, title="هفتم", level_order=7)
    class_a1 = Classroom.objects.create(
        school=school_a, academic_year=year_a, grade=grade7, name="هفتم الف"
    )
    class_a2 = Classroom.objects.create(
        school=school_a, academic_year=year_a, grade=grade7, name="هفتم ب"
    )

    # معلم ۱: کلاس هفتم الف، زنگ ۱
    TeacherAssignment.objects.create(
        school=school_a,
        teacher=teacher_a1,
        classroom=class_a1,
        subject_name="ریاضی",
        session_number=1,
    )
    # معلم ۲: کلاس هفتم الف زنگ ۲ + کلاس هفتم ب زنگ ۱
    TeacherAssignment.objects.create(
        school=school_a,
        teacher=teacher_a2,
        classroom=class_a1,
        subject_name="ادبیات",
        session_number=2,
    )
    TeacherAssignment.objects.create(
        school=school_a,
        teacher=teacher_a2,
        classroom=class_a2,
        subject_name="ادبیات",
        session_number=1,
    )

    st1 = Student.objects.create(
        school=school_a,
        first_name="امیر",
        last_name="رضایی",
        father_name="حسن",
        national_code="0012345679",
    )
    st2 = Student.objects.create(
        school=school_a,
        first_name="سهراب",
        last_name="علوی",
        father_name="رضا",
        national_code="0123456789",
    )
    st_other_class = Student.objects.create(
        school=school_a,
        first_name="پویا",
        last_name="کریمی",
        father_name="مهدی",
        national_code="0034567895",
    )

    Enrollment.objects.create(school=school_a, student=st1, academic_year=year_a, classroom=class_a1)
    Enrollment.objects.create(school=school_a, student=st2, academic_year=year_a, classroom=class_a1)
    Enrollment.objects.create(
        school=school_a, student=st_other_class, academic_year=year_a, classroom=class_a2
    )

    # ولی فقط به دانش‌آموز ۱ (امیر رضایی) متصل و تأیید شده است
    ParentStudentLink.objects.create(
        school=school_a, parent_user=parent_a1, student=st1, is_verified=True
    )

    return {
        "school_a": school_a,
        "school_b": school_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "teacher_a1": teacher_a1,
        "teacher_a2": teacher_a2,
        "parent_a1": parent_a1,
        "class_a1": class_a1,
        "class_a2": class_a2,
        "st1": st1,
        "st2": st2,
        "st_other_class": st_other_class,
    }


@pytest.mark.django_db
def test_bulk_submit_attendance_and_upsert_idempotency(attendance_setup):
    """
    ثبت یک‌جای حضور و غیاب کل کلاس در یک درخواست و به‌روزرسانی خودکار در صورت ارسال مجدد (بدون ثبت تکراری).
    """
    client = APIClient()
    client.force_authenticate(user=attendance_setup["teacher_a1"])

    # ۱. ارسال یک‌جای وضعیت هر دو دانش‌آموز کلاس هفتم الف برای زنگ ۱ در تاریخ شمسی ۱۴۰۴/۰۷/۱۵
    res_bulk = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": attendance_setup["class_a1"].id,
            "date": "۱۴۰۴/۰۷/۱۵",
            "session_number": 1,
            "records": [
                {
                    "student_id": attendance_setup["st1"].id,
                    "status": "PRESENT",
                    "note": "",
                },
                {
                    "student_id": attendance_setup["st2"].id,
                    "status": "UNEXCUSED_ABSENCE",
                    "note": "غیبت در زنگ ریاضی",
                },
            ],
        },
        format="json",
    )
    assert res_bulk.status_code == 200
    assert res_bulk.data["created_count"] == 2
    assert res_bulk.data["updated_count"] == 0
    assert res_bulk.data["date"] == "1404-07-15"

    # ۲. ارسال مجدد برای همان روز و زنگ (تغییر وضعیت دانش‌آموز دوم از غایب به تأخیر) -> نباید رکورد تکراری بسازد
    res_bulk_update = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": attendance_setup["class_a1"].id,
            "date": "1404-07-15",
            "session_number": 1,
            "records": [
                {
                    "student_id": attendance_setup["st1"].id,
                    "status": "PRESENT",
                },
                {
                    "student_id": attendance_setup["st2"].id,
                    "status": "LATE",
                    "note": "با ۱۵ دقیقه تأخیر حاضر شد",
                },
            ],
        },
        format="json",
    )
    assert res_bulk_update.status_code == 200
    assert res_bulk_update.data["created_count"] == 0
    assert res_bulk_update.data["updated_count"] == 2
    assert AttendanceRecord.objects.for_school(attendance_setup["school_a"]).count() == 2

    # ۳. دریافت برگه‌ی حضور و غیاب کلاس (sheet)
    res_sheet = client.get(
        "/api/v1/attendance/sheet/",
        {
            "classroom": attendance_setup["class_a1"].id,
            "date": "1404-07-15",
            "session_number": 1,
        },
    )
    assert res_sheet.status_code == 200
    students_sheet = {s["student_id"]: s for s in res_sheet.data["students"]}
    assert students_sheet[attendance_setup["st2"].id]["status"] == "LATE"
    assert students_sheet[attendance_setup["st2"].id]["father_name"] == "رضا"


@pytest.mark.django_db
def test_teacher_restricted_to_own_classroom_and_session(attendance_setup):
    """
    معلم ۱ فقط می‌تواند برای کلاس خودش (هفتم الف) و زنگ خودش (زنگ ۱) حضور و غیاب ثبت کند.
    """
    client = APIClient()
    client.force_authenticate(user=attendance_setup["teacher_a1"])

    # تلاش معلم ۱ برای ثبت حضور و غیاب در کلاس «هفتم ب» -> 403
    res_wrong_class = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": attendance_setup["class_a2"].id,
            "date": "1404-07-15",
            "session_number": 1,
            "records": [{"student_id": attendance_setup["st_other_class"].id, "status": "PRESENT"}],
        },
        format="json",
    )
    assert res_wrong_class.status_code == 403

    # تلاش معلم ۱ برای ثبت حضور و غیاب در زنگ ۲ کلاس «هفتم الف» (که متعلق به معلم ۲ است) -> 403
    res_wrong_session = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": attendance_setup["class_a1"].id,
            "date": "1404-07-15",
            "session_number": 2,
            "records": [{"student_id": attendance_setup["st1"].id, "status": "PRESENT"}],
        },
        format="json",
    )
    assert res_wrong_session.status_code == 403


@pytest.mark.django_db
def test_parent_read_only_and_only_own_children_plus_school_isolation(attendance_setup):
    """
    - ولی فقط رکورد حضور و غیاب فرزند خودش (st1) را می‌بیند و رکورد هم‌کلاسی او (st2) را نمی‌بیند.
    - ولی اجازه ثبت یا ویرایش حضور و غیاب را ندارد (403).
    - ادمین مدرسه B هیچ دسترسی به حضور و غیاب مدرسه A ندارد.
    """
    client = APIClient()
    client.force_authenticate(user=attendance_setup["admin_a"])

    # ثبت روزانه (session_number=0) توسط کادر آموزشی با گزینه default_present_for_others=True
    res = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": attendance_setup["class_a1"].id,
            "date": "1404-07-16",
            "session_number": 0,
            "default_present_for_others": True,
            "records": [
                {
                    "student_id": attendance_setup["st1"].id,
                    "status": "EXCUSED_ABSENCE",
                    "note": "گواهی پزشکی",
                }
            ],
        },
        format="json",
    )
    assert res.status_code == 200
    assert res.data["created_count"] == 2  # st1 غایب موجه + st2 خودکار حاضر

    # ۱. بررسی دید ولی (PARENT)
    client.force_authenticate(user=attendance_setup["parent_a1"])
    res_parent = client.get("/api/v1/attendance/")
    assert res_parent.status_code == 200
    results = res_parent.data["results"]
    assert len(results) == 1
    assert results[0]["student"] == attendance_setup["st1"].id
    assert results[0]["status"] == "EXCUSED_ABSENCE"
    assert results[0]["date"] == "1404-07-16"

    # ولی نباید بتواند حضور و غیاب ثبت کند
    assert client.post("/api/v1/attendance/bulk-submit/", {}).status_code == 403

    # ۲. بررسی ایزولاسیون بین مدارس (ادمین مدرسه B)
    client.force_authenticate(user=attendance_setup["admin_b"])
    res_admin_b = client.get("/api/v1/attendance/")
    assert res_admin_b.status_code == 200
    assert res_admin_b.data["results"] == []