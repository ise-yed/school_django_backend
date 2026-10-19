from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.accounts.api.v1.views.auth import (
    ParentOTPRequestView,
    ParentOTPVerifyView,
    StaffLoginView,
)
from apps.accounts.api.v1.views.staff import SchoolStaffViewSet

router = DefaultRouter()
router.register(r"staff", SchoolStaffViewSet, basename="school-staff")

urlpatterns = [
    path("auth/staff/login/", StaffLoginView.as_view(), name="staff-login"),
    path("auth/parent/otp/request/", ParentOTPRequestView.as_view(), name="parent-otp-request"),
    path("auth/parent/otp/verify/", ParentOTPVerifyView.as_view(), name="parent-otp-verify"),
    path("", include(router.urls)),
]