import django_filters
from rest_framework.exceptions import ValidationError

from apps.core.fields import JalaliDateField
from apps.discipline.models import DisciplinaryRecord


class DisciplinaryRecordFilter(django_filters.FilterSet):
    classroom = django_filters.NumberFilter(field_name="classroom_id")
    student = django_filters.NumberFilter(field_name="student_id")
    category = django_filters.CharFilter()
    date = django_filters.CharFilter(method="filter_date")

    class Meta:
        model = DisciplinaryRecord
        fields = ["classroom", "student", "category", "date"]

    def filter_date(self, queryset, name, value):
        if not value:
            return queryset
        try:
            greg_date = JalaliDateField().to_internal_value(value)
            return queryset.filter(date=greg_date)
        except Exception:
            raise ValidationError({"date": "فرمت تاریخ نامعتبر است (مثال: ۱۴۰۴-۰۷-۱۵)."})
