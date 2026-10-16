import math
from datetime import UTC, datetime
from pathlib import Path

import pytest
import swisseph as swe

from tolerances import LAGNA_ARCMIN, PLANET_ARCSEC
from vedic_engine import ephemeris
from vedic_engine.angles import arc, norm
from vedic_engine.constants import Graha
from vedic_engine.models import EngineError, EphemerisRangeError, InputError, Settings
from vedic_engine.timeutil import jd_from_utc

DEFAULT = Settings()
# Precision of the equation-of-time extremes as quoted to 0.1 min (not a spec 7 tolerance).
EOT_EXTREME_PRECISION_MIN = 0.2
TRUE_NODE = Settings(node="TRUE")
CENTER = Settings(sunrise="CENTER_NO_REFRACTION")
JD_2024 = jd_from_utc(datetime(2024, 4, 10, tzinfo=UTC))
DELHI = (28.6139, 77.2090)


@pytest.fixture(autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


def _signed_diff(a: float, b: float) -> float:
    d = arc(b, a)
    return d - 360.0 if d > 180.0 else d


def test_range_constants() -> None:
    # Ruling R9: sepl_18.se1 starts at 1800-01-01 0h; light-time needs ~0.1 day before that.
    assert ephemeris.JD_MIN == jd_from_utc(datetime(1800, 1, 1, 6, tzinfo=UTC))
    assert ephemeris.JD_MAX == jd_from_utc(datetime(2400, 1, 1, tzinfo=UTC))


def test_sidereal_equals_tropical_minus_ayanamsa() -> None:
    aya = ephemeris.ayanamsa(JD_2024, DEFAULT)
    pos = ephemeris.positions(JD_2024, DEFAULT)
    for graha in (Graha.SUN, Graha.MOON, Graha.MARS, Graha.SATURN, Graha.RAHU):
        expected = norm(ephemeris.tropical_longitude(JD_2024, graha) - aya)
        assert abs(_signed_diff(pos[graha].lon, expected)) < 1e-6, graha


def test_positions_cover_all_grahas_normalised() -> None:
    pos = ephemeris.positions(JD_2024, DEFAULT)
    assert set(pos) == set(Graha)
    for graha, p in pos.items():
        assert p.graha is graha
        assert 0.0 <= p.lon < 360.0


def test_body_longitude_matches_positions() -> None:
    pos = ephemeris.positions(JD_2024, DEFAULT)
    for graha in Graha:
        assert ephemeris.body_longitude(JD_2024, graha, DEFAULT) == pytest.approx(
            pos[graha].lon, abs=1e-9
        )


def test_ketu_opposite_rahu() -> None:
    for settings in (DEFAULT, TRUE_NODE):
        pos = ephemeris.positions(JD_2024, settings)
        rahu, ketu = pos[Graha.RAHU], pos[Graha.KETU]
        assert arc(rahu.lon, ketu.lon) == pytest.approx(180.0, abs=1e-9)
        assert ketu.speed == rahu.speed
        assert rahu.retro and ketu.retro


def _meeus_apparent_mean_node(jd_ut: float) -> float:
    """Meeus (Astronomical Algorithms, 2nd ed., eq. 47.7) mean node plus nutation in longitude."""
    jd_tt = jd_ut + swe.deltat(jd_ut)
    t = (jd_tt - 2451545.0) / 36525.0
    omega = 125.0445479 - 1934.1362891 * t + 0.0020754 * t**2 + t**3 / 467441 - t**4 / 60616000
    dpsi = swe.calc_ut(jd_ut, swe.ECL_NUT)[0][2]
    return norm(omega + dpsi)


def _tropical_rahu(jd_ut: float, settings: Settings) -> float:
    sidereal = ephemeris.positions(jd_ut, settings)[Graha.RAHU].lon
    return norm(sidereal + ephemeris.ayanamsa(jd_ut, settings))


NODE_EPOCHS = (2415020.5, 2451545.0, 2488069.5)  # 1900-01-01, J2000.0, 2100-01-01


@pytest.mark.parametrize("jd", NODE_EPOCHS)
def test_default_node_is_mean(jd: float) -> None:
    err = abs(_signed_diff(_tropical_rahu(jd, DEFAULT), _meeus_apparent_mean_node(jd))) * 3600
    assert err <= PLANET_ARCSEC


@pytest.mark.parametrize("jd", NODE_EPOCHS)
def test_true_node_setting_is_not_mean(jd: float) -> None:
    # At these epochs the true node is > 1 deg from the mean node.
    diff = abs(_signed_diff(_tropical_rahu(jd, TRUE_NODE), _meeus_apparent_mean_node(jd)))
    assert diff > 0.5


def test_true_vs_mean_node_differ() -> None:
    mean = ephemeris.positions(JD_2024, DEFAULT)[Graha.RAHU].lon
    true = ephemeris.positions(JD_2024, TRUE_NODE)[Graha.RAHU].lon
    diff = abs(_signed_diff(mean, true))
    assert 0.0 < diff < 2.0


def test_retro_flag_from_speed() -> None:
    pos = ephemeris.positions(JD_2024, DEFAULT)
    mercury = pos[Graha.MERCURY]
    assert mercury.speed < 0
    assert mercury.retro is True
    assert pos[Graha.SUN].retro is False  # the Sun is never retrograde


@pytest.mark.parametrize(
    "dt",
    [
        datetime(1799, 12, 31, tzinfo=UTC),
        datetime(1800, 1, 1, 5, 59, tzinfo=UTC),
        datetime(2400, 1, 2, tzinfo=UTC),
    ],
)
def test_out_of_range_raises(dt: datetime) -> None:
    jd = jd_from_utc(dt)
    with pytest.raises(EphemerisRangeError, match="06:00 UT"):
        ephemeris.check_range(jd)
    with pytest.raises(EphemerisRangeError):
        ephemeris.positions(jd, DEFAULT)
    with pytest.raises(EphemerisRangeError):
        ephemeris.ascendant(jd, *DELHI)


def test_range_edges_use_swiss_ephemeris_files() -> None:
    start = jd_from_utc(datetime(1800, 1, 1, 6, tzinfo=UTC))
    for jd in (start, ephemeris.JD_MAX):
        assert len(ephemeris.positions(jd, DEFAULT)) == 9
        ephemeris.tropical_longitude(jd, Graha.SATURN)


def test_missing_ephe_fails_fast(tmp_path: Path) -> None:
    with pytest.raises(EngineError):
        ephemeris.init(tmp_path)


def test_unusable_ephe_files_fail_fast(tmp_path: Path, ephe_path: Path) -> None:
    # Files present by name but empty/invalid: Swiss Ephemeris would silently use Moshier.
    for name in ("sepl_18.se1", "semo_18.se1", "seas_18.se1"):
        (tmp_path / name).write_bytes(b"")
    with pytest.raises(EngineError):
        ephemeris.init(tmp_path)
        ephemeris.positions(JD_2024, DEFAULT)
    ephemeris.init(ephe_path)


def test_unsupported_ayanamsa_rejected() -> None:
    with pytest.raises(InputError):
        ephemeris.ayanamsa(JD_2024, Settings(ayanamsa="RAMAN"))


def test_ascendant_is_sidereal() -> None:
    # Delhi, 2024-04-10 00:00 UTC (05:30 IST): just after sunrise the lagna is near the Sun.
    lagna = ephemeris.ascendant(JD_2024, *DELHI)
    sun = ephemeris.positions(JD_2024, DEFAULT)[Graha.SUN].lon
    assert 0.0 <= lagna < 360.0
    assert abs(_signed_diff(lagna, sun)) < 15.0


def test_rise_set_polar_none() -> None:
    jd = jd_from_utc(datetime(2024, 6, 21, tzinfo=UTC))
    assert ephemeris.rise_set(jd, 78.2, 15.6, 0.0, "sun", "rise", DEFAULT) is None
    assert ephemeris.rise_set(jd, 78.2, 15.6, 0.0, "sun", "set", DEFAULT) is None


def test_rise_set_definitions() -> None:
    # Delhi sunrise on 2024-06-21 is ~05:24 IST = 23:54 UTC on 2024-06-20.
    jd = jd_from_utc(datetime(2024, 6, 20, 12, tzinfo=UTC))
    limb = ephemeris.rise_set(jd, *DELHI, 0.0, "sun", "rise", DEFAULT)
    centre = ephemeris.rise_set(jd, *DELHI, 0.0, "sun", "rise", CENTER)
    assert limb is not None and centre is not None
    expected = jd_from_utc(datetime(2024, 6, 20, 23, 54, tzinfo=UTC))
    assert abs(limb - expected) * 1440 < 3.0
    # Upper limb + refraction sees the Sun several minutes before its centre crosses the horizon.
    assert 2.0 < (centre - limb) * 1440 < 6.0
    sunset = ephemeris.rise_set(jd, *DELHI, 0.0, "sun", "set", DEFAULT)
    assert sunset is not None and jd < sunset < jd + 1


def test_rise_set_none_when_event_beyond_one_day() -> None:
    # The Moon rises ~50 min later each day, so on some civil days it has no rise at all.
    # Scan 30 consecutive days at Delhi: at least one day must report no moonrise.
    start = jd_from_utc(datetime(2024, 1, 1, tzinfo=UTC)) - 5.5 / 24  # local midnight IST
    results = [
        ephemeris.rise_set(start + d, *DELHI, 0.0, "moon", "rise", DEFAULT) for d in range(30)
    ]
    assert any(r is None for r in results)
    for d, r in enumerate(results):
        assert r is None or start + d <= r < start + d + 1


def test_refraction_atmosphere_is_named_standard() -> None:
    # Sunrise convention (Drik Panchang "Edge"): ISA sea-level atmosphere for refraction.
    assert ephemeris.REFRACTION_PRESSURE_MBAR == 1013.25
    assert ephemeris.REFRACTION_TEMP_C == 15.0


def test_rise_set_window_may_extend_past_range_end() -> None:
    # Search from 2399-12-31 03:00 UT: the 1-day window ends past JD_MAX, the sunrise does not.
    start = ephemeris.JD_MAX - 21.0 / 24.0
    rise = ephemeris.rise_set(start, -23.55, -46.63, 0.0, "sun", "rise", DEFAULT)
    assert rise is not None and start <= rise < ephemeris.JD_MAX


def test_rise_set_event_just_past_range_end_is_returned() -> None:
    # Sao Paulo, search from 2399-12-31 03:00 UT (local midnight): the moonset of that civil
    # day falls ~0.02 day after JD_MAX, a derived instant inside DERIVED_MARGIN_DAYS.
    start = ephemeris.JD_MAX - 21.0 / 24.0
    moonset = ephemeris.rise_set(start, -23.55, -46.63, 0.0, "moon", "set", DEFAULT)
    assert moonset is not None and ephemeris.JD_MAX < moonset < ephemeris.JD_MAX + 0.1


def test_derived_margin_uses_swiss_ephemeris_files() -> None:
    # calc_ut refuses a Moshier fallback, so this proves the files cover the whole margin.
    edge = ephemeris.JD_MAX + ephemeris.DERIVED_MARGIN_DAYS
    for graha in (Graha.SUN, Graha.MOON):
        ephemeris.body_longitude(edge, graha, DEFAULT, derived=True)
    with pytest.raises(EphemerisRangeError):
        ephemeris.body_longitude(ephemeris.JD_MAX + 1e-6, Graha.SUN, DEFAULT)
    with pytest.raises(EphemerisRangeError):
        ephemeris.body_longitude(edge + 1e-6, Graha.SUN, DEFAULT, derived=True)


def test_rise_set_from_range_start() -> None:
    rise = ephemeris.rise_set(ephemeris.JD_MIN, *DELHI, 0.0, "sun", "rise", DEFAULT)
    assert rise is not None and rise >= ephemeris.JD_MIN
    with pytest.raises(EphemerisRangeError):
        ephemeris.rise_set(ephemeris.JD_MIN - 0.01, *DELHI, 0.0, "sun", "rise", DEFAULT)


def _meeus_mc(jd_ut: float, lon_east: float) -> float:
    """Tropical MC from GMST (Meeus 12.4) and mean obliquity (Meeus 22.2), no nutation."""
    t = (jd_ut - 2451545.0) / 36525.0
    gmst = 280.46061837 + 360.98564736629 * (jd_ut - 2451545.0) + 0.000387933 * t * t
    ramc = math.radians(norm(gmst + lon_east))
    eps = math.radians(23.439291111 - 0.0130041667 * t)
    return norm(math.degrees(math.atan2(math.sin(ramc), math.cos(ramc) * math.cos(eps))))


@pytest.mark.parametrize(
    "dt",
    [datetime(2024, 1, 10, 6, tzinfo=UTC), datetime(1918, 10, 16, 8, 50, tzinfo=UTC),
     datetime(2350, 7, 1, 18, tzinfo=UTC)],
)  # fmt: skip
def test_midheaven_is_sidereal_mc(dt: datetime) -> None:
    """Independent check: Meeus MC minus Lahiri ayanamsa; nutation (< 20") is left out."""
    jd = jd_from_utc(dt)
    expected = norm(_meeus_mc(jd, 77.58) - ephemeris.ayanamsa(jd, DEFAULT))
    got = ephemeris.midheaven(jd, 13.0, 77.58)
    assert abs(_signed_diff(got, expected)) * 60.0 < LAGNA_ARCMIN
    assert ephemeris.midheaven(jd, 60.0, 77.58) == pytest.approx(got)  # MC ignores latitude


def test_midheaven_and_equation_of_time_reject_out_of_range() -> None:
    for jd in (ephemeris.JD_MIN - 0.01, ephemeris.JD_MAX + 0.01):
        with pytest.raises(EphemerisRangeError):
            ephemeris.midheaven(jd, *DELHI)
        with pytest.raises(EphemerisRangeError):
            ephemeris.equation_of_time(jd)


@pytest.mark.parametrize(
    ("dt", "minutes"),
    [(datetime(2024, 11, 3, 12, tzinfo=UTC), 16.4), (datetime(2024, 2, 11, 12, tzinfo=UTC), -14.2)],
)
def test_equation_of_time_extremes(dt: datetime, minutes: float) -> None:
    """Apparent minus mean solar time; the annual extremes are about +16.4 and -14.2 min."""
    assert ephemeris.equation_of_time(jd_from_utc(dt)) * 1440.0 == pytest.approx(
        minutes, abs=EOT_EXTREME_PRECISION_MIN
    )
