from rest_framework.routers import DefaultRouter
from apps.attendance.api.v1.views.attendance import AttendanceRecordViewSet

router = DefaultRouter()
router.register(r"", AttendanceRecordViewSet, basename="attendance")

urlpatterns = router.urls