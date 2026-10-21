from rest_framework.routers import DefaultRouter
from apps.attendance.api.v1.views.attendance import (
    AttendanceAuditLogViewSet,
    AttendanceRecordViewSet,
)

router = DefaultRouter()
router.register(r"audit-logs", AttendanceAuditLogViewSet, basename="attendance-audit-log")
router.register(r"", AttendanceRecordViewSet, basename="attendance")

urlpatterns = router.urls