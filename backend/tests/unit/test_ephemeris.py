from datetime import UTC, datetime
from pathlib import Path

import pytest

from vedic_engine import ephemeris
from vedic_engine.angles import arc, norm
from vedic_engine.constants import Graha
from vedic_engine.models import EngineError, EphemerisRangeError, InputError, Settings
from vedic_engine.timeutil import jd_from_utc

DEFAULT = Settings()
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
    assert ephemeris.JD_MIN == jd_from_utc(datetime(1800, 1, 1, tzinfo=UTC))
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
    "dt", [datetime(1799, 12, 31, tzinfo=UTC), datetime(2400, 1, 2, tzinfo=UTC)]
)
def test_out_of_range_raises(dt: datetime) -> None:
    jd = jd_from_utc(dt)
    with pytest.raises(EphemerisRangeError):
        ephemeris.check_range(jd)
    with pytest.raises(EphemerisRangeError):
        ephemeris.positions(jd, DEFAULT)
    with pytest.raises(EphemerisRangeError):
        ephemeris.ascendant(jd, *DELHI)


def test_range_edges_use_swiss_ephemeris_files() -> None:
    for jd in (ephemeris.JD_MIN + 0.25, ephemeris.JD_MAX):
        assert len(ephemeris.positions(jd, DEFAULT)) == 9
        ephemeris.tropical_longitude(jd, Graha.SATURN)


def test_first_hours_of_range_raise_range_error_not_moshier() -> None:
    # sepl_18.se1 starts at 1800-01-01 0h; light-time needs data from before that instant.
    with pytest.raises(EphemerisRangeError):
        ephemeris.positions(ephemeris.JD_MIN, DEFAULT)


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
