import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord
from apps.core.models import AuditLog
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


@pytest.mark.django_db
def test_single_create_attendance_security_and_idor(attendance_setup):
    """
    بررسی امنیت ثبت تکی (POST /api/v1/attendance/):
    - جلوگیری از دور زدن دسترسی معلم به کلاس دیگر (403)
    - جلوگیری از دور زدن دسترسی معلم به زنگ دیگر (403)
    - جلوگیری از IDOR (دانش‌آموز یا کلاس متعلق به مدرسه دیگر) -> 400
    - جلوگیری از ثبت برای دانش‌آموزی که در آن کلاس ثبت‌نام نشده است -> 400
    - ثبت موفق برای کلاس و زنگ مجاز و تنظیم خودکار recorded_by
    - ممانعت از ثبت تکی توسط ولی (403)
    """
    client = APIClient()

    # ۱. ثبت موفق توسط معلم ۱ برای کلاس و زنگ مجاز خودش
    client.force_authenticate(user=attendance_setup["teacher_a1"])
    res_ok = client.post(
        "/api/v1/attendance/",
        {
            "student": attendance_setup["st1"].id,
            "classroom": attendance_setup["class_a1"].id,
            "date": "1404-07-20",
            "session_number": 1,
            "status": "PRESENT",
        },
        format="json",
    )
    assert res_ok.status_code == 201
    assert res_ok.data["recorded_by_name"] == "teacher_a1"
    record_id = res_ok.data["id"]
    record = AttendanceRecord.objects.get(id=record_id)
    assert record.recorded_by == attendance_setup["teacher_a1"]
    assert record.school == attendance_setup["school_a"]

    # ۲. تلاش معلم ۱ برای ثبت در کلاسی که به او تخصیص داده نشده (هفتم ب) -> 403
    res_unauthorized_class = client.post(
        "/api/v1/attendance/",
        {
            "student": attendance_setup["st_other_class"].id,
            "classroom": attendance_setup["class_a2"].id,
            "date": "1404-07-20",
            "session_number": 1,
            "status": "PRESENT",
        },
        format="json",
    )
    assert res_unauthorized_class.status_code == 403

    # ۳. تلاش معلم ۱ برای ثبت در زنگی که متعلق به او نیست (زنگ ۲ کلاس هفتم الف) -> 403
    res_unauthorized_session = client.post(
        "/api/v1/attendance/",
        {
            "student": attendance_setup["st2"].id,
            "classroom": attendance_setup["class_a1"].id,
            "date": "1404-07-20",
            "session_number": 2,
            "status": "PRESENT",
        },
        format="json",
    )
    assert res_unauthorized_session.status_code == 403

    # ۴. بررسی IDOR: ساخت دانش‌آموز و کلاس در مدرسه B
    school_b = attendance_setup["school_b"]
    year_b = AcademicYear.objects.create(
        school=school_b, title="۱۴۰۴-۱۴۰۵ ب", start_date="2025-09-23", end_date="2026-06-21"
    )
    grade_b = Grade.objects.create(school=school_b, title="هفتم ب", level_order=7)
    class_b = Classroom.objects.create(
        school=school_b, academic_year=year_b, grade=grade_b, name="کلاس ب"
    )
    st_b = Student.objects.create(
        school=school_b, first_name="علی", last_name="حسینی", national_code="9876543210"
    )

    # ۴.۱ تلاش برای ثبت با student مدرسه دیگر -> 400
    res_idor_student = client.post(
        "/api/v1/attendance/",
        {
            "student": st_b.id,
            "classroom": attendance_setup["class_a1"].id,
            "date": "1404-07-21",
            "session_number": 1,
            "status": "PRESENT",
        },
        format="json",
    )
    assert res_idor_student.status_code == 400
    assert "student" in res_idor_student.data

    # ۴.۲ تلاش برای ثبت با classroom مدرسه دیگر -> 400
    res_idor_class = client.post(
        "/api/v1/attendance/",
        {
            "student": attendance_setup["st1"].id,
            "classroom": class_b.id,
            "date": "1404-07-21",
            "session_number": 1,
            "status": "PRESENT",
        },
        format="json",
    )
    assert res_idor_class.status_code == 400
    assert "classroom" in res_idor_class.data

    # ۵. دانش‌آموز متعلق به مدرسه هست اما عضو این کلاس نیست -> 400
    res_wrong_enrollment = client.post(
        "/api/v1/attendance/",
        {
            "student": attendance_setup["st_other_class"].id,
            "classroom": attendance_setup["class_a1"].id,
            "date": "1404-07-22",
            "session_number": 1,
            "status": "PRESENT",
        },
        format="json",
    )
    assert res_wrong_enrollment.status_code == 400
    assert "student" in res_wrong_enrollment.data

    # ۶. تلاش ولی برای POST تکی -> 403
    client.force_authenticate(user=attendance_setup["parent_a1"])
    res_parent_post = client.post(
        "/api/v1/attendance/",
        {
            "student": attendance_setup["st1"].id,
            "classroom": attendance_setup["class_a1"].id,
            "date": "1404-07-20",
            "session_number": 1,
            "status": "PRESENT",
        },
        format="json",
    )
    assert res_parent_post.status_code == 403


@pytest.mark.django_db
def test_bulk_update_updates_updated_at_field(attendance_setup):
    """
    بررسی اینکه هنگام اجرای bulk_upsert_classroom_attendance برای رکوردهای موجود،
    فیلد updated_at با timezone.now() به‌روزرسانی می‌شود (زیرا bulk_update جنگو auto_now را خودکار آپدیت نمی‌کند).
    """
    from datetime import timedelta
    from django.utils import timezone
    from apps.attendance.services import bulk_upsert_classroom_attendance

    school = attendance_setup["school_a"]
    teacher = attendance_setup["teacher_a1"]
    classroom = attendance_setup["class_a1"]
    st1 = attendance_setup["st1"]

    past_time = timezone.now() - timedelta(hours=2)
    rec = AttendanceRecord.objects.create(
        school=school,
        student=st1,
        classroom=classroom,
        date=timezone.now().date(),
        session_number=1,
        status="PRESENT",
        recorded_by=teacher,
    )
    # تغییر دستی updated_at به ۲ ساعت قبل برای اطمینان از تغییر آن پس از bulk_update
    AttendanceRecord.objects.filter(pk=rec.pk).update(updated_at=past_time)
    rec.refresh_from_db()
    assert rec.updated_at == past_time

    bulk_upsert_classroom_attendance(
        school=school,
        user=teacher,
        classroom=classroom,
        date=timezone.now().date(),
        session_number=1,
        records=[{"student_id": st1.id, "status": "LATE", "note": "تاخیر"}],
    )

    rec.refresh_from_db()
    assert rec.status == "LATE"
    assert rec.updated_at > past_time


@pytest.mark.django_db
def test_teacher_day_of_week_and_session_attendance_permission(attendance_setup):
    """
    تست سناریوی کاربر:
    معلم شنبه زنگ ۲، چهارشنبه دو زنگ اول (زنگ ۱ و ۲)، سه‌شنبه زنگ ۳ می‌تواند حضور و غیاب کند.
    در سایر روزها یا سایر زنگ‌ها باید با خطای ۴۰۳ دسترسی رد شود.
    """
    school = attendance_setup["school_a"]
    class1 = attendance_setup["class_a1"]
    class2 = attendance_setup["class_a2"]
    st1 = attendance_setup["st1"]
    st2 = attendance_setup["st2"]
    st_other = attendance_setup["st_other_class"]

    # ساخت یک معلم جدید
    teacher = User.objects.create_user(
        username="teacher_schedule_test",
        password="password123",
        role=User.Role.TEACHER,
        school=school,
    )

    # شنبه (DayOfWeek.SATURDAY = 0) زنگ ۲ در class1
    TeacherAssignment.objects.create(
        school=school,
        teacher=teacher,
        classroom=class1,
        subject_name="ریاضی",
        day_of_week=TeacherAssignment.DayOfWeek.SATURDAY,
        session_number=2,
    )
    # چهارشنبه (DayOfWeek.WEDNESDAY = 4) زنگ ۱ در class1
    TeacherAssignment.objects.create(
        school=school,
        teacher=teacher,
        classroom=class1,
        subject_name="ریاضی",
        day_of_week=TeacherAssignment.DayOfWeek.WEDNESDAY,
        session_number=1,
    )
    # چهارشنبه (DayOfWeek.WEDNESDAY = 4) زنگ ۲ در class1
    TeacherAssignment.objects.create(
        school=school,
        teacher=teacher,
        classroom=class1,
        subject_name="هندسه",
        day_of_week=TeacherAssignment.DayOfWeek.WEDNESDAY,
        session_number=2,
    )
    # سه‌شنبه (DayOfWeek.TUESDAY = 3) زنگ ۳ در class2
    TeacherAssignment.objects.create(
        school=school,
        teacher=teacher,
        classroom=class2,
        subject_name="فیزیک",
        day_of_week=TeacherAssignment.DayOfWeek.TUESDAY,
        session_number=3,
    )

    client = APIClient()
    client.force_authenticate(user=teacher)

    # تاریخ‌ها در گاه‌شمار شمسی و میلادی:
    # 1405-08-02 = 2026-10-24 (شنبه)
    # 1405-08-03 = 2026-10-25 (یکشنبه)
    # 1405-08-05 = 2026-10-27 (سه‌شنبه)
    # 1405-08-06 = 2026-10-28 (چهارشنبه)

    # ۱. شنبه زنگ ۲ -> مجاز
    res_sat_s2 = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": class1.id,
            "date": "1405-08-02",
            "session_number": 2,
            "records": [{"student_id": st1.id, "status": "PRESENT"}],
        },
        format="json",
    )
    assert res_sat_s2.status_code == 200

    # ۲. شنبه زنگ ۱ -> غیرمجاز (۴۰۳)
    res_sat_s1 = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": class1.id,
            "date": "1405-08-02",
            "session_number": 1,
            "records": [{"student_id": st1.id, "status": "PRESENT"}],
        },
        format="json",
    )
    assert res_sat_s1.status_code == 403

    # ۳. چهارشنبه زنگ ۱ -> مجاز
    res_wed_s1 = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": class1.id,
            "date": "1405-08-06",
            "session_number": 1,
            "records": [{"student_id": st1.id, "status": "PRESENT"}],
        },
        format="json",
    )
    assert res_wed_s1.status_code == 200

    # ۴. چهارشنبه زنگ ۲ -> مجاز
    res_wed_s2 = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": class1.id,
            "date": "1405-08-06",
            "session_number": 2,
            "records": [{"student_id": st1.id, "status": "PRESENT"}],
        },
        format="json",
    )
    assert res_wed_s2.status_code == 200

    # ۵. چهارشنبه زنگ ۳ -> غیرمجاز (۴۰۳)
    res_wed_s3 = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": class1.id,
            "date": "1405-08-06",
            "session_number": 3,
            "records": [{"student_id": st1.id, "status": "PRESENT"}],
        },
        format="json",
    )
    assert res_wed_s3.status_code == 403

    # ۶. سه‌شنبه زنگ ۳ روی class2 -> مجاز
    res_tue_s3 = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": class2.id,
            "date": "1405-08-05",
            "session_number": 3,
            "records": [{"student_id": st_other.id, "status": "PRESENT"}],
        },
        format="json",
    )
    assert res_tue_s3.status_code == 200

    # ۷. سه‌شنبه زنگ ۱ روی class2 -> غیرمجاز (۴۰۳)
    res_tue_s1 = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": class2.id,
            "date": "1405-08-05",
            "session_number": 1,
            "records": [{"student_id": st_other.id, "status": "PRESENT"}],
        },
        format="json",
    )
    assert res_tue_s1.status_code == 403

    # ۸. یکشنبه در class1 -> غیرمجاز (۴۰۳ - هیچ تخصیصی در یکشنبه ندارد)
    res_sun = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": class1.id,
            "date": "1405-08-03",
            "session_number": 2,
            "records": [{"student_id": st1.id, "status": "PRESENT"}],
        },
        format="json",
    )
    assert res_sun.status_code == 403

    # ۹. ثبت تکی (POST /api/v1/attendance/) با تاریخ شنبه زنگ ۲ برای دانش‌آموز st2 -> مجاز (۲۰۱)
    res_single_valid = client.post(
        "/api/v1/attendance/",
        {
            "student": st2.id,
            "classroom": class1.id,
            "date": "1405-08-02",
            "session_number": 2,
            "status": "PRESENT",
        },
        format="json",
    )
    assert res_single_valid.status_code == 201

    # ۱۰. ثبت تکی شنبه زنگ ۱ برای st2 -> خطای ۴۰۳
    res_single_invalid = client.post(
        "/api/v1/attendance/",
        {
            "student": st2.id,
            "classroom": class1.id,
            "date": "1405-08-02",
            "session_number": 1,
            "status": "PRESENT",
        },
        format="json",
    )
    assert res_single_invalid.status_code == 403


@pytest.mark.django_db
def test_attendance_audit_log_recorded_on_create_update_and_bulk(attendance_setup):
    """
    بررسی اینکه هنگام ثبت، ویرایش تکی و ویرایش گروهی (bulk) حضور و غیاب،
    تاریخچه تغییرات در AuditLog با اکشن UPDATE و مقادیر old و new ذخیره می‌شود.
    """
    client = APIClient()
    teacher = attendance_setup["teacher_a1"]
    school = attendance_setup["school_a"]
    class1 = attendance_setup["class_a1"]
    st1 = attendance_setup["st1"]

    client.force_authenticate(user=teacher)

    # ۱. ثبت تکی اولیه
    res_create = client.post(
        "/api/v1/attendance/",
        {
            "student": st1.id,
            "classroom": class1.id,
            "date": "1404-07-20",
            "session_number": 1,
            "status": "PRESENT",
            "note": "حاضر در کلاس",
        },
        format="json",
    )
    assert res_create.status_code == 201
    rec_id = res_create.data["id"]

    # بررسی لاگ ایجاد
    create_log = AuditLog.objects.filter(
        school=school, target_model="AttendanceRecord", target_id=str(rec_id), action=AuditLog.Action.CREATE
    ).first()
    assert create_log is not None
    assert create_log.actor == teacher
    assert create_log.changes["status"]["new"] == "PRESENT"

    # ۲. ویرایش تکی رکورد (PATCH) و تغییر وضعیت به UNEXCUSED_ABSENCE
    res_patch = client.patch(
        f"/api/v1/attendance/{rec_id}/",
        {"status": "UNEXCUSED_ABSENCE", "note": "غیبت غیرموجه"},
        format="json",
    )
    assert res_patch.status_code == 200, res_patch.data

    # بررسی لاگ ویرایش
    update_log = AuditLog.objects.filter(
        school=school, target_model="AttendanceRecord", target_id=str(rec_id), action=AuditLog.Action.UPDATE
    ).first()
    assert update_log is not None
    assert update_log.actor == teacher
    assert update_log.changes["status"]["old"] == "PRESENT"
    assert update_log.changes["status"]["new"] == "UNEXCUSED_ABSENCE"
    assert update_log.changes["note"]["old"] == "حاضر در کلاس"
    assert update_log.changes["note"]["new"] == "غیبت غیرموجه"

    # ۳. بررسی تاریخچه از طریق اکشن /history/
    res_hist = client.get(f"/api/v1/attendance/{rec_id}/history/")
    assert res_hist.status_code == 200
    assert len(res_hist.data) >= 2
    actions = [item["action"] for item in res_hist.data]
    assert "UPDATE" in actions
    assert "CREATE" in actions

    # ۴. ویرایش گروهی از طریق bulk-submit و تغییر وضعیت مجدد به LATE
    res_bulk = client.post(
        "/api/v1/attendance/bulk-submit/",
        {
            "classroom_id": class1.id,
            "date": "1404-07-20",
            "session_number": 1,
            "records": [{"student_id": st1.id, "status": "LATE", "note": "تاخیر ۱۰ دقیقه‌ای"}],
        },
        format="json",
    )
    assert res_bulk.status_code == 200

    # بررسی لاگ ویرایش ناشی از bulk-submit
    latest_update = (
        AuditLog.objects.filter(
            school=school, target_model="AttendanceRecord", target_id=str(rec_id), action=AuditLog.Action.UPDATE
        )
        .order_by("-created_at", "-id")
        .first()
    )
    assert latest_update is not None
    assert latest_update.changes["status"]["old"] == "UNEXCUSED_ABSENCE"
    assert latest_update.changes["status"]["new"] == "LATE"

    # ۵. بررسی ویوست اختصاصی /api/v1/attendance/audit-logs/ (مخصوص IsSchoolAdmin)
    client.force_authenticate(user=teacher)
    assert client.get("/api/v1/attendance/audit-logs/").status_code == 403

    client.force_authenticate(user=attendance_setup["admin_a"])
    res_admin_logs = client.get("/api/v1/attendance/audit-logs/")
    assert res_admin_logs.status_code == 200
    assert len(res_admin_logs.data["results"]) >= 3


@pytest.mark.django_db
def test_single_attendance_atomic_transaction_rollback(attendance_setup):
    """
    بررسی اینکه در ثبت تکی حضور، ایجاد رکورد و AuditLog داخل یک transaction.atomic هستند؛
    در صورت بروز خطا در ثبت لاگ، رکورد حضور و غیاب نیز Rollback شده و ذخیره نمی‌شود.
    """
    from unittest.mock import patch
    from rest_framework.test import APIRequestFactory, force_authenticate
    from apps.attendance.api.v1.views.attendance import AttendanceRecordViewSet

    factory = APIRequestFactory()
    teacher = attendance_setup["teacher_a1"]
    class1 = attendance_setup["class_a1"]
    st1 = attendance_setup["st1"]

    initial_attendance_count = AttendanceRecord.objects.count()
    initial_audit_count = AuditLog.objects.count()

    request = factory.post(
        "/api/v1/attendance/",
        {
            "classroom": class1.id,
            "student": st1.id,
            "date": "1404-07-22",
            "session_number": 1,
            "status": "PRESENT",
        },
        format="json",
    )
    force_authenticate(request, user=teacher)
    view = AttendanceRecordViewSet.as_view({"post": "create"})

    with pytest.raises(RuntimeError):
        with patch("apps.core.models.AuditLog.objects.create", side_effect=RuntimeError("AuditLog DB failure")):
            view(request)

    # به دلیل atomic بودن تراکنش، رکورد حضور باید رول‌بک شده باشد
    assert AttendanceRecord.objects.count() == initial_attendance_count
    assert AuditLog.objects.count() == initial_audit_count
