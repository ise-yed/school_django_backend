from rest_framework.routers import DefaultRouter
from apps.discipline.api.v1.views.discipline import (
    DisciplinaryAuditLogViewSet,
    DisciplinaryRecordViewSet,
)

router = DefaultRouter()
router.register(r"audit-logs", DisciplinaryAuditLogViewSet, basename="discipline-audit-log")
router.register(r"", DisciplinaryRecordViewSet, basename="discipline")

urlpatterns = router.urls