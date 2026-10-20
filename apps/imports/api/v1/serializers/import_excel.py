from rest_framework import serializers
from apps.imports.models import ImportLog, ImportMapping
from apps.schools.models import Classroom


class AnalyzeImportSerializer(serializers.Serializer):
    file = serializers.FileField()
    sheet_name = serializers.CharField(required=False, allow_blank=True)


class ColumnMappingConfigSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    full_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    father_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    national_code = serializers.CharField(required=True)
    parent_phone = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    student_code = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    split_full_name = serializers.BooleanField(default=False)

    def validate(self, attrs):
        has_full = bool(attrs.get("full_name"))
        has_separate = bool(attrs.get("first_name") and attrs.get("last_name"))
        if not has_full and not has_separate:
            raise serializers.ValidationError(
                "باید یا ستون ترکیبی «اسم» (full_name) یا هر دو ستون «نام» و «نام خانوادگی» مشخص شوند."
            )
        return attrs


class PreviewImportSerializer(serializers.Serializer):
    import_log_id = serializers.IntegerField()
    classroom_id = serializers.IntegerField()
    mapping = ColumnMappingConfigSerializer()
    sheet_name = serializers.CharField(required=False, allow_blank=True)
    header_row = serializers.IntegerField(required=False, min_value=1)
    row_overrides = serializers.DictField(required=False)

    def validate(self, attrs):
        request = self.context["request"]
        school = request.user.school

        try:
            attrs["import_log"] = ImportLog.objects.for_school(school).get(
                pk=attrs["import_log_id"]
            )
        except ImportLog.DoesNotExist:
            raise serializers.ValidationError({"import_log_id": "لاگ ایمپورت در مدرسه‌ی شما یافت نشد."})

        try:
            attrs["classroom"] = Classroom.objects.for_school(school).select_related(
                "academic_year"
            ).get(pk=attrs["classroom_id"])
        except Classroom.DoesNotExist:
            raise serializers.ValidationError({"classroom_id": "کلاس مقصد در مدرسه‌ی شما یافت نشد."})

        return attrs


class CommitImportSerializer(PreviewImportSerializer):
    allow_classroom_transfer = serializers.BooleanField(default=False)
    save_mapping = serializers.BooleanField(default=False)
    mapping_name = serializers.CharField(required=False, default="پیش‌فرض")


class ImportMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportMapping
        fields = ["id", "name", "mapping_config", "updated_at"]
        read_only_fields = ["id", "updated_at"]


class ImportLogSerializer(serializers.ModelSerializer):
    classroom_name = serializers.CharField(source="target_classroom.name", read_only=True)

    class Meta:
        model = ImportLog
        fields = [
            "id",
            "original_filename",
            "target_classroom",
            "classroom_name",
            "status",
            "total_rows",
            "created_count",
            "updated_count",
            "error_count",
            "errors_detail",
            "created_at",
        ]
        read_only_fields = fields