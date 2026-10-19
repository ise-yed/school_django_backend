from rest_framework import serializers
from apps.accounts.models import User
from apps.schools.models import School


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ["id", "name", "code", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class CreateSchoolAdminSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ["id", "username", "phone_number", "first_name", "last_name", "password"]
        read_only_fields = ["id"]