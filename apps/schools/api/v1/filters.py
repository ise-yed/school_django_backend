import django_filters
from apps.schools.models import Classroom, TeacherAssignment


class ClassroomFilter(django_filters.FilterSet):
    academic_year = django_filters.NumberFilter(field_name="academic_year_id")
    grade = django_filters.NumberFilter(field_name="grade_id")
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Classroom
        fields = ["academic_year", "grade", "is_active"]


class TeacherAssignmentFilter(django_filters.FilterSet):
    classroom = django_filters.NumberFilter(field_name="classroom_id")
    teacher = django_filters.NumberFilter(field_name="teacher_id")
    day_of_week = django_filters.NumberFilter()
    session_number = django_filters.NumberFilter()

    class Meta:
        model = TeacherAssignment
        fields = ["classroom", "teacher", "day_of_week", "session_number"]
