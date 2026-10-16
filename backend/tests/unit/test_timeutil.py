from datetime import UTC, datetime, timedelta

import pytest

from vedic_engine.models import InputError
from vedic_engine.timeutil import (
    AmbiguousTimeError,
    NonexistentTimeError,
    UnknownTimezoneError,
    jd_from_utc,
    to_local,
    to_utc,
    utc_from_jd,
)


def test_ist() -> None:
    assert to_utc(datetime(2000, 1, 1, 12, 0), "Asia/Kolkata") == datetime(
        2000, 1, 1, 6, 30, tzinfo=UTC
    )


def test_india_war_time() -> None:
    assert to_utc(datetime(1943, 6, 1, 12, 0), "Asia/Kolkata") == datetime(
        1943, 6, 1, 5, 30, tzinfo=UTC
    )


def test_india_lmt() -> None:
    utc = to_utc(datetime(1850, 1, 1, 12, 0), "Asia/Kolkata")
    assert to_local(utc, "Asia/Kolkata").utcoffset() == timedelta(hours=5, minutes=53, seconds=28)


def test_nonexistent_and_ambiguous() -> None:
    with pytest.raises(NonexistentTimeError):
        to_utc(datetime(2021, 3, 14, 2, 30), "America/New_York")
    with pytest.raises(AmbiguousTimeError):
        to_utc(datetime(2021, 11, 7, 1, 30), "America/New_York", fold=None)
    assert to_utc(datetime(2021, 11, 7, 1, 30), "America/New_York", fold=0) == datetime(
        2021, 11, 7, 5, 30, tzinfo=UTC
    )
    assert to_utc(datetime(2021, 11, 7, 1, 30), "America/New_York", fold=1) == datetime(
        2021, 11, 7, 6, 30, tzinfo=UTC
    )


def test_unknown_tz() -> None:
    with pytest.raises(UnknownTimezoneError):
        to_utc(datetime(2000, 1, 1), "Mars/Olympus")
    with pytest.raises(UnknownTimezoneError):
        to_utc(datetime(2000, 1, 1), "../etc/passwd")


def test_exceptions_are_input_errors() -> None:
    for exc in (NonexistentTimeError, AmbiguousTimeError, UnknownTimezoneError):
        assert issubclass(exc, InputError)


def test_rejects_aware_and_bad_fold() -> None:
    with pytest.raises(InputError):
        to_utc(datetime(2000, 1, 1, tzinfo=UTC), "Asia/Kolkata")
    with pytest.raises(InputError):
        to_utc(datetime(2000, 1, 1), "Asia/Kolkata", fold=2)


def test_jd_roundtrip() -> None:
    j2000 = datetime(2000, 1, 1, 12, 0, tzinfo=UTC)
    assert jd_from_utc(j2000) == 2451545.0
    for dt in (
        j2000,
        datetime(1850, 3, 7, 23, 59, 59, 123000, tzinfo=UTC),
        datetime(2399, 12, 31, 0, 0, 1, tzinfo=UTC),
    ):
        assert abs(utc_from_jd(jd_from_utc(dt)) - dt) <= timedelta(milliseconds=1)
    assert utc_from_jd(2451545.0).tzinfo is UTC


def test_jd_requires_aware() -> None:
    with pytest.raises(InputError):
        jd_from_utc(datetime(2000, 1, 1))
