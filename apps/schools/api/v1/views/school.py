from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.accounts.models import User
from apps.core.permissions import IsSuperUser
from apps.schools.models import School
from apps.schools.api.v1.serializers.school import (
    CreateSchoolAdminSerializer,
    SchoolSerializer,
)


class SchoolManagementViewSet(viewsets.ModelViewSet):
    """مدیریت مدارس و ساخت ادمین هر مدرسه توسط SUPERUSER"""
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    permission_classes = [IsSuperUser]

    @action(detail=True, methods=["post"], url_path="create-admin")
    def create_admin(self, request, pk=None):
        school = self.get_object()
        serializer = CreateSchoolAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        admin_user = User.objects.create_user(
            username=data["username"],
            password=data["password"],
            phone_number=data.get("phone_number"),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            school=school,
            role=User.Role.SCHOOL_ADMIN,
        )
        return Response(
            {
                "id": admin_user.id,
                "username": admin_user.username,
                "school_id": school.id,
                "role": admin_user.role,
            },
            status=status.HTTP_201_CREATED,
        )