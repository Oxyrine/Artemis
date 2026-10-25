from datetime import date

import pytest

from artemis.money import format_inr, quarter_of, to_paise


def test_to_paise_no_float():
    assert to_paise("15,08,000.00") == 150_800_000 and to_paise("₹26,000") == 2_600_000
    assert to_paise("0.07") == 7
    for bad in (1.5, 15):
        with pytest.raises(TypeError):
            to_paise(bad)
    with pytest.raises(ValueError):
        to_paise("1.001")
    with pytest.raises(ValueError):
        to_paise("twelve")


def test_format_and_quarter():
    assert format_inr(150_800_000) == "15,08,000" and format_inr(2_600_000) == "26,000"
    assert format_inr(12_345) == "123.45" and format_inr(-100_000) == "-1,000"
    assert quarter_of(date(2026, 8, 1)) == 2 and quarter_of(date(2026, 4, 1)) == 1
    assert quarter_of(date(2026, 3, 31)) == 4
