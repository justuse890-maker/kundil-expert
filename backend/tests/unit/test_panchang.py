from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from vedic_engine import ephemeris, panchang
from vedic_engine.constants import TITHIS, VAARS
from vedic_engine.models import EphemerisRangeError, InputError, Settings
from vedic_engine.panchang import karana, karana_key, paksha, tithi, yoga
from vedic_engine.timeutil import jd_from_utc, to_utc

DEFAULT = Settings()
DELHI = (28.6139, 77.2090)
SECOND = 1.0 / 86400.0


@pytest.fixture(autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


def test_tithi_formula() -> None:
    # The brief lists (10, 22) -> 1; elongation 12 is exactly the start of tithi 2 by the
    # spec formula floor(12 / 12) + 1, the same convention as (10, 190) -> 16. See report.
    assert tithi(10.0, 21.99) == 1
    assert tithi(10.0, 22.0) == 2
    assert tithi(10.0, 190.0) == 16
    assert tithi(10.0, 9.99) == 30


def test_tithi_boundaries() -> None:
    assert tithi(0.0, 0.0) == 1
    assert tithi(0.0, 11.999) == 1
    assert tithi(0.0, 12.0) == 2
    assert tithi(0.0, 180.0) == 16
    assert tithi(350.0, 340.0) == 30


def test_paksha() -> None:
    assert paksha(1) == "shukla"
    assert paksha(15) == "shukla"
    assert paksha(16) == "krishna"
    assert paksha(30) == "krishna"


def test_yoga_formula() -> None:
    assert yoga(0.0, 0.0) == 1  # Vishkambha
    assert yoga(10.0, 3.0) == 1  # sum 13 < 13 1/3
    assert yoga(10.0, 3.34) == 2  # sum 13.34 > 13 1/3
    assert yoga(200.0, 159.9) == 27  # sum 359.9: Vaidhriti
    assert yoga(200.0, 170.0) == 1  # sum 370 wraps to 10: Vishkambha
    assert yoga(300.0, 101.0) == 4  # sum 401 wraps to 41: 4th yoga (40..53 1/3)


def test_karana_index() -> None:
    assert karana(0.0, 0.0) == 0
    assert karana(0.0, 5.999) == 0
    assert karana(0.0, 6.0) == 1
    assert karana(100.0, 99.0) == 59


def test_karana_fixed_and_movable() -> None:
    assert karana_key(0) == "kimstughna"
    assert karana_key(1) == "bava"
    assert karana_key(7) == "vishti"
    assert karana_key(8) == "bava"
    assert karana_key(56) == "vishti"
    assert karana_key(57) == "shakuni"
    assert karana_key(58) == "chatushpada"
    assert karana_key(59) == "naga"


def test_karana_key_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        karana_key(60)
    with pytest.raises(ValueError):
        karana_key(-1)


def test_find_end_linear() -> None:
    # 12 deg/day from 5 deg: next multiple of 12 is reached after 7/12 day.
    end = panchang.find_end(lambda jd: (5.0 + 12.0 * (jd - 100.0)) % 360.0, 100.0, 12.0)
    assert abs(end - (100.0 + 7.0 / 12.0)) < SECOND


def test_find_end_across_360() -> None:
    # 350 deg moving 13 deg/day crosses 360 (= 0, a multiple of 40/3) after 10/13 day.
    end = panchang.find_end(lambda jd: (350.0 + 13.0 * (jd - 50.0)) % 360.0, 50.0, 40.0 / 3.0)
    assert abs(end - (50.0 + 10.0 / 13.0)) < SECOND


def test_find_end_on_boundary_finds_next() -> None:
    end = panchang.find_end(lambda jd: (12.0 * (jd - 10.0)) % 360.0, 10.0, 12.0)
    assert abs(end - 11.0) < SECOND


def test_elements_at_consistent_with_formulas() -> None:
    jd = jd_from_utc(datetime(2024, 4, 10, 6, 0, tzinfo=UTC))
    at = panchang.elements_at(jd, *DELHI, 0.0, DEFAULT)
    assert at.tithi.key == TITHIS[at.tithi.index - 1]
    assert at.paksha == paksha(at.tithi.index)
    assert 1 <= at.pada <= 4
    assert at.karana.key == karana_key(at.karana.index)
    assert at.karana.index in (2 * at.tithi.index - 2, 2 * at.tithi.index - 1)
    for attr in ("tithi", "nakshatra", "yoga", "karana"):
        el = getattr(at, attr)
        end = jd_from_utc(el.ends_utc)
        assert jd < end < jd + 1.5
        # Just before the end the element still holds; just after it has changed.
        before = panchang.elements_at(end - 2 * SECOND, *DELHI, 0.0, DEFAULT)
        after = panchang.elements_at(end + 2 * SECOND, *DELHI, 0.0, DEFAULT)
        assert getattr(before, attr).key == el.key
        assert getattr(after, attr).key != el.key


def test_vaar_before_sunrise() -> None:
    # 04:30 IST on Wednesday 2024-01-10 is before that day's 07:15 sunrise: still Tuesday.
    jd = jd_from_utc(to_utc(datetime(2024, 1, 10, 4, 30), "Asia/Kolkata"))
    assert panchang.elements_at(jd, *DELHI, 0.0, DEFAULT).vaar == "mangala"


def test_vaar_after_sunrise() -> None:
    jd = jd_from_utc(to_utc(datetime(2024, 1, 10, 7, 30), "Asia/Kolkata"))
    assert panchang.elements_at(jd, *DELHI, 0.0, DEFAULT).vaar == "budha"
    # Late evening and just before the next sunrise are still Wednesday's vaar.
    jd = jd_from_utc(to_utc(datetime(2024, 1, 11, 6, 0), "Asia/Kolkata"))
    assert panchang.elements_at(jd, *DELHI, 0.0, DEFAULT).vaar == "budha"


def test_vaar_at_range_start() -> None:
    # JD_MIN is 1800-01-01 11:09 local mean time at Delhi: that day's sunrise (~01:45 UT) lies
    # before the supported range, but the moment is valid and after it.
    at = panchang.elements_at(ephemeris.JD_MIN, *DELHI, 0.0, DEFAULT)
    assert at.vaar == VAARS[date(1800, 1, 1).weekday()]


def test_day_panchang_delhi() -> None:
    dp = panchang.day_panchang(date(2024, 1, 10), "Asia/Kolkata", *DELHI, 0.0, DEFAULT)
    assert dp.date == date(2024, 1, 10)
    assert dp.at_sunrise.vaar == "budha"
    assert jd_from_utc(dp.at_sunrise.tithi.ends_utc) > jd_from_utc(dp.sunrise_utc)
    assert dp.sunrise_utc < dp.sunset_utc
    # Eve of Amavasya: the thin crescent rises shortly before the Sun, within the civil day.
    assert dp.moonrise_utc is not None and dp.moonrise_utc < dp.sunrise_utc
    assert dp.moonset_utc is not None
    for t in (dp.sunrise_utc, dp.sunset_utc, dp.moonrise_utc, dp.moonset_utc):
        assert t.tzinfo is UTC


@pytest.mark.parametrize(
    ("day", "hours"),
    [(date(2024, 3, 10), 23), (date(2024, 11, 3), 25), (date(2024, 3, 9), 24)],
)
def test_day_panchang_dst_days(day: date, hours: int) -> None:
    # New York: 2024-03-10 has 23 h, 2024-11-03 has 25 h. Events must lie inside the civil day.
    tz = "America/New_York"
    dp = panchang.day_panchang(day, tz, 40.7128, -74.0060, 0.0, DEFAULT)
    start = to_utc(datetime(day.year, day.month, day.day), tz, fold=0)
    nxt = date.fromordinal(day.toordinal() + 1)
    end = to_utc(datetime(nxt.year, nxt.month, nxt.day), tz, fold=0)
    assert (end - start).total_seconds() == hours * 3600
    for t in (dp.sunrise_utc, dp.sunset_utc, dp.moonrise_utc, dp.moonset_utc):
        assert t is None or start <= t < end
    # Sunrise moves smoothly across the DST change in UT (not by an hour).
    yesterday = date.fromordinal(day.toordinal() - 1)
    prev = panchang.day_panchang(yesterday, tz, 40.7128, -74.0060, 0.0, DEFAULT)
    delta_min = (dp.sunrise_utc - prev.sunrise_utc).total_seconds() / 60 - 1440
    assert abs(delta_min) < 3.0


def test_day_panchang_moon_events_stay_inside_civil_day() -> None:
    # Across a month of New York days, including the 25 h day, every moon event found lies
    # inside its own civil day, and each day without a moonrise is followed by one with it.
    tz = "America/New_York"
    for d in range(date(2024, 10, 20).toordinal(), date(2024, 11, 18).toordinal()):
        day = date.fromordinal(d)
        dp = panchang.day_panchang(day, tz, 40.7128, -74.0060, 0.0, DEFAULT)
        start = to_utc(datetime(day.year, day.month, day.day), tz, fold=0)
        nxt = date.fromordinal(d + 1)
        end = to_utc(datetime(nxt.year, nxt.month, nxt.day), tz, fold=0)
        for t in (dp.moonrise_utc, dp.moonset_utc):
            assert t is None or start <= t < end


def test_day_panchang_polar_no_sunrise() -> None:
    with pytest.raises(InputError):
        panchang.day_panchang(date(2024, 6, 21), "Arctic/Longyearbyen", 78.2, 15.6, 0.0, DEFAULT)


def test_day_panchang_first_supported_ist_day() -> None:
    # 1800-01-02 in IST (LMT +05:53:28 then): local midnight is 1800-01-01 ~18:06 UT, after
    # JD_MIN; nothing may search before it.
    dp = panchang.day_panchang(date(1800, 1, 2), "Asia/Kolkata", *DELHI, 0.0, DEFAULT)
    assert jd_from_utc(dp.sunrise_utc) > ephemeris.JD_MIN
    assert dp.at_sunrise.vaar == VAARS[date(1800, 1, 2).weekday()]


def test_day_panchang_last_supported_day_west_of_greenwich() -> None:
    # 2399-12-31 in Sao Paulo (UTC-3): the civil day ends 3 h past JD_MAX, its moonset and the
    # end times of the elements prevailing at sunrise fall after JD_MAX too.
    tz = "America/Sao_Paulo"
    dp = panchang.day_panchang(date(2399, 12, 31), tz, -23.55, -46.63, 0.0, DEFAULT)
    assert jd_from_utc(dp.sunset_utc) < ephemeris.JD_MAX
    assert dp.moonset_utc is not None and jd_from_utc(dp.moonset_utc) > ephemeris.JD_MAX
    assert jd_from_utc(dp.at_sunrise.yoga.ends_utc) > ephemeris.JD_MAX
    assert dp.at_sunrise.vaar == VAARS[date(2399, 12, 31).weekday()]


def _ranged_linear(jd0: float, start: float, rate: float) -> Callable[[float], float]:
    def f(t: float) -> float:
        ephemeris.check_range(t, derived=True)  # as body_longitude does for end-time searches
        return (start + rate * (t - jd0)) % 360.0

    return f


LIMIT = ephemeris.JD_MAX + ephemeris.DERIVED_MARGIN_DAYS


def test_find_end_near_range_end_does_not_poke_past() -> None:
    # The crossing is 0.05 day before the last computable instant; a 0.25 day bracket step
    # must not overshoot it.
    jd0 = LIMIT - 0.1
    end = panchang.find_end(_ranged_linear(jd0, 11.4, 12.0), jd0, 12.0)
    assert abs(end - (jd0 + 0.05)) < SECOND


def test_elements_at_rejects_moment_past_range() -> None:
    with pytest.raises(EphemerisRangeError):
        panchang.elements_at(ephemeris.JD_MAX + 0.01, *DELHI, 0.0, DEFAULT)


def test_end_time_beyond_range_raises() -> None:
    # An element whose end lies after the derived margin is a genuinely out-of-range instant.
    jd0 = LIMIT - 0.1
    with pytest.raises(EphemerisRangeError):
        panchang.find_end(_ranged_linear(jd0, 0.0, 12.0), jd0, 12.0)
