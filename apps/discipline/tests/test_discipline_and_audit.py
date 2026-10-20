import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.schools.models import AcademicYear, Classroom, Grade, School, TeacherAssignment
from apps.students.models import Enrollment, ParentStudentLink, Student


@pytest.fixture
def discipline_setup(db):
    school_a = School.objects.create(name="دبیرستان البرز", code="alborz")
    school_b = School.objects.create(name="دبیرستان علامه", code="allameh")

    admin_a = User.objects.create_user(
        username="admin_a",
        password="pass1234",
        first_name="کاوه",
        last_name="مدیری",
        school=school_a,
        role=User.Role.SCHOOL_ADMIN,
    )
    admin_b = User.objects.create_user(
        username="admin_b",
        password="pass1234",
        school=school_b,
        role=User.Role.SCHOOL_ADMIN,
    )
    teacher_a1 = User.objects.create_user(
        username="teacher_a1",
        password="pass1234",
        first_name="رضا",
        last_name="معلمی",
        school=school_a,
        role=User.Role.TEACHER,
    )
    parent_a1 = User.objects.create_user(
        phone_number="09121112233",
        school=school_a,
        role=User.Role.PARENT,
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

    # معلم ۱ فقط به کلاس «هفتم الف» دسترسی دارد
    TeacherAssignment.objects.create(
        school=school_a,
        teacher=teacher_a1,
        classroom=class_a1,
        subject_name="ریاضی",
        session_number=1,
    )

    st1 = Student.objects.create(
        school=school_a,
        first_name="امیر",
        last_name="رضایی",
        father_name="حسن",
        national_code="0012345679",
    )
    st2_same_class = Student.objects.create(
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

    Enrollment.objects.create(
        school=school_a, student=st1, academic_year=year_a, classroom=class_a1
    )
    Enrollment.objects.create(
        school=school_a, student=st2_same_class, academic_year=year_a, classroom=class_a1
    )
    Enrollment.objects.create(
        school=school_a, student=st_other_class, academic_year=year_a, classroom=class_a2
    )

    ParentStudentLink.objects.create(
        school=school_a, parent_user=parent_a1, student=st1, is_verified=True
    )

    return {
        "school_a": school_a,
        "school_b": school_b,
        "admin_a": admin_a,
        "admin_b": admin_b,
        "teacher_a1": teacher_a1,
        "parent_a1": parent_a1,
        "class_a1": class_a1,
        "class_a2": class_a2,
        "st1": st1,
        "st2_same_class": st2_same_class,
        "st_other_class": st_other_class,
    }


@pytest.mark.django_db
def test_create_update_discipline_and_audit_log_tracking(discipline_setup):
    """
    ثبت مورد انضباطی توسط معلم و ویرایش آن توسط ادمین مدرسه + بررسی ثبت دقیق تغییرات در AuditLog.
    """
    client = APIClient()
    client.force_authenticate(user=discipline_setup["teacher_a1"])

    # ۱. ثبت مورد انضباطی توسط معلم کلاس هفتم الف (بدون ارسال classroom؛ تشخیص خودکار کلاس فعال)
    res_create = client.post(
        "/api/v1/discipline/",
        {
            "student": discipline_setup["st1"].id,
            "date": "۱۴۰۴/۰۷/۲۰",
            "category": "BEHAVIORAL",
            "description": "صحبت کردن مکرر هنگام تدریس",
            "score_impact": -1,
        },
        format="json",
    )
    assert res_create.status_code == 201
    record_id = res_create.data["id"]
    assert res_create.data["classroom"] == discipline_setup["class_a1"].id
    assert res_create.data["date"] == "1404-07-20"
    assert res_create.data["created_by_name"] == "رضا معلمی"

    # ۲. ویرایش همان رکورد توسط کادر آموزشی مدرسه
    client.force_authenticate(user=discipline_setup["admin_a"])
    res_patch = client.patch(
        f"/api/v1/discipline/{record_id}/",
        {
            "description": "صحبت کردن در کلاس (پس از تعهد دانش‌آموز بخشیده شد)",
            "score_impact": 0,
        },
        format="json",
    )
    assert res_patch.status_code == 200
    assert res_patch.data["updated_by_name"] == "کاوه مدیری"

    # ۳. بررسی تاریخچه تغییرات (AuditLog) از طریق اکشن /history/
    res_history = client.get(f"/api/v1/discipline/{record_id}/history/")
    assert res_history.status_code == 200
    assert len(res_history.data) == 2

    latest_log = res_history.data[0]
    first_log = res_history.data[1]

    assert latest_log["action"] == AuditLog.Action.UPDATE
    assert latest_log["actor_name"] == "کاوه مدیری"
    assert latest_log["changes"]["score_impact"] == {"old": -1, "new": 0}
    assert latest_log["changes"]["description"]["old"] == "صحبت کردن مکرر هنگام تدریس"

    assert first_log["action"] == AuditLog.Action.CREATE
    assert first_log["actor_name"] == "رضا معلمی"


@pytest.mark.django_db
def test_teacher_cannot_access_or_create_discipline_for_other_classroom(discipline_setup):
    """معلم ۱ فقط مجاز به ثبت و مشاهده پرونده انضباطی کلاس خودش (هفتم الف) است."""
    client = APIClient()

    # ادمین یک مورد انضباطی برای دانش‌آموز کلاس «هفتم ب» ثبت می‌کند
    client.force_authenticate(user=discipline_setup["admin_a"])
    res_admin = client.post(
        "/api/v1/discipline/",
        {
            "student": discipline_setup["st_other_class"].id,
            "date": "1404-07-21",
            "category": "TARDINESS",
            "description": "تاخیر صبحگاهی",
        },
        format="json",
    )
    assert res_admin.status_code == 201
    other_record_id = res_admin.data["id"]

    # معلم ۱ (معلم هفتم الف) نباید بتواند برای دانش‌آموز هفتم ب مورد انضباطی ثبت کند -> 403
    client.force_authenticate(user=discipline_setup["teacher_a1"])
    res_forbidden_create = client.post(
        "/api/v1/discipline/",
        {
            "student": discipline_setup["st_other_class"].id,
            "date": "1404-07-21",
            "category": "BEHAVIORAL",
            "description": "تلاش غیرمجاز",
        },
        format="json",
    )
    assert res_forbidden_create.status_code == 403

    # معلم ۱ نباید پرونده دانش‌آموز هفتم ب را ببیند یا ویرایش کند -> 404
    assert client.get(f"/api/v1/discipline/{other_record_id}/").status_code == 404
    assert (
        client.patch(
            f"/api/v1/discipline/{other_record_id}/", {"description": "تغییر"}
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_parent_read_only_own_child_and_cross_school_isolation(discipline_setup):
    """
    - ولی فقط پرونده انضباطی فرزند خودش (st1) را می‌بیند و پرونده هم‌کلاسی فرزندش (st2) را نمی‌بیند.
    - ولی اجازه ثبت، ویرایش یا مشاهده AuditLog را ندارد.
    - ادمین مدرسه B هیچ دسترسی به پرونده‌ها یا لاگ‌های مدرسه A ندارد.
    """
    client = APIClient()
    client.force_authenticate(user=discipline_setup["admin_a"])

    # ثبت مورد برای فرزندِ ولی (st1) و هم‌کلاسی‌اش (st2)
    res1 = client.post(
        "/api/v1/discipline/",
        {
            "student": discipline_setup["st1"].id,
            "date": "1404-07-22",
            "category": "MERIT",
            "description": "کسب رتبه اول المپیاد ریاضی مدرسه",
            "score_impact": 2,
        },
        format="json",
    )
    rec1_id = res1.data["id"]

    res2 = client.post(
        "/api/v1/discipline/",
        {
            "student": discipline_setup["st2_same_class"].id,
            "date": "1404-07-22",
            "category": "BEHAVIORAL",
            "description": "مورد مربوط به دانش‌آموز دیگر",
        },
        format="json",
    )
    rec2_id = res2.data["id"]

    # ۱. بررسی دسترسی ولی (PARENT)
    client.force_authenticate(user=discipline_setup["parent_a1"])
    res_parent_list = client.get("/api/v1/discipline/")
    assert res_parent_list.status_code == 200
    returned_ids = [r["id"] for r in res_parent_list.data["results"]]
    assert returned_ids == [rec1_id]

    assert client.get(f"/api/v1/discipline/{rec2_id}/").status_code == 404
    assert client.post("/api/v1/discipline/", {}).status_code == 403
    assert client.get(f"/api/v1/discipline/{rec1_id}/history/").status_code == 403

    # ۲. بررسی ایزولاسیون بین مدارس (ادمین مدرسه B)
    client.force_authenticate(user=discipline_setup["admin_b"])
    assert client.get("/api/v1/discipline/").data["results"] == []
    assert client.get(f"/api/v1/discipline/{rec1_id}/").status_code == 404
    assert client.get("/api/v1/discipline/audit-logs/").data["results"] == []