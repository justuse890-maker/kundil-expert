"""Golden birth charts: build_kundli against independent references (spec 9 item 3).

Fixtures come from scripts/build_golden_charts.py: planets from JPL Horizons minus the
IAE-verified Lahiri ayanamsa, lagna from an independent sidereal-time computation. Categorical
values must match exactly; longitudes within the spec 7 tolerances.
"""

from functools import cache
from pathlib import Path
from typing import Any

import pytest

from chart_fixtures import CHART_PATHS, birth_of, load_chart
from tolerances import LAGNA_ARCMIN, MOON_ARCSEC, PLANET_ARCSEC
from vedic_engine import ephemeris
from vedic_engine.angles import arc, sign_of
from vedic_engine.constants import NAKSHATRAS, RASHIS, SEVEN, Graha
from vedic_engine.kundli import Kundli, build_kundli

pytestmark = pytest.mark.golden

# Half a millisecond: the fixture JD is the engine's own UT rounded to 9 decimals.
JD_MATCH_DAYS = 1e-8
BOUNDARY_ARCSEC = 120.0  # spec 9: "within 2' of a boundary"


@pytest.fixture(scope="module", autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


@cache
def _kundli(path: Path) -> Kundli:
    return build_kundli(birth_of(load_chart(path)))


def _arcsec(a: float, b: float) -> float:
    d = arc(a, b)
    return min(d, 360.0 - d) * 3600.0


def _all() -> list[dict[str, Any]]:
    return [load_chart(p) for p in CHART_PATHS]


def test_chart_set_coverage() -> None:
    charts = _all()
    assert len(charts) >= 25
    ids = {c["id"] for c in charts}
    years = [int(c["birth"]["local"][:4]) for c in charts]
    assert min(years) == 1850 and max(years) == 2030
    tags = {t for c in charts for t in c["coverage"]}
    assert {
        "southern_hemisphere", "west_longitude", "dst", "pre_1947_india", "war_time",
        "pre_sunrise", "lagna_boundary", "moon_boundary",
    } <= tags  # fmt: skip
    for city in ("sydney", "sao_paulo", "new_york", "los_angeles", "calcutta_1900", "bombay_1943"):
        assert any(city in i for i in ids), city
    for c in charts:
        assert c["source"] and c["verified_by"]
        assert (c["birth"]["lat"] < 0) == ("southern_hemisphere" in c["coverage"])
        assert (c["birth"]["lon"] < 0) == ("west_longitude" in c["coverage"])


def test_boundary_charts_are_within_two_arcmin() -> None:
    for c in _all():
        m = c["margins"]
        if "lagna_boundary" in c["coverage"]:
            assert m["lagna_arcsec"] < BOUNDARY_ARCSEC, c["id"]
        if "moon_boundary" in c["coverage"]:
            assert m["moon_nakshatra_arcsec"] < BOUNDARY_ARCSEC, c["id"]


@pytest.mark.parametrize("path", CHART_PATHS, ids=lambda p: p.stem)
def test_categorical_values_exact(path: Path) -> None:
    exp = load_chart(path)["expected"]
    k = _kundli(path)
    assert RASHIS[sign_of(k.lagna_lon)] == exp["lagna_rashi"]
    assert NAKSHATRAS[k.panchang.nakshatra.index] == exp["moon_nakshatra"]
    assert k.panchang.pada == exp["moon_pada"]
    assert k.panchang.tithi.index == exp["tithi"]
    assert k.panchang.tithi.key == exp["tithi_key"]
    assert RASHIS[k.vargas[9]["lagna"]] == exp["d9_lagna"]
    assert k.vimshottari[0].lord == exp["first_maha_lord"]


@pytest.mark.parametrize("path", CHART_PATHS, ids=lambda p: p.stem)
def test_longitudes_within_tolerance(path: Path) -> None:
    sid = load_chart(path)["sidereal"]
    k = _kundli(path)
    for g in SEVEN:
        tol = MOON_ARCSEC if g is Graha.MOON else PLANET_ARCSEC
        err = _arcsec(k.grahas[g].lon, sid[g.value])
        assert err <= tol, f"{g} {err:.3f} arcsec"
    lagna_err = _arcsec(k.lagna_lon, sid["lagna"]) / 60.0
    assert lagna_err <= LAGNA_ARCMIN, f"lagna {lagna_err:.3f} arcmin"


@pytest.mark.parametrize("path", CHART_PATHS, ids=lambda p: p.stem)
def test_civil_time_conversion_unchanged(path: Path) -> None:
    jd = load_chart(path)["time"]["jd_ut"]
    assert abs(_kundli(path).meta["jd_ut"] - jd) <= JD_MATCH_DAYS
