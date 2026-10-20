from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.core.fields import JalaliDateField
from apps.core.models import AuditLog
from apps.discipline.models import DisciplinaryRecord
from apps.schools.models import Classroom, TeacherAssignment
from apps.students.models import Enrollment, Student


def get_client_ip(request) -> str | None:
    if not request:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def ensure_teacher_has_classroom_access(user: User, classroom: Classroom) -> None:
    if user.role == User.Role.SCHOOL_ADMIN:
        return
    if user.role != User.Role.TEACHER:
        raise PermissionDenied("شما مجوز ثبت یا تغییر پرونده انضباطی را ندارید.")

    has_access = TeacherAssignment.objects.for_school(user.school).filter(
        teacher=user, classroom=classroom
    ).exists()
    if not has_access:
        raise PermissionDenied("شما فقط به کلاس‌های تخصیص‌یافته به خودتان دسترسی دارید.")


def resolve_and_validate_student_classroom(
    school, student: Student, classroom: Classroom | None = None
) -> Classroom:
    """
    بررسی ثبت‌نام دانش‌آموز در کلاس انتخاب‌شده (یا یافتن خودکار کلاس فعال دانش‌آموز در سال جاری).
    """
    qs = Enrollment.objects.for_school(school).filter(student=student, is_active=True)
    if classroom is not None:
        if not qs.filter(classroom=classroom).exists():
            raise ValidationError(
                {"student": "این دانش‌آموز در کلاس انتخاب‌شده ثبت‌نام نشده است."}
            )
        return classroom

    current_enr = (
        qs.filter(academic_year__is_current=True).select_related("classroom").first()
        or qs.select_related("classroom").first()
    )
    if not current_enr:
        raise ValidationError(
            {"student": "این دانش‌آموز در هیچ کلاس فعالی ثبت‌نام نشده است."}
        )
    return current_enr.classroom


def _serialize_record_snapshot(record: DisciplinaryRecord) -> dict:
    return {
        "student_id": record.student_id,
        "classroom_id": record.classroom_id,
        "date": JalaliDateField().to_representation(record.date),
        "category": record.category,
        "description": record.description,
        "score_impact": record.score_impact,
    }


def create_disciplinary_record(
    *,
    school,
    user: User,
    validated_data: dict,
    ip_address: str | None = None,
) -> DisciplinaryRecord:
    student = validated_data["student"]
    classroom = resolve_and_validate_student_classroom(
        school=school,
        student=student,
        classroom=validated_data.get("classroom"),
    )
    ensure_teacher_has_classroom_access(user, classroom)

    with transaction.atomic():
        record = DisciplinaryRecord.objects.create(
            school=school,
            student=student,
            classroom=classroom,
            date=validated_data["date"],
            category=validated_data.get("category", DisciplinaryRecord.Category.BEHAVIORAL),
            description=validated_data["description"],
            score_impact=validated_data.get("score_impact", 0),
            created_by=user,
            updated_by=user,
        )
        snapshot = _serialize_record_snapshot(record)
        AuditLog.objects.create(
            school=school,
            actor=user,
            action=AuditLog.Action.CREATE,
            target_model="DisciplinaryRecord",
            target_id=str(record.id),
            changes={k: {"old": None, "new": v} for k, v in snapshot.items()},
            ip_address=ip_address,
        )
    return record


def update_disciplinary_record(
    *,
    record: DisciplinaryRecord,
    user: User,
    validated_data: dict,
    ip_address: str | None = None,
) -> DisciplinaryRecord:
    ensure_teacher_has_classroom_access(user, record.classroom)

    if "classroom" in validated_data and validated_data["classroom"] != record.classroom:
        new_classroom = resolve_and_validate_student_classroom(
            school=record.school,
            student=validated_data.get("student", record.student),
            classroom=validated_data["classroom"],
        )
        ensure_teacher_has_classroom_access(user, new_classroom)

    old_snapshot = _serialize_record_snapshot(record)

    with transaction.atomic():
        for field in ("student", "classroom", "date", "category", "description", "score_impact"):
            if field in validated_data:
                setattr(record, field, validated_data[field])
        record.updated_by = user
        record.save()

        new_snapshot = _serialize_record_snapshot(record)
        diff = {
            k: {"old": old_snapshot[k], "new": new_snapshot[k]}
            for k in old_snapshot
            if old_snapshot[k] != new_snapshot[k]
        }

        if diff:
            AuditLog.objects.create(
                school=record.school,
                actor=user,
                action=AuditLog.Action.UPDATE,
                target_model="DisciplinaryRecord",
                target_id=str(record.id),
                changes=diff,
                ip_address=ip_address,
            )
    return record


def delete_disciplinary_record(
    *,
    record: DisciplinaryRecord,
    user: User,
    ip_address: str | None = None,
) -> None:
    ensure_teacher_has_classroom_access(user, record.classroom)
    old_snapshot = _serialize_record_snapshot(record)
    record_id = str(record.id)
    school = record.school

    with transaction.atomic():
        record.delete()
        AuditLog.objects.create(
            school=school,
            actor=user,
            action=AuditLog.Action.DELETE,
            target_model="DisciplinaryRecord",
            target_id=record_id,
            changes={k: {"old": v, "new": None} for k, v in old_snapshot.items()},
            ip_address=ip_address,
        )