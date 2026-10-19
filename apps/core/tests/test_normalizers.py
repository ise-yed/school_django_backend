import pytest
from apps.core.normalizers import normalize_and_validate_national_code


def test_national_code_zero_padding_and_checksum():
    assert normalize_and_validate_national_code("۷۹۰۷۵۶۱۴") == "0079075614"
    with pytest.raises(ValueError):
        normalize_and_validate_national_code("0079075615")