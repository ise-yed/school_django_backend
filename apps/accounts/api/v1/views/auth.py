from django.apps import apps
from django.db import transaction
from rest_framework import status, views
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.services import generate_and_send_otp, verify_otp_code
from apps.accounts.api.v1.serializers.auth import (
    OTPRequestSerializer,
    OTPVerifySerializer,
    StaffLoginSerializer,
    get_tokens_for_user,
)


class StaffLoginView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = StaffLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class ParentOTPRequestView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone_number"]
        national_code = serializer.validated_data.get("student_national_code")

        parent_exists = User.objects.filter(
            phone_number=phone,
            role=User.Role.PARENT,
            is_active=True,
            school__is_active=True,
        ).exists()

        student_exists = False
        if national_code and apps.is_installed("apps.students"):
            Student = apps.get_model("students", "Student")
            student_exists = Student.objects.filter(
                national_code=national_code,
                is_active=True,
                school__is_active=True,
            ).exists()

        if not parent_exists and not student_exists:
            raise AuthenticationFailed(
                "این شماره موبایل یا کد ملی دانش‌آموز در هیچ مدرسه‌ی فعالی یافت نشد."
            )

        generate_and_send_otp(phone)
        return Response({"detail": "کد تأیید ارسال شد."}, status=status.HTTP_200_OK)


class ParentOTPVerifyView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]
        national_code = serializer.validated_data.get("student_national_code")
        school_id = serializer.validated_data.get("school_id")

        verify_otp_code(phone, code)

        pending_verification_only = False

        if national_code and apps.is_installed("apps.students"):
            Student = apps.get_model("students", "Student")
            ParentStudentLink = apps.get_model("students", "ParentStudentLink")

            student_qs = Student.objects.filter(
                national_code=national_code,
                is_active=True,
                school__is_active=True,
            ).select_related("school")
            if school_id:
                student_qs = student_qs.filter(school_id=school_id)

            with transaction.atomic():
                for student in student_qs:
                    parent_user, _ = User.objects.get_or_create(
                        school=student.school,
                        phone_number=phone,
                        defaults={
                            "role": User.Role.PARENT,
                            "first_name": student.father_name,
                            "last_name": student.last_name,
                            "is_active": True,
                        },
                    )
                    existing_link = ParentStudentLink.objects.filter(
                        school=student.school,
                        parent_user=parent_user,
                        student=student,
                    ).first()

                    if existing_link is None:
                        # اتصال جدید فقط توسط کادر آموزشی یا اکسل مدرسه تأیید می‌شود؛ ثبت خودکار جدید همواره در انتظار تأیید می‌ماند
                        ParentStudentLink.objects.create(
                            school=student.school,
                            parent_user=parent_user,
                            student=student,
                            is_verified=False,
                        )
                        pending_verification_only = True
                    elif not existing_link.is_verified:
                        pending_verification_only = True

        parents = User.objects.filter(
            phone_number=phone,
            role=User.Role.PARENT,
            is_active=True,
            school__is_active=True,
        ).select_related("school")

        if school_id:
            parents = parents.filter(school_id=school_id)

        if not parents.exists():
            raise AuthenticationFailed("حساب ولی فعالی برای این شماره یافت نشد.")

        # اگر مدل دانش‌آموز نصب است، بررسی کن که ولی حداقل یک فرزند تأییدشده داشته باشد
        if apps.is_installed("apps.students"):
            ParentStudentLink = apps.get_model("students", "ParentStudentLink")
            if ParentStudentLink.objects.filter(parent_user__in=parents).exists():
                verified_parents = parents.filter(children_links__is_verified=True).distinct()
                if not verified_parents.exists():
                    raise PermissionDenied(
                        "درخواست اتصال شما ثبت شد و پس از تأیید کادر آموزشی مدرسه فعال خواهد شد."
                    )
                parents = verified_parents

        if pending_verification_only and not parents.exists():
            raise PermissionDenied(
                "درخواست اتصال شما ثبت شد و پس از تأیید کادر آموزشی مدرسه فعال خواهد شد."
            )

        if parents.count() > 1 and not school_id:
            return Response(
                {
                    "requires_school_selection": True,
                    "schools": [{"id": p.school.id, "name": p.school.name} for p in parents],
                },
                status=status.HTTP_200_OK,
            )

        parent_user = parents.first()
        return Response(get_tokens_for_user(parent_user), status=status.HTTP_200_OK)