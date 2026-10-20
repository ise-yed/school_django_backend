from rest_framework.routers import DefaultRouter
from apps.students.api.v1.views.parent_link import ParentStudentLinkViewSet
from apps.students.api.v1.views.student import EnrollmentViewSet, StudentViewSet

router = DefaultRouter()
router.register(r"enrollments", EnrollmentViewSet, basename="enrollment")
router.register(r"parent-links", ParentStudentLinkViewSet, basename="parent-link")
router.register(r"", StudentViewSet, basename="student")

urlpatterns = router.urls