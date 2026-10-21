import django_filters
from apps.students.models import Enrollment, ParentStudentLink, Student


class StudentFilter(django_filters.FilterSet):
    classroom = django_filters.NumberFilter(method="filter_classroom")
    is_active = django_filters.BooleanFilter()
    national_code = django_filters.CharFilter(lookup_expr="icontains")
    first_name = django_filters.CharFilter(lookup_expr="icontains")
    last_name = django_filters.CharFilter(lookup_expr="icontains")
    father_name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Student
        fields = [
            "classroom",
            "is_active",
            "national_code",
            "first_name",
            "last_name",
            "father_name",
        ]

    def filter_classroom(self, queryset, name, value):
        return queryset.filter(
            enrollments__classroom_id=value,
            enrollments__is_active=True,
        )


class EnrollmentFilter(django_filters.FilterSet):
    classroom = django_filters.NumberFilter(field_name="classroom_id")
    academic_year = django_filters.NumberFilter(field_name="academic_year_id")
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Enrollment
        fields = ["classroom", "academic_year", "is_active"]


class ParentStudentLinkFilter(django_filters.FilterSet):
    student = django_filters.NumberFilter(field_name="student_id")
    classroom = django_filters.NumberFilter(method="filter_classroom")
    is_verified = django_filters.BooleanFilter()
    national_code = django_filters.CharFilter(
        field_name="student__national_code", lookup_expr="icontains"
    )
    phone_number = django_filters.CharFilter(
        field_name="parent_user__phone_number", lookup_expr="icontains"
    )

    class Meta:
        model = ParentStudentLink
        fields = [
            "student",
            "classroom",
            "is_verified",
            "national_code",
            "phone_number",
        ]

    def filter_classroom(self, queryset, name, value):
        return queryset.filter(
            student__enrollments__classroom_id=value,
            student__enrollments__is_active=True,
        )
