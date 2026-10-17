"""Ayanamsa selector (Task 16)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from vedic_engine import ephemeris
from vedic_engine.angles import arc
from vedic_engine.constants import Graha
from vedic_engine.models import Settings
from vedic_engine.timeutil import jd_from_utc

JD_J2000 = 2451545.0
JD_2024 = jd_from_utc(datetime(2024, 4, 10, tzinfo=UTC))

# Swiss Ephemeris programmer's documentation, "Sidereal modes" table (swephexp.h / sweph.c
# ayanamsa[] table): (t0 as JD, ayanamsa at t0 in degrees).
#   Lahiri         t0 = 2435553.5     ayan_t0 = 23.250182778 - 0.004658035 (= 23.245524743)
#   Raman          t0 = 2415020.0     ayan_t0 = 360 - 338.98556            (= 21.01444)
#   Krishnamurti   t0 = 2415020.0     ayan_t0 = 360 - 337.636111           (= 22.363889)
#   Fagan/Bradley  t0 = 2433282.42346 ayan_t0 = 24.042044444
# The expected offset between two modes is computed here with linear precession at the
# IAU 2006 general-precession rate at J2000 (5028.796195 arcsec/Julian century).
T0_AYAN: dict[str, tuple[float, float]] = {
    "LAHIRI": (2435553.5, 23.250182778 - 0.004658035),
    "RAMAN": (2415020.0, 360.0 - 338.98556),
    "KP": (2415020.0, 360.0 - 337.636111),
    "FAGAN_BRADLEY": (2433282.42346, 24.042044444),
}
PRECESSION_DEG_PER_DAY = 5028.796195 / 3600.0 / 36525.0
# Linear precession from different epochs vs SE's polynomial precession: the rate drifts by
# ~0.02 arcsec/yr per century, i.e. < 2 arcsec over the <= 100-year spans here.
LINEAR_MODEL_TOL_DEG = 2.0 / 3600.0


def _linear(mode: str, jd: float) -> float:
    t0, aya0 = T0_AYAN[mode]
    return aya0 + (jd - t0) * PRECESSION_DEG_PER_DAY


@pytest.fixture(autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


@pytest.mark.parametrize("mode", ["RAMAN", "KP", "FAGAN_BRADLEY"])
def test_offset_from_lahiri_matches_documented_constants(mode: str) -> None:
    other = Settings(ayanamsa=mode)  # type: ignore[arg-type]
    got = ephemeris.ayanamsa(JD_J2000, other) - ephemeris.ayanamsa(JD_J2000, Settings())
    expected = _linear(mode, JD_J2000) - _linear("LAHIRI", JD_J2000)
    assert got == pytest.approx(expected, abs=LINEAR_MODEL_TOL_DEG)


@pytest.mark.parametrize("mode", ["RAMAN", "KP", "FAGAN_BRADLEY"])
def test_sidereal_longitudes_shift_by_exactly_the_ayanamsa_difference(mode: str) -> None:
    base, other = Settings(), Settings(ayanamsa=mode)  # type: ignore[arg-type]
    diff = ephemeris.ayanamsa(JD_2024, other) - ephemeris.ayanamsa(JD_2024, base)
    p_base = ephemeris.positions(JD_2024, base)
    p_other = ephemeris.positions(JD_2024, other)
    for graha in Graha:
        assert arc(p_base[graha].lon, p_other[graha].lon + diff) < 1e-6
        assert ephemeris.body_longitude(JD_2024, graha, other) == pytest.approx(
            p_other[graha].lon, abs=1e-9
        )
    asc_shift = ephemeris.ascendant(JD_2024, 28.6, 77.2, base) - ephemeris.ascendant(
        JD_2024, 28.6, 77.2, other
    )
    assert arc(asc_shift, diff) < 1e-6
    mc_shift = ephemeris.midheaven(JD_2024, 28.6, 77.2, base) - ephemeris.midheaven(
        JD_2024, 28.6, 77.2, other
    )
    assert arc(mc_shift, diff) < 1e-6


def test_mode_is_reasserted_after_another_mode() -> None:
    lahiri = ephemeris.ayanamsa(JD_2024, Settings())
    ephemeris.ayanamsa(JD_2024, Settings(ayanamsa="KP"))
    assert ephemeris.ayanamsa(JD_2024, Settings()) == lahiri
