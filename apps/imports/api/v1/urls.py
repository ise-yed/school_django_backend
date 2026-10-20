from django.urls import include, path
from rest_framework.routers import DefaultRouter
from apps.imports.api.v1.views.import_excel import (
    ImportAnalyzeView,
    ImportCommitView,
    ImportLogViewSet,
    ImportMappingViewSet,
    ImportPreviewView,
    ImportSampleTemplateView,
)

router = DefaultRouter()
router.register(r"mappings", ImportMappingViewSet, basename="import-mapping")
router.register(r"logs", ImportLogViewSet, basename="import-log")

urlpatterns = [
    path("analyze/", ImportAnalyzeView.as_view(), name="import-analyze"),
    path("preview/", ImportPreviewView.as_view(), name="import-preview"),
    path("commit/", ImportCommitView.as_view(), name="import-commit"),
    path("template/", ImportSampleTemplateView.as_view(), name="import-template"),
    path("", include(router.urls)),
]