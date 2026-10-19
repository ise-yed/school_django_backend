import datetime
import jdatetime
from rest_framework import serializers
from apps.core.normalizers import normalize_digits


class JalaliDateField(serializers.DateField):
    """
    ذخیره در دیتابیس به‌صورت datetime.date میلادی،
    نمایش و دریافت در API به فرمت شمسی YYYY/MM/DD یا YYYY-MM-DD.
    """

    def to_representation(self, value):
        if not value:
            return None
        if isinstance(value, datetime.datetime):
            value = value.date()
        j_date = jdatetime.date.fromgregorian(date=value)
        return j_date.strftime("%Y-%m-%d")

    def to_internal_value(self, data):
        if isinstance(data, datetime.date):
            return data
        clean = normalize_digits(str(data)).replace("/", "-")
        parts = clean.split("-")
        if len(parts) == 3:
            try:
                year, month, day = map(int, parts)
                # اگر سال شمسی ارسال شده باشد (مثلاً 1404)
                if 1300 <= year <= 1500:
                    return jdatetime.date(year, month, day).togregorian()
            except ValueError as e:
                raise serializers.ValidationError(f"تاریخ شمسی نامعتبر است: {e}")
        return super().to_internal_value(clean)