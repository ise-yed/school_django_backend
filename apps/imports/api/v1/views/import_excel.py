from django.http import HttpResponse
from rest_framework import status, views
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.core.permissions import IsSchoolAdmin
from apps.core.viewsets import BaseViewSet
from apps.imports.api.v1.serializers.import_excel import (
    AnalyzeImportSerializer,
    CommitImportSerializer,
    ImportLogSerializer,
    ImportMappingSerializer,
    PreviewImportSerializer,
)
from apps.imports.models import ImportLog, ImportMapping
from apps.imports.services import (
    analyze_excel_file,
    commit_import,
    generate_errors_workbook,
    generate_sample_template_workbook,
    preview_import,
)


class ImportAnalyzeView(views.APIView):
    """مرحله ۱: آپلود فایل اکسل و دریافت شیت‌ها، سرستون حدسی، نگاشت پیشنهادی، ۵ نمونه و کلاس پیشنهادی."""
    permission_classes = [IsSchoolAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = AnalyzeImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = analyze_excel_file(
            school=request.user.school,
            user=request.user,
            file_obj=serializer.validated_data["file"],
            sheet_name=serializer.validated_data.get("sheet_name") or None,
        )
        return Response(result, status=status.HTTP_200_OK)


class ImportPreviewView(views.APIView):
    """مرحله ۲: پیش‌نمایش ردیف‌های سالم، خطاها، دانش‌آموزان جدید/موجود و غایبین در فایل."""
    permission_classes = [IsSchoolAdmin]

    def post(self, request):
        serializer = PreviewImportSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = preview_import(
            import_log=data["import_log"],
            classroom=data["classroom"],
            mapping=data["mapping"],
            sheet_name=data.get("sheet_name") or None,
            header_row=data.get("header_row"),
            row_overrides=data.get("row_overrides"),
        )
        return Response(result, status=status.HTTP_200_OK)


class ImportCommitView(views.APIView):
    """مرحله ۳: ذخیره نهایی ردیف‌های سالم در یک تراکنش با bulk_create و bulk_update."""
    permission_classes = [IsSchoolAdmin]

    def post(self, request):
        serializer = CommitImportSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = commit_import(
            import_log=data["import_log"],
            classroom=data["classroom"],
            mapping=data["mapping"],
            allow_classroom_transfer=data["allow_classroom_transfer"],
            save_mapping=data["save_mapping"],
            mapping_name=data.get("mapping_name", "پیش‌فرض"),
            sheet_name=data.get("sheet_name") or None,
            header_row=data.get("header_row"),
            row_overrides=data.get("row_overrides"),
        )
        return Response(result, status=status.HTTP_200_OK)


class ImportSampleTemplateView(views.APIView):
    """دانلود قالب نمونه اکسل با فرمت متنی برای ستون کد ملی و موبایل ولی."""
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        content = generate_sample_template_workbook()
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="student_import_template.xlsx"'
        return response


class ImportMappingViewSet(BaseViewSet):
    queryset = ImportMapping.objects.all()
    serializer_class = ImportMappingSerializer
    permission_classes = [IsSchoolAdmin]


class ImportLogViewSet(BaseViewSet):
    queryset = ImportLog.objects.select_related("target_classroom")
    serializer_class = ImportLogSerializer
    permission_classes = [IsSchoolAdmin]
    http_method_names = ["get", "head", "options"]

    @action(detail=True, methods=["get"], url_path="errors-excel")
    def errors_excel(self, request, pk=None):
        import_log = self.get_object()
        content = generate_errors_workbook(import_log)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="import_errors_{import_log.id}.xlsx"'
        )
        return response