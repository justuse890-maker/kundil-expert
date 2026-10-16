"""Birth-time sensitivity (spec 5.11)."""

import math
from collections.abc import Callable
from pathlib import Path

import pytest

from chart_fixtures import birth_of, load_chart
from vedic_engine import ephemeris
from vedic_engine.angles import nak_of, sign_of
from vedic_engine.constants import Graha
from vedic_engine.models import BirthInput, Settings
from vedic_engine.sensitivity import (
    SEARCH_MINUTES,
    WARN_MINUTES,
    SensitivityItem,
    sensitivity,
)
from vedic_engine.timeutil import jd_from_utc, to_utc
from vedic_engine.varga import varga_sign

DEFAULT = Settings()
MINUTE = 1.0 / 1440.0
# The bisection resolves a change to 1 s; probe 2 s either side of the reported instant.
PROBE = 2.0 / 86400.0
ITEMS = ("lagna", "moon_nakshatra_pada", "d9_lagna", "d10_lagna")


@pytest.fixture(autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


def _value_fns(b: BirthInput) -> dict[str, Callable[[float], object]]:
    def asc(t: float) -> float:
        return ephemeris.ascendant(t, b.lat, b.lon)

    return {
        "lagna": lambda t: sign_of(asc(t)),
        "moon_nakshatra_pada": lambda t: nak_of(ephemeris.body_longitude(t, Graha.MOON, DEFAULT)),
        "d9_lagna": lambda t: varga_sign(asc(t), 9),
        "d10_lagna": lambda t: varga_sign(asc(t), 10),
    }


def _jd(b: BirthInput) -> float:
    return jd_from_utc(to_utc(b.local, b.tz, b.fold))


def _by_name(items: tuple[SensitivityItem, ...]) -> dict[str, SensitivityItem]:
    return {i.item: i for i in items}


def test_sensitivity_flags_boundary_chart() -> None:
    # Lagna ~1.4 arcmin after the start of Simha: it changed seconds before birth.
    items, warnings = sensitivity(birth_of(load_chart("varanasi_1984_lagna_boundary")), DEFAULT)
    lagna = _by_name(items)["lagna"]
    assert 0.0 < lagna.minutes_before < 1.0
    assert [w.code for w in warnings] == ["birth_time_sensitive"]
    assert "lagna" in warnings[0].message


def test_moon_boundary_chart_flagged() -> None:
    # Moon ~1 arcmin into Ashlesha: it entered about two minutes before birth.
    items, warnings = sensitivity(birth_of(load_chart("toronto_1971_moon_boundary")), DEFAULT)
    moon = _by_name(items)["moon_nakshatra_pada"]
    assert 0.0 < moon.minutes_before < WARN_MINUTES
    assert [w.code for w in warnings] == ["birth_time_sensitive"]


def test_items_in_spec_order() -> None:
    items, _ = sensitivity(birth_of(load_chart("new_delhi_1947")), DEFAULT)
    assert tuple(i.item for i in items) == ITEMS


@pytest.mark.parametrize(
    "chart", ["new_delhi_1947", "london_1850", "sydney_1985_dst", "reykjavik_1980", "cairo_2015"]
)
def test_reported_minutes_bracket_the_change(chart: str) -> None:
    b = birth_of(load_chart(chart))
    jd = _jd(b)
    fns = _value_fns(b)
    items, warnings = sensitivity(b, DEFAULT)
    for item in items:
        f = fns[item.item]
        v0 = f(jd)
        for sign, minutes in ((-1.0, item.minutes_before), (1.0, item.minutes_after)):
            if math.isinf(minutes):
                # No change anywhere in the window, sampled every minute.
                assert all(f(jd + sign * k * MINUTE) == v0 for k in range(1, SEARCH_MINUTES + 1)), (
                    item
                )
                continue
            assert 0.0 < minutes <= SEARCH_MINUTES
            edge = jd + sign * minutes * MINUTE
            assert f(edge - sign * PROBE) == v0, item
            assert f(edge + sign * PROBE) != v0, item
    nearest = min(min(i.minutes_before, i.minutes_after) for i in items)
    assert (nearest <= WARN_MINUTES) == bool(warnings)
