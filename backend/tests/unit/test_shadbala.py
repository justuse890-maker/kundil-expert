"""Shadbala unit tests (BPHS Ch 27, as worked by B. V. Raman, Graha and Bhava Balas, 1942)."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from vedic_engine import ephemeris, panchang
from vedic_engine.constants import SEVEN, Graha
from vedic_engine.models import Settings
from vedic_engine.shadbala import (
    REQUIRED_RUPA,
    SCHOOL,
    _day_frame,
    _dig,
    _drishti,
    _kranti,
    _natonnata,
    _paksha,
    _tribhaga,
    _uchcha,
    _yuddha,
    ahargana,
    ahargana_lords,
    naisargika,
    shadbala,
    shadbala_report,
)
from vedic_engine.timeutil import jd_from_utc, to_utc

# Precision of these checks (not spec 7 tolerances): naisargika is printed to 2 decimals; the
# sunrise frame must reproduce panchang's own sunrise/sunset to well under a second.
NAISARGIKA_PRINT_PRECISION = 0.005
FRAME_HOURS_PRECISION = 1e-4

DEFAULT = Settings()
LONDON = (51.5074, -0.1278)
OSLO = (59.9139, 10.7522)
BANGALORE = (12.9716, 77.5946)
SVALBARD = (78.2232, 15.6267)

DEEP_EXALTATION = {
    Graha.SUN: 10.0, Graha.MOON: 33.0, Graha.MARS: 298.0, Graha.MERCURY: 165.0,
    Graha.JUPITER: 95.0, Graha.VENUS: 357.0, Graha.SATURN: 200.0,
}  # fmt: skip


def test_school_is_named() -> None:
    assert SCHOOL == "raman-1942"


def test_naisargika_constants() -> None:
    expected = {
        Graha.SUN: 60.0, Graha.MOON: 51.43, Graha.VENUS: 42.86, Graha.JUPITER: 34.29,
        Graha.MERCURY: 25.71, Graha.MARS: 17.14, Graha.SATURN: 8.57,
    }  # fmt: skip
    for g, v in expected.items():
        assert naisargika(g) == pytest.approx(v, abs=NAISARGIKA_PRINT_PRECISION)


@pytest.mark.parametrize("graha", SEVEN, ids=[g.value for g in SEVEN])
def test_uchcha_bala_exalted_is_60(graha: Graha) -> None:
    assert _uchcha(graha, DEEP_EXALTATION[graha]) == pytest.approx(60.0)


@pytest.mark.parametrize("graha", SEVEN, ids=[g.value for g in SEVEN])
def test_uchcha_bala_debilitated_is_0(graha: Graha) -> None:
    assert _uchcha(graha, DEEP_EXALTATION[graha] + 180.0) == pytest.approx(0.0, abs=1e-9)


def test_uchcha_bala_is_symmetric_about_exaltation() -> None:
    assert _uchcha(Graha.SUN, 40.0) == pytest.approx(_uchcha(Graha.SUN, 340.0))
    assert _uchcha(Graha.SUN, 100.0) == pytest.approx(30.0)


def test_dig_bala_max() -> None:
    asc, mc = 294.95, 214.9
    assert _dig(Graha.JUPITER, asc, asc, mc) == pytest.approx(60.0)
    assert _dig(Graha.MERCURY, asc, asc, mc) == pytest.approx(60.0)
    assert _dig(Graha.SUN, mc, asc, mc) == pytest.approx(60.0)
    assert _dig(Graha.MARS, mc, asc, mc) == pytest.approx(60.0)
    assert _dig(Graha.SATURN, asc + 180.0, asc, mc) == pytest.approx(60.0)
    assert _dig(Graha.MOON, mc + 180.0, asc, mc) == pytest.approx(60.0)
    assert _dig(Graha.VENUS, mc + 180.0, asc, mc) == pytest.approx(60.0)
    assert _dig(Graha.SUN, mc + 180.0, asc, mc) == pytest.approx(0.0, abs=1e-9)


def test_required_rupa() -> None:
    assert REQUIRED_RUPA == {
        Graha.SUN: 6.5, Graha.MOON: 6.0, Graha.MARS: 5.0, Graha.MERCURY: 7.0,
        Graha.JUPITER: 6.5, Graha.VENUS: 5.5, Graha.SATURN: 5.0,
    }  # fmt: skip


def test_ahargana_of_raman_example_date() -> None:
    """Raman p. 43 (Example 23): 16 October 1918 -> 33,405; p. 44 (Example 27) the same."""
    assert ahargana(date(1918, 10, 16)) == 33405


def test_ahargana_lords_match_santhanam_example() -> None:
    """Santhanam BPHS Vol 1 pp. 271-272: 1 June 1984 -> year Jupiter, month Venus, Friday.

    Santhanam uses a different abbreviated ahargana (65,295); the lords must still agree.
    """
    assert ahargana_lords(ahargana(date(1984, 6, 1))) == (Graha.JUPITER, Graha.VENUS, Graha.VENUS)


@pytest.mark.parametrize(
    ("bhuja", "minutes"),
    [(0.0, 0.0), (15.0, 362.0), (30.0, 703.0), (45.0, 1002.0), (60.0, 1238.0), (75.0, 1388.0),
     (90.0, 1440.0)],
)  # fmt: skip
def test_kranti_table(bhuja: float, minutes: float) -> None:
    """Raman Art. 73 (pp. 50-51): declination at each 15-degree step of the bhuja."""
    assert _kranti(bhuja) == pytest.approx(minutes / 60.0)


@pytest.mark.parametrize(
    ("angle", "value"),
    [(29.0, 0.0), (30.0, 0.0), (60.0, 15.0), (90.0, 45.0), (120.0, 30.0), (150.0, 0.0),
     (180.0, 60.0), (240.0, 30.0), (300.0, 0.0), (330.0, 0.0)],
)  # fmt: skip
def test_drishti_values(angle: float, value: float) -> None:
    """Raman Art. 110 and 114 (pp. 74, 77): ordinary aspect value by aspect angle."""
    assert _drishti(angle) == pytest.approx(value)


@pytest.fixture
def _ephe(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


@pytest.mark.usefixtures("_ephe")
def test_shadbala_live_chart_structure() -> None:
    jd = jd_from_utc(to_utc(datetime(1990, 5, 17, 9, 30), "Asia/Kolkata"))  # a Thursday
    rows = shadbala(jd, 28.6139, 77.209, Settings())
    assert tuple(rows) == SEVEN
    for g, r in rows.items():
        total = r.sthana + r.dig + r.kaala + r.cheshta + r.naisargika + r.drik
        assert r.total_virupa == pytest.approx(total)
        assert r.total_rupa == pytest.approx(total / 60.0)
        assert r.required_rupa == REQUIRED_RUPA[g]
        assert r.ratio == pytest.approx(r.total_rupa / r.required_rupa)
        sthana = sum(
            r.components[k] for k in ("uchcha", "saptavargaja", "ojhayugma", "kendradi", "drekkana")
        )
        assert r.sthana == pytest.approx(sthana)
        kaala = sum(
            r.components[k]
            for k in ("natonnata", "paksha", "tribhaga", "abda", "masa", "vara", "hora", "ayana",
                      "yuddha")
        )  # fmt: skip
        assert r.kaala == pytest.approx(kaala)
        assert 0.0 <= r.dig <= 60.0
        assert 0.0 <= r.cheshta <= 60.0
    # Exactly one planet each holds the year, month, day and hora lordship.
    for key, value in (("abda", 15.0), ("masa", 30.0), ("vara", 45.0), ("hora", 60.0)):
        assert sorted(r.components[key] for r in rows.values()).count(value) == 1
    assert rows[Graha.JUPITER].components["tribhaga"] == 60.0
    assert rows[Graha.JUPITER].components["vara"] == 45.0
    assert rows[Graha.SUN].cheshta == 0.0 and rows[Graha.MOON].cheshta == 0.0


def _lons(**kw: float) -> dict[Graha, float]:
    base = {g: 30.0 * i + 1.0 for i, g in enumerate(SEVEN)}
    base.update({Graha(k): v for k, v in kw.items()})
    return base


def test_natonnata_noon_and_midnight() -> None:
    assert _natonnata(Graha.SUN, 12.0) == pytest.approx(60.0)
    assert _natonnata(Graha.MOON, 12.0) == pytest.approx(0.0)
    assert _natonnata(Graha.SATURN, 0.0) == pytest.approx(60.0)
    assert _natonnata(Graha.VENUS, 0.0) == pytest.approx(0.0)
    assert _natonnata(Graha.MERCURY, 3.0) == 60.0


@pytest.mark.parametrize(
    ("is_day", "part", "lord"),
    [(True, 0.1, Graha.MERCURY), (True, 0.5, Graha.SUN), (True, 0.9, Graha.SATURN),
     (False, 0.1, Graha.MOON), (False, 0.5, Graha.VENUS), (False, 0.9, Graha.MARS)],
)  # fmt: skip
def test_tribhaga_lords(is_day: bool, part: float, lord: Graha) -> None:
    got = {g for g in SEVEN if _tribhaga(g, is_day, part) == 60.0}
    assert got == {lord, Graha.JUPITER}


def test_paksha_malefic_moon_and_afflicted_mercury() -> None:
    # Moon 30 deg ahead of the Sun (before the 8th tithi): malefic, value doubled.
    lon = _lons(sun=100.0, moon=130.0, mercury=105.0)
    assert _paksha(Graha.MOON, lon) == pytest.approx(2.0 * (60.0 - 10.0))
    # Mercury in the Sun's sign is malefic; Jupiter stays benefic.
    assert _paksha(Graha.MERCURY, lon) == pytest.approx(50.0)
    assert _paksha(Graha.JUPITER, lon) == pytest.approx(10.0)
    lon = _lons(sun=100.0, moon=280.0, mercury=125.0)  # full Moon, Mercury alone in Simha
    assert _paksha(Graha.MOON, lon) == pytest.approx(120.0)
    assert _paksha(Graha.MERCURY, lon) == pytest.approx(60.0)
    assert _paksha(Graha.SATURN, lon) == pytest.approx(0.0)


def test_paksha_malefic_moon_takes_malefic_value_doubled() -> None:
    """Raman pp. 34-35 (Art. 53, 55 rule c) and Santhanam p. 269 (note to 27.10-11): the Moon
    is malefic outside the 8th bright to 8th dark tithi and her value is always doubled."""
    for moon in (130.0, 70.0):  # 30 deg after and 30 deg before the Sun at 100
        assert _paksha(Graha.MOON, _lons(sun=100.0, moon=moon)) == pytest.approx(100.0)
    assert _paksha(Graha.MOON, _lons(sun=100.0, moon=184.0)) == pytest.approx(2.0 * 84.0 / 3.0)
    assert _paksha(Graha.MOON, _lons(sun=100.0, moon=183.9)) == pytest.approx(
        2.0 * (60.0 - 83.9 / 3.0)
    )


@pytest.mark.usefixtures("_ephe")
def test_shadbala_at_range_edges() -> None:
    for jd in (ephemeris.JD_MIN, ephemeris.JD_MAX):
        rows, warnings = shadbala_report(jd, 28.6139, 77.209, DEFAULT)
        assert tuple(rows) == SEVEN
        # 1800-01-01 06:00 UT is after Delhi's sunrise, which precedes the supported range.
        assert [w.code for w in warnings] == (["range_sunrise"] if jd < 2.4e6 else [])


def test_yuddha_lesser_longitude_wins() -> None:
    lon = _lons(mars=200.0, venus=200.5)
    strength = {g: 100.0 for g in SEVEN} | {Graha.MARS: 150.0, Graha.VENUS: 114.0}
    war = _yuddha(lon, strength)
    assert war[Graha.MARS] == pytest.approx(36.0 / (16.6 - 9.4))
    assert war[Graha.VENUS] == pytest.approx(-36.0 / (16.6 - 9.4))
    assert all(war[g] == 0.0 for g in SEVEN if g not in (Graha.MARS, Graha.VENUS))
    # Across 0 deg Jupiter at 359.8 is behind Saturn at 0.3, so Jupiter wins even though it is
    # the weaker of the two: the share moves by longitude, not by strength.
    strength = {g: 100.0 for g in SEVEN} | {Graha.JUPITER: 120.0, Graha.SATURN: 152.6}
    across_zero = _yuddha(_lons(jupiter=359.8, saturn=0.3), strength)
    assert across_zero[Graha.JUPITER] == pytest.approx(32.6 / (190.4 - 158.0))
    assert across_zero[Graha.SATURN] == pytest.approx(-32.6 / (190.4 - 158.0))
    assert _yuddha(_lons(jupiter=10.0, saturn=11.0), strength)[Graha.JUPITER] == 0.0  # 1 deg apart


@pytest.mark.usefixtures("_ephe")
def test_live_raman_chart_time_lords() -> None:
    """Raman's Standard Horoscope (16 Oct 1918, 14:00 LMT, 13 N 77 35 E) from the ephemeris.

    The categorical Kaala components must equal his printed ones (pp. 37-48, 57): third part
    of the day (Saturn), year Saturn, month and weekday Mercury, Moon's hora.
    """
    lon_e = 77.0 + 35.0 / 60.0
    jd = jd_from_utc(datetime(1918, 10, 16, 14, tzinfo=UTC)) - lon_e / 360.0
    rows = shadbala(jd, 13.0, lon_e, Settings())
    expected = {
        "tribhaga": {Graha.JUPITER, Graha.SATURN}, "abda": {Graha.SATURN},
        "masa": {Graha.MERCURY}, "vara": {Graha.MERCURY}, "hora": {Graha.MOON},
    }  # fmt: skip
    for key, lords in expected.items():
        assert {g for g, r in rows.items() if r.components[key] > 0.0} == lords, key


def test_ahargana_lords_before_1900() -> None:
    """Raman's ahargana counts back past 1900 (and below zero before 1827) without a seam."""
    assert ahargana_lords(ahargana(date(1850, 1, 1)))[2] is Graha.MARS  # a Tuesday
    assert ahargana(date(1800, 1, 1)) < 0
    assert ahargana_lords(ahargana(date(1800, 1, 1)))[2] is Graha.MERCURY  # a Wednesday
    weekday_lord = (Graha.MOON, Graha.MARS, Graha.MERCURY, Graha.JUPITER, Graha.VENUS,
                    Graha.SATURN, Graha.SUN)  # fmt: skip  # date.weekday(): Monday = 0
    day = date(1800, 1, 1)
    for _ in range(800):
        assert ahargana_lords(ahargana(day))[2] is weekday_lord[day.weekday()], day
        day += timedelta(days=1)


def _sun_events(day: date, tz: str, place: tuple[float, float]) -> tuple[float, float, float]:
    """(sunrise, sunset, next sunrise) of civil ``day`` from panchang, as JDs."""
    today = panchang.day_panchang(day, tz, *place, 0.0, DEFAULT)
    tomorrow = panchang.day_panchang(day + timedelta(days=1), tz, *place, 0.0, DEFAULT)
    return (
        jd_from_utc(today.sunrise_utc),
        jd_from_utc(today.sunset_utc),
        jd_from_utc(tomorrow.sunrise_utc),
    )


@pytest.mark.usefixtures("_ephe")
@pytest.mark.parametrize(
    ("place", "tz", "local"),
    [
        (LONDON, "Europe/London", datetime(2024, 7, 9, 12, 0)),
        (LONDON, "Europe/London", datetime(2024, 7, 9, 23, 30)),
        (LONDON, "Europe/London", datetime(2024, 10, 15, 12, 0)),
        (LONDON, "Europe/London", datetime(2024, 12, 21, 20, 0)),
        (OSLO, "Europe/Oslo", datetime(2024, 6, 21, 13, 0)),
        (OSLO, "Europe/Oslo", datetime(2024, 6, 21, 23, 50)),
        (BANGALORE, "Asia/Kolkata", datetime(2024, 12, 20, 14, 0)),
    ],
    ids=["london-jul-noon", "london-jul-night", "london-oct-noon", "london-dec-night",
         "oslo-midsummer-day", "oslo-midsummer-night", "bangalore-dec-noon"],
)  # fmt: skip
def test_day_frame_matches_panchang_sunrise(
    place: tuple[float, float], tz: str, local: datetime
) -> None:
    """Sunrises more than 24 h apart (high latitudes) must not fall back to a fixed frame."""
    jd = jd_from_utc(to_utc(local, tz))
    rise, sett, nxt = _sun_events(local.date(), tz, place)
    is_day, part, hours, day, warning = _day_frame(jd, *place, DEFAULT)
    assert warning is None
    assert day == local.date()
    assert hours == pytest.approx((jd - rise) * 24.0, abs=FRAME_HOURS_PRECISION)
    assert is_day is (jd < sett)
    expected = (jd - rise) / (sett - rise) if is_day else (jd - sett) / (nxt - sett)
    assert part == pytest.approx(expected, abs=FRAME_HOURS_PRECISION / 24.0)


@pytest.mark.usefixtures("_ephe")
@pytest.mark.parametrize(
    ("place", "tz", "day"),
    [(BANGALORE, "Asia/Kolkata", date(2024, 12, 20)), (LONDON, "Europe/London", date(2024, 7, 9))],
    ids=["bangalore", "london-summer"],
)
def test_day_frame_seconds_before_sunrise_is_previous_night(
    place: tuple[float, float], tz: str, day: date
) -> None:
    rise, _sett, _nxt = _sun_events(day, tz, place)
    jd = rise - 5.0 / 86400.0
    is_day, part, hours, civil, warning = _day_frame(jd, *place, DEFAULT)
    assert warning is None
    assert not is_day
    assert civil == day - timedelta(days=1)
    assert part > 0.999
    prev_rise, _, _ = _sun_events(day - timedelta(days=1), tz, place)
    assert hours == pytest.approx((jd - prev_rise) * 24.0, abs=FRAME_HOURS_PRECISION)
    rows = shadbala(jd, *place, DEFAULT)
    assert {g for g, r in rows.items() if r.components["tribhaga"] > 0.0} == {
        Graha.MARS, Graha.JUPITER,
    }  # fmt: skip


@pytest.mark.usefixtures("_ephe")
def test_polar_day_falls_back_with_warning() -> None:
    jd = jd_from_utc(datetime(2024, 6, 21, 12, tzinfo=UTC))
    rows, warnings = shadbala_report(jd, *SVALBARD, DEFAULT)
    assert tuple(rows) == SEVEN
    assert [w.code for w in warnings] == ["polar_sunrise"]
    assert shadbala(jd, *SVALBARD, DEFAULT) == rows
    _rows, warnings = shadbala_report(jd, *LONDON, DEFAULT)
    assert warnings == ()
