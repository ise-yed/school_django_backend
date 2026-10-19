from rest_framework.routers import DefaultRouter
from apps.schools.api.v1.views.academic import (
    AcademicYearViewSet,
    ClassroomViewSet,
    GradeViewSet,
)
from apps.schools.api.v1.views.assignment import TeacherAssignmentViewSet
from apps.schools.api.v1.views.school import SchoolManagementViewSet

router = DefaultRouter()
router.register(r"manage", SchoolManagementViewSet, basename="school-manage")
router.register(r"academic-years", AcademicYearViewSet, basename="academic-year")
router.register(r"grades", GradeViewSet, basename="grade")
router.register(r"classrooms", ClassroomViewSet, basename="classroom")
router.register(r"assignments", TeacherAssignmentViewSet, basename="teacher-assignment")

urlpatterns = router.urls