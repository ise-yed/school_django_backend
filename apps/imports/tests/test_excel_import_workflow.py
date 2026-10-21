import io
import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.schools.models import AcademicYear, Classroom, Grade, School
from apps.students.models import Enrollment, ParentStudentLink, Student


def make_excel_file(filename: str, rows: list[list], merge_top_row: bool = False):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "هفتم الف"
    for r in rows:
        ws.append(r)
    if merge_top_row:
        ws.merge_cells("A1:D1")
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return SimpleUploadedFile(
        filename,
        buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@pytest.fixture
def import_setup(db):
    school = School.objects.create(name="دبیرستان البرز", code="alborz")
    admin = User.objects.create_user(
        username="admin_a", password="pass1234", school=school, role=User.Role.SCHOOL_ADMIN
    )
    year = AcademicYear.objects.create(
        school=school,
        title="۱۴۰۴-۱۴۰۵",
        start_date="2025-09-23",
        end_date="2026-06-21",
        is_current=True,
    )
    grade7 = Grade.objects.create(school=school, title="هفتم", level_order=7)
    class_alef = Classroom.objects.create(
        school=school, academic_year=year, grade=grade7, name="هفتم الف"
    )
    class_be = Classroom.objects.create(
        school=school, academic_year=year, grade=grade7, name="هفتم ب"
    )

    # دانش‌آموزی که از قبل در «هفتم الف» است ولی در فایل اکسل جدید نیست (برای تست گزارش غایبین فایل)
    missing_student = Student.objects.create(
        school=school,
        first_name="پویا",
        last_name="نوری",
        father_name="جواد",
        national_code="0034567895",
    )
    Enrollment.objects.create(
        school=school, student=missing_student, academic_year=year, classroom=class_alef
    )

    # دانش‌آموزی که قبلاً در «هفتم ب» ثبت‌نام شده و حالا در فایل «هفتم الف» آمده است (تست جابه‌جایی کلاس)
    transfer_student = Student.objects.create(
        school=school,
        first_name="علی",
        last_name="محمدی",
        father_name="کاظم",
        national_code="0123456789",
    )
    Enrollment.objects.create(
        school=school, student=transfer_student, academic_year=year, classroom=class_be
    )

    return {
        "school": school,
        "admin": admin,
        "year": year,
        "class_alef": class_alef,
        "class_be": class_be,
        "missing_student": missing_student,
        "transfer_student": transfer_student,
    }


@pytest.mark.django_db
def test_three_step_import_analyze_preview_commit_and_idempotency(import_setup):
    client = APIClient()
    client.force_authenticate(user=import_setup["admin"])

    # ساخت فایل اکسل واقعی مدرسه:
    # ردیف ۱: عنوان ادغام‌شده بالای جدول
    # ردیف ۲: سرستون‌ها (اسم ترکیبی، نام پدر، کدملی، موبایل ولی)
    # ردیف ۳: دانش‌آموز جدید با نام دوکلمه‌ای «سید محمد حسینی» و کدملی ۸ رقمی عددی بدون صفر ابتدایی (12345679 -> 0012345679)
    # ردیف ۴: دانش‌آموز موجود در کلاس هفتم ب (0123456789)
    # ردیف ۵: ردیف خراب (کد ملی نامعتبر)
    excel_file = make_excel_file(
        "لیست_هفتم_الف.xlsx",
        rows=[
            ["لیست دانش‌آموزان کلاس هفتم الف", "", "", ""],
            ["اسم", "نام پدر", "کدملی", "موبایل ولی"],
            ["سید محمد حسینی", "علی", 12345679, "۰۹۱۲۱۱۱۲۲۳۳"],
            ["علی محمدی", "کاظم", "0123456789", ""],
            ["دانش آموز خراب", "حسن", "1111111111", ""],
        ],
        merge_top_row=True,
    )

    # ۱. مرحله Analyze
    res_analyze = client.post(
        "/api/v1/imports/analyze/",
        {"file": excel_file},
        format="multipart",
    )
    assert res_analyze.status_code == 200
    assert res_analyze.data["guessed_header_row"] == 2
    assert res_analyze.data["suggested_mapping"]["full_name"] == "اسم"
    assert res_analyze.data["suggested_mapping"]["split_full_name"] is True
    assert res_analyze.data["suggested_classroom"]["id"] == import_setup["class_alef"].id

    import_log_id = res_analyze.data["import_log_id"]
    mapping = res_analyze.data["suggested_mapping"]

    # ۲. مرحله Preview
    res_preview = client.post(
        "/api/v1/imports/preview/",
        {
            "import_log_id": import_log_id,
            "classroom_id": import_setup["class_alef"].id,
            "mapping": mapping,
        },
        format="json",
    )
    assert res_preview.status_code == 200
    assert res_preview.data["valid_count"] == 2
    assert res_preview.data["error_count"] == 1
    assert res_preview.data["errors"][0]["row_number"] == 5

    # بررسی پیش‌نمایش: نام سه کلمه‌ای «سید محمد حسینی» با قاعده کلمه آخر = فامیل تفکیک شده و دارای هشدار است
    new_st = res_preview.data["new_students"][0]
    assert new_st["first_name"] == "سید محمد"
    assert new_st["last_name"] == "حسینی"
    assert new_st["full_name"] == "سید محمد حسینی"
    assert new_st["national_code"] == "0012345679"
    assert new_st["has_warning"] is True
    assert res_preview.data["warning_count"] >= 1
    assert any("سید محمد حسینی" in w["student_name"] for w in res_preview.data["warnings"])

    # بررسی تشخیص نیاز به جابه‌جایی کلاس برای علی محمدی (دو کلمه - بدون هشدار)
    existing_st = res_preview.data["existing_students"][0]
    assert existing_st["first_name"] == "علی"
    assert existing_st["last_name"] == "محمدی"
    assert existing_st["has_warning"] is False
    assert existing_st["requires_classroom_transfer"] is True
    assert existing_st["previous_classroom_name"] == "هفتم ب"

    # بررسی گزارش دانش‌آموز غایب در فایل (پویا نوری) بدون حذف او
    missing_list = res_preview.data["missing_from_file_students"]
    assert len(missing_list) == 1
    assert missing_list[0]["national_code"] == "0034567895"

    # ۳. مرحله Commit (همراه با اصلاح دستی تفکیک نام سید محمد حسینی با row_overrides و بدون اجازه جابه‌جایی کلاس)
    res_commit_no_transfer = client.post(
        "/api/v1/imports/commit/",
        {
            "import_log_id": import_log_id,
            "classroom_id": import_setup["class_alef"].id,
            "mapping": mapping,
            "allow_classroom_transfer": False,
            "save_mapping": True,
            "row_overrides": {
                "3": {"first_name": "سید محمد", "last_name": "حسینی"}
            },
        },
        format="json",
    )
    assert res_commit_no_transfer.status_code == 200
    assert res_commit_no_transfer.data["created_count"] == 1
    assert res_commit_no_transfer.data["updated_count"] == 1
    assert res_commit_no_transfer.data["skipped_transfers_count"] == 1

    # کلاسِ علی محمدی نباید بدون تایید تغییر کرده باشد
    enr_transfer = Enrollment.objects.get(student=import_setup["transfer_student"])
    assert enr_transfer.classroom_id == import_setup["class_be"].id

    # بررسی ذخیره شدن full_name اصلی و نام/نام‌خانوادگی اصلاح‌شده روی مدل Student
    created_student = Student.objects.get(
        school=import_setup["school"], national_code="0012345679"
    )
    assert created_student.full_name == "سید محمد حسینی"
    assert created_student.first_name == "سید محمد"
    assert created_student.last_name == "حسینی"

    # بررسی ساخته شدن خودکار حساب ولی و ParentStudentLink برای ردیف دارای موبایل ولی
    assert ParentStudentLink.objects.filter(
        school=import_setup["school"],
        student=created_student,
        parent_user__phone_number="09121112233",
        is_verified=True,
    ).exists()

    # ۴. اجرای مجدد Commit با تایید جابه‌جایی کلاس (و تست Idempotency که رکورد تکراری نسازد)
    res_commit_with_transfer = client.post(
        "/api/v1/imports/commit/",
        {
            "import_log_id": import_log_id,
            "classroom_id": import_setup["class_alef"].id,
            "mapping": mapping,
            "allow_classroom_transfer": True,
        },
        format="json",
    )
    assert res_commit_with_transfer.status_code == 200
    assert res_commit_with_transfer.data["created_count"] == 0
    assert res_commit_with_transfer.data["updated_count"] == 2
    assert Student.objects.for_school(import_setup["school"]).count() == 3

    enr_transfer.refresh_from_db()
    assert enr_transfer.classroom_id == import_setup["class_alef"].id

    # ۵. تست دانلود فایل اکسل خطاها و قالب نمونه
    res_err_excel = client.get(f"/api/v1/imports/logs/{import_log_id}/errors-excel/")
    assert res_err_excel.status_code == 200

    res_template = client.get("/api/v1/imports/template/")
    assert res_template.status_code == 200