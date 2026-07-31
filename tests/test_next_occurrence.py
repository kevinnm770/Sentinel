from __future__ import annotations

from datetime import time, timedelta

from services.training_service import _next_occurrence
from utils.time_utils import to_local, utc_now


def test_next_occurrence_is_always_in_the_future():
    for day in range(7):
        occurrence = _next_occurrence(day, time(12, 0))
        assert occurrence > utc_now()


def test_next_occurrence_falls_on_the_requested_weekday():
    for day in range(7):
        occurrence = _next_occurrence(day, time(12, 0))
        local = to_local(occurrence)
        assert local.weekday() == day


def test_next_occurrence_is_within_the_next_eight_days():
    # Nunca debería saltar más de una semana hacia adelante.
    now = utc_now()
    for day in range(7):
        occurrence = _next_occurrence(day, time(12, 0))
        assert occurrence <= now + timedelta(days=8)


def test_next_occurrence_is_naive_utc():
    # Toda la base de datos guarda datetimes sin tzinfo (ver utils/time_utils.py).
    occurrence = _next_occurrence(0, time(12, 0))
    assert occurrence.tzinfo is None
