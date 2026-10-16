"""Golden checks: tropical longitudes vs NASA JPL Horizons; Lahiri ayanamsa vs the IAE.

Two documented convention differences are reconciled before comparing (like with like); neither
touches the tolerances:

1. Time scale after the last leap second. Horizons' "UT" is UTC after 1962 and, per its own
   header, "the last known leap-second is used as a constant over future intervals", so for
   any epoch after 2017-01-01 its time tag means TT = UT + 69.184 s exactly. Swiss Ephemeris
   ``calc_ut`` instead applies its own (extrapolated) Delta T, which differs by minutes by 2400.
   For those epochs we evaluate the engine at the same TT instant.

2. Ecliptic-of-date frame. Horizons quantity 31 is referred to the IAU76/80 ecliptic and
   equinox of date (stated in its column header); Swiss Ephemeris uses the modern IAU 2006
   precession (Vondrak 2011 long-term). The IAU 1976 precession rate is too large by ~0.3"/cy,
   so the two equinoxes drift apart linearly from J2000 (~1.2" by 2399). We shift the engine
   longitude by p_A(IAU1976) - p_A(IAU2006): the difference of the two published polynomials
   for general precession in longitude (Lieske et al. 1977, A&A 58, 1; Capitaine et al. 2003,
   A&A 412, 567). Sidereal output is unaffected, because the ayanamsa is precessed with the
   same model as the tropical longitudes and the difference cancels.
"""

import json
from pathlib import Path
from typing import Any

import pytest
import swisseph as swe

from tolerances import AYANAMSA_ARCSEC, MOON_ARCSEC, PLANET_ARCSEC
from vedic_engine import ephemeris
from vedic_engine.angles import arc
from vedic_engine.constants import SEVEN, Graha
from vedic_engine.models import Settings

pytestmark = pytest.mark.golden

GOLDEN = Path(__file__).resolve().parent.parent.parent / "fixtures" / "golden"
HORIZONS = sorted((GOLDEN / "horizons").glob("*.json"))

LAST_LEAP_SECOND_JD = 2457754.5  # 2017-01-01 00:00 UTC; TT - UTC = 69.184 s since then
TT_MINUS_UTC_DAYS = 69.184 / 86400.0
J2000 = 2451545.0


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def _signed_arcsec(a: float, b: float) -> float:
    d = arc(b, a)
    return (d - 360.0 if d > 180.0 else d) * 3600.0


def _engine_ut_for_horizons(jd_tag: float) -> float:
    """UT at which the engine sees the same physical instant as the Horizons time tag."""
    if jd_tag < LAST_LEAP_SECOND_JD:
        return jd_tag
    jd_tt = jd_tag + TT_MINUS_UTC_DAYS
    ut = jd_tt
    for _ in range(5):  # Delta T changes by << 1 s over the iteration step
        ut = jd_tt - swe.deltat(ut)
    return ut


def _iau1976_minus_iau2006_arcsec(jd_tt: float) -> float:
    t = (jd_tt - J2000) / 36525.0
    p76 = 5029.0966 * t + 1.11113 * t**2 - 0.000006 * t**3
    p06 = (
        5028.796195 * t
        + 1.1054348 * t**2
        + 0.00007964 * t**3
        - 0.000023857 * t**4
        - 0.0000000383 * t**5
    )
    return p76 - p06


@pytest.fixture(scope="module", autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


def test_fixture_set_complete() -> None:
    assert len(HORIZONS) == 30
    for path in HORIZONS:
        data = _load(path)
        assert data["source"] == "JPL Horizons"
        assert data["query"]["QUANTITIES"] == "31"
        assert data["query"]["TIME_TYPE"] == "UT"
        assert set(data["lon"]) == {g.value for g in SEVEN}


@pytest.mark.parametrize("graha", SEVEN, ids=str)
@pytest.mark.parametrize("path", HORIZONS, ids=lambda p: p.stem)
def test_tropical_longitudes_match_jpl(path: Path, graha: Graha) -> None:
    data = _load(path)
    jd_ut = _engine_ut_for_horizons(data["jd_ut"])
    jd_tt = jd_ut + swe.deltat(jd_ut)
    ours = ephemeris.tropical_longitude(jd_ut, graha)
    ours_in_horizons_frame = ours + _iau1976_minus_iau2006_arcsec(jd_tt) / 3600.0
    err = abs(_signed_arcsec(ours_in_horizons_frame, data["lon"][graha.value]))
    tol = MOON_ARCSEC if graha is Graha.MOON else PLANET_ARCSEC
    assert err <= tol, f"{graha} {err:.3f} arcsec at JD {data['jd_ut']}"


AYANAMSA_VALUES = _load(GOLDEN / "ayanamsa_iae.json")["values"]


def test_ayanamsa_fixture_has_published_values() -> None:
    published = [v for v in AYANAMSA_VALUES if "url" in v["source"]]
    assert len(published) >= 3
    assert all(v["jd_ut"] >= 2458849.5 for v in published)  # 2020 onwards


@pytest.mark.parametrize("value", AYANAMSA_VALUES, ids=lambda v: v["label"][:10])
def test_ayanamsa_matches_iae(value: dict[str, Any]) -> None:
    assert value["kind"] == "true"
    ours = ephemeris.ayanamsa(value["jd_ut"], Settings())
    err = abs(ours - value["ayanamsa_deg"]) * 3600.0
    assert err <= AYANAMSA_ARCSEC, f"{value['label']}: {err:.3f} arcsec"
