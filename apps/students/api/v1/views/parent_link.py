from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.core.normalizers import normalize_and_validate_national_code, normalize_phone
from apps.core.permissions import IsSchoolAdmin
from apps.core.viewsets import BaseViewSet
from apps.students.api.v1.serializers.parent_link import (
    AssignParentByAdminSerializer,
    BulkAssignParentsSerializer,
    ChangeParentPhoneSerializer,
    ParentStudentLinkSerializer,
)
from apps.students.api.v1.filters import ParentStudentLinkFilter
from apps.students.models import ParentStudentLink, Student


class ParentStudentLinkViewSet(BaseViewSet):
    """
    مدیریت، ثبت، ویرایش و تأیید اتصال اولیا به دانش‌آموزان توسط کادر آموزشی مدرسه (SCHOOL_ADMIN).
    """
    queryset = ParentStudentLink.objects.select_related("parent_user", "student")
    serializer_class = ParentStudentLinkSerializer
    filterset_class = ParentStudentLinkFilter
    permission_classes = [IsSchoolAdmin]

    def get_queryset(self):
        return super().get_queryset().distinct()

    def create(self, request, *args, **kwargs):
        serializer = AssignParentByAdminSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        link = serializer.save()
        output = ParentStudentLinkSerializer(link).data
        return Response(output, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify_link(self, request, pk=None):
        """تأیید اتصال ولی به دانش‌آموز توسط کادر آموزشی."""
        link = self.get_object()
        link.is_verified = True
        link.save(update_fields=["is_verified", "updated_at"])
        return Response(ParentStudentLinkSerializer(link).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="unverify")
    def unverify_link(self, request, pk=None):
        """لغو تأیید اتصال ولی توسط کادر آموزشی."""
        link = self.get_object()
        link.is_verified = False
        link.save(update_fields=["is_verified", "updated_at"])
        return Response(ParentStudentLinkSerializer(link).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="change-phone")
    def change_phone(self, request, pk=None):
        """تغییر یا اصلاح شماره موبایل ولی برای یک دانش‌آموز توسط کادر آموزشی."""
        link = self.get_object()
        serializer = ChangeParentPhoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        school = self.get_school()
        new_phone = serializer.validated_data["phone_number"]
        new_relation = serializer.validated_data.get("relation", link.relation)

        with transaction.atomic():
            new_parent_user, _ = User.objects.get_or_create(
                school=school,
                phone_number=new_phone,
                role=User.Role.PARENT,
                defaults={
                    "first_name": link.student.father_name,
                    "last_name": link.student.last_name,
                    "is_active": True,
                },
            )
            # اگر قبلاً لینکی با کاربر جدید برای این دانش‌آموز وجود داشته، همان را آپدیت و لینک قبلی را حذف کن
            existing_other = (
                ParentStudentLink.objects.for_school(school)
                .filter(parent_user=new_parent_user, student=link.student)
                .exclude(pk=link.pk)
                .first()
            )
            if existing_other:
                link.delete()
                existing_other.relation = new_relation
                existing_other.is_verified = True
                existing_other.save(update_fields=["relation", "is_verified", "updated_at"])
                link = existing_other
            else:
                link.parent_user = new_parent_user
                link.relation = new_relation
                link.is_verified = True
                link.save(update_fields=["parent_user", "relation", "is_verified", "updated_at"])

        return Response(ParentStudentLinkSerializer(link).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="bulk-assign")
    def bulk_assign(self, request):
        """ثبت گروهی شماره موبایل اولیا بر اساس کد ملی دانش‌آموزان در یک درخواست."""
        serializer = BulkAssignParentsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = self.get_school()

        linked_count = 0
        errors = []

        with transaction.atomic():
            for idx, item in enumerate(serializer.validated_data["items"], start=1):
                try:
                    nc = normalize_and_validate_national_code(item["student_national_code"])
                    phone = normalize_phone(item["phone_number"])
                except ValueError as e:
                    errors.append({"index": idx, "error": str(e)})
                    continue

                student = Student.objects.for_school(school).filter(national_code=nc).first()
                if not student:
                    errors.append(
                        {"index": idx, "error": f"دانش‌آموزی با کد ملی {nc} در مدرسه یافت نشد."}
                    )
                    continue

                parent_user, _ = User.objects.get_or_create(
                    school=school,
                    phone_number=phone,
                    role=User.Role.PARENT,
                    defaults={
                        "first_name": student.father_name,
                        "last_name": student.last_name,
                        "is_active": True,
                    },
                )
                ParentStudentLink.objects.update_or_create(
                    school=school,
                    parent_user=parent_user,
                    student=student,
                    defaults={
                        "relation": item["relation"],
                        "is_verified": True,
                    },
                )
                linked_count += 1

        return Response(
            {"linked_count": linked_count, "error_count": len(errors), "errors": errors},
            status=status.HTTP_200_OK,
        )