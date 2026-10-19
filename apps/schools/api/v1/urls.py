from rest_framework.routers import DefaultRouter
from apps.schools.api.v1.views.school import SchoolManagementViewSet

router = DefaultRouter()
router.register(r"manage", SchoolManagementViewSet, basename="school-manage")

urlpatterns = router.urls