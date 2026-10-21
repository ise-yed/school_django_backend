import datetime
from django.db import models, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.attendance.models import AttendanceRecord
from apps.core.models import AuditLog
from apps.schools.models import Classroom, TeacherAssignment
from apps.students.models import Enrollment


def check_teacher_classroom_and_session_access(
    user: User,
    classroom: Classroom,
    session_number: int | None = None,
    date: datetime.date | None = None,
) -> None:
    """
    بررسی دسترسی معلم به کلاس، روز هفته و زنگ موردنظر:
    - ادمین مدرسه به تمام کلاس‌ها و زنگ‌های مدرسه خودش دسترسی دارد.
    - معلم فقط به کلاس‌های تخصیص‌یافته به خودش در روز و زنگ مربوطه دسترسی دارد.
    """
    if user.role == User.Role.SCHOOL_ADMIN:
        return

    if user.role != User.Role.TEACHER:
        raise PermissionDenied("شما مجوز دسترسی به این بخش را ندارید.")

    assignments = TeacherAssignment.objects.for_school(user.school).filter(
        teacher=user, classroom=classroom
    )
    if not assignments.exists():
        raise PermissionDenied("شما به این کلاس دسترسی ندارید.")

    if date is not None:
        # محاسبه روز هفته در گاه‌شمار خورشیدی (0=شنبه تا 6=جمعه)
        day_of_week = (date.weekday() + 2) % 7
        day_name = TeacherAssignment.DayOfWeek(day_of_week).label
        day_assignments = assignments.filter(
            models.Q(day_of_week=day_of_week) | models.Q(day_of_week__isnull=True)
        )
        if not day_assignments.exists():
            raise PermissionDenied(f"شما در روز {day_name} در این کلاس تخصیصی ندارید.")
        assignments = day_assignments

    if session_number and session_number > 0:
        if not assignments.filter(session_number=session_number).exists():
            if date is not None:
                day_of_week = (date.weekday() + 2) % 7
                day_name = TeacherAssignment.DayOfWeek(day_of_week).label
                raise PermissionDenied(
                    f"زنگ شماره {session_number} در روز {day_name} در این کلاس به شما تخصیص داده نشده است."
                )
            raise PermissionDenied(
                f"زنگ شماره {session_number} در این کلاس به شما تخصیص داده نشده است."
            )


def bulk_upsert_classroom_attendance(
    *,
    school,
    user: User,
    classroom: Classroom,
    date: datetime.date,
    session_number: int,
    records: list[dict],
    default_present_for_others: bool = False,
    ip_address: str | None = None,
) -> dict:
    """
    ثبت یا ویرایش یک‌جای حضور و غیاب کل دانش‌آموزان یک کلاس در یک تراکنش:
    - بدون نیاز به ارسال درخواست جداگانه برای هر دانش‌آموز
    - استفاده از bulk_create و bulk_update برای جلوگیری از N+1 و جلوگیری از ثبت تکراری
    - ثبت تاریخچه تغییرات در AuditLog
    """
    check_teacher_classroom_and_session_access(user, classroom, session_number, date=date)

    enrolled_student_ids = set(
        Enrollment.objects.for_school(school)
        .filter(classroom=classroom, is_active=True)
        .values_list("student_id", flat=True)
    )

    if not enrolled_student_ids:
        raise ValidationError("هیچ دانش‌آموز فعالی در این کلاس ثبت‌نام نشده است.")

    incoming_map: dict[int, dict] = {}
    for item in records:
        st_id = item["student_id"]
        if st_id not in enrolled_student_ids:
            raise ValidationError(
                {"records": f"دانش‌آموز با شناسه {st_id} عضو این کلاس نیست."}
            )
        if st_id in incoming_map:
            raise ValidationError(
                {"records": f"دانش‌آموز با شناسه {st_id} بیش از یک‌بار در لیست ارسال شده است."}
            )
        incoming_map[st_id] = {
            "status": item["status"],
            "note": item.get("note", "") or "",
        }

    # اگر معلم فقط غایبین/تاخیری‌ها را فرستاده باشد و بخواهد بقیه خودکار حاضر رد شوند
    if default_present_for_others:
        for st_id in enrolled_student_ids:
            if st_id not in incoming_map:
                incoming_map[st_id] = {
                    "status": AttendanceRecord.Status.PRESENT,
                    "note": "",
                }

    target_student_ids = list(incoming_map.keys())

    with transaction.atomic():
        existing_records = {
            rec.student_id: rec
            for rec in AttendanceRecord.objects.for_school(school)
            .select_for_update()
            .filter(
                student_id__in=target_student_ids,
                date=date,
                session_number=session_number,
            )
        }

        now = timezone.now()
        to_create = []
        to_update = []
        audit_logs_to_create = []

        for st_id, payload in incoming_map.items():
            if st_id in existing_records:
                rec = existing_records[st_id]
                old_status = rec.status
                old_note = rec.note or ""
                new_status = payload["status"]
                new_note = payload["note"] or ""

                diff = {}
                if old_status != new_status:
                    diff["status"] = {"old": old_status, "new": new_status}
                if old_note != new_note:
                    diff["note"] = {"old": old_note, "new": new_note}

                rec.classroom = classroom
                rec.status = new_status
                rec.note = new_note
                rec.recorded_by = user
                rec.updated_at = now
                to_update.append(rec)

                if diff:
                    audit_logs_to_create.append(
                        AuditLog(
                            school=school,
                            actor=user,
                            action=AuditLog.Action.UPDATE,
                            target_model="AttendanceRecord",
                            target_id=str(rec.id),
                            changes=diff,
                            ip_address=ip_address,
                        )
                    )
            else:
                to_create.append(
                    AttendanceRecord(
                        school=school,
                        student_id=st_id,
                        classroom=classroom,
                        date=date,
                        session_number=session_number,
                        status=payload["status"],
                        note=payload["note"],
                        recorded_by=user,
                    )
                )

        if to_create:
            created_records = AttendanceRecord.objects.bulk_create(to_create)
            for new_rec in created_records:
                audit_logs_to_create.append(
                    AuditLog(
                        school=school,
                        actor=user,
                        action=AuditLog.Action.CREATE,
                        target_model="AttendanceRecord",
                        target_id=str(new_rec.id),
                        changes={
                            "status": {"old": None, "new": new_rec.status},
                            "note": {"old": None, "new": new_rec.note},
                            "student_id": {"old": None, "new": new_rec.student_id},
                            "classroom_id": {"old": None, "new": new_rec.classroom_id},
                            "date": {"old": None, "new": str(new_rec.date)},
                            "session_number": {"old": None, "new": new_rec.session_number},
                        },
                        ip_address=ip_address,
                    )
                )

        if to_update:
            AttendanceRecord.objects.bulk_update(
                to_update,
                ["classroom", "status", "note", "recorded_by", "updated_at"],
            )

        if audit_logs_to_create:
            AuditLog.objects.bulk_create(audit_logs_to_create)

    return {
        "classroom_id": classroom.id,
        "session_number": session_number,
        "total_submitted": len(target_student_ids),
        "created_count": len(to_create),
        "updated_count": len(to_update),
    }


def get_classroom_attendance_sheet(
    *,
    school,
    user: User,
    classroom: Classroom,
    date: datetime.date,
    session_number: int,
) -> list[dict]:
    """
    دریافت لیست کامل دانش‌آموزان یک کلاس به همراه وضعیت حضور و غیاب آن‌ها در تاریخ و زنگ مشخص‌شده.
    """
    check_teacher_classroom_and_session_access(user, classroom, session_number, date=date)

    enrollments = (
        Enrollment.objects.for_school(school)
        .filter(classroom=classroom, is_active=True)
        .select_related("student")
        .order_by("student__last_name", "student__first_name", "student_id")
    )

    records_map = {
        rec.student_id: rec
        for rec in AttendanceRecord.objects.for_school(school).filter(
            classroom=classroom,
            date=date,
            session_number=session_number,
        )
    }

    sheet = []
    for enr in enrollments:
        st = enr.student
        rec = records_map.get(st.id)
        sheet.append(
            {
                "student_id": st.id,
                "first_name": st.first_name,
                "last_name": st.last_name,
                "father_name": st.father_name,
                "national_code": st.national_code,
                "attendance_id": rec.id if rec else None,
                "status": rec.status if rec else None,
                "note": rec.note if rec else "",
            }
        )
    return sheet