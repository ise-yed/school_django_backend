from apps.accounts.models import User
from apps.accounts.api.v1.serializers.staff import SchoolStaffSerializer
from apps.core.permissions import IsSchoolAdmin
from apps.core.viewsets import BaseViewSet


class SchoolStaffViewSet(BaseViewSet):
    """مدیریت معلمان و کادر آموزشی مدرسه توسط SCHOOL_ADMIN همان مدرسه"""
    queryset = User.objects.filter(role__in=[User.Role.SCHOOL_ADMIN, User.Role.TEACHER])
    serializer_class = SchoolStaffSerializer
    permission_classes = [IsSchoolAdmin]