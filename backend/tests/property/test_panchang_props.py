from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vedic_engine import ephemeris, panchang
from vedic_engine.angles import arc
from vedic_engine.constants import Graha
from vedic_engine.models import Settings

DEFAULT = Settings()
LON = st.floats(min_value=0.0, max_value=360.0, exclude_max=True, allow_nan=False)
# Whole supported range, leaving 2 days at the end so every tithi end is inside it.
JD = st.floats(min_value=ephemeris.JD_MIN, max_value=ephemeris.JD_MAX - 2.0, allow_nan=False)


@pytest.fixture(autouse=True, scope="module")
def _init() -> None:
    ephemeris.init(Path(__file__).resolve().parent.parent.parent / "ephe")


@given(sun=LON, moon=LON)
def test_half_tithi_inside_tithi(sun: float, moon: float) -> None:
    t = panchang.tithi(sun, moon)
    assert 1 <= t <= 30
    assert panchang.karana(sun, moon) in (2 * t - 2, 2 * t - 1)
    assert 1 <= panchang.yoga(sun, moon) <= 27


def _elongation(jd: float) -> float:
    sun = ephemeris.body_longitude(jd, Graha.SUN, DEFAULT)
    moon = ephemeris.body_longitude(jd, Graha.MOON, DEFAULT)
    return arc(sun, moon)


@settings(max_examples=40, deadline=None)
@given(jd=JD)
def test_tithi_end_within_a_day_and_a_half(jd: float) -> None:
    end = panchang.find_end(_elongation, jd, 12.0)
    assert jd < end < jd + 1.5
    assert panchang.tithi(0.0, _elongation(end + 1e-4)) != panchang.tithi(0.0, _elongation(jd))
