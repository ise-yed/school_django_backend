import pytest
from apps.core.normalizers import (
    normalize_and_validate_national_code,
    normalize_for_search,
    normalize_persian_text,
)


def test_national_code_zero_padding_and_checksum():
    assert normalize_and_validate_national_code("۷۹۰۷۵۶۱۴") == "0079075614"
    with pytest.raises(ValueError):
        normalize_and_validate_national_code("0079075615")


def test_normalize_persian_text_preserves_alif_madd_and_zwnj():
    """
    بررسی اینکه normalize_persian_text برای ذخیره و نمایش:
    - کلاه «آ» را حذف نمی‌کند («آزاده» -> «آزاده»)
    - نیم‌فاصله را از بین نمی‌برد («می‌شود» -> «می‌شود»)
    - «ي» و «ك» عربی را به فارسی تبدیل می‌کند («علي كریمی» -> «علی کریمی»)
    - ارقام را تبدیل می‌کند و فاصله‌های اضافه را می‌زداید.
    """
    assert normalize_persian_text("آزاده") == "آزاده"
    assert normalize_persian_text("می\u200cشود") == "می\u200cشود"
    assert normalize_persian_text("  علي   كریمی  ") == "علی کریمی"
    assert normalize_persian_text("کلاس  ۱۲  ") == "کلاس 12"
    assert normalize_persian_text("بی\u200cانضباطی در آزمون") == "بی\u200cانضباطی در آزمون"


def test_normalize_for_search_aggressive_matching():
    """
    بررسی اینکه normalize_for_search به صورت تهاجمی برای ایندکس و جستجو عمل می‌کند:
    - «آ» به «ا» تبدیل می‌شود («آزاده» -> «ازاده»)
    - نیم‌فاصله به فاصله تبدیل می‌شود («می‌شود» -> «می شود»)
    - همزه‌ها و حروف عربی یکنواخت می‌شوند («رئیسی» -> «رییسی»، «فاطمة» -> «فاطمه»)
    - اعراب حذف می‌شوند («عَلِیّ» -> «علی»)
    """
    assert normalize_for_search("آزاده") == "ازاده"
    assert normalize_for_search("می\u200cشود") == "می شود"
    assert normalize_for_search("عَلِیّ") == "علی"
    assert normalize_for_search("فاطمة") == "فاطمه"
    assert normalize_for_search("رئیسی") == "رییسی"
    assert normalize_for_search("مسؤول") == "مسوول"