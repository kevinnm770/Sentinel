from __future__ import annotations

from datetime import date, time

import pytest

from utils.time_parsing import parse_date_ddmmyyyy, parse_time_hhmm


def test_parse_time_hhmm_valid():
    assert parse_time_hhmm("17:00") == time(17, 0)
    assert parse_time_hhmm("9:05") == time(9, 5)


@pytest.mark.parametrize("text", ["25:00", "17:60", "hola", "17-00", ""])
def test_parse_time_hhmm_invalid(text):
    with pytest.raises(ValueError):
        parse_time_hhmm(text)


def test_parse_date_ddmmyyyy_valid():
    assert parse_date_ddmmyyyy("15/08/2026") == date(2026, 8, 15)


@pytest.mark.parametrize("text", ["31/02/2026", "2026-08-15", "hola", "15/08/26", ""])
def test_parse_date_ddmmyyyy_invalid(text):
    with pytest.raises(ValueError):
        parse_date_ddmmyyyy(text)
