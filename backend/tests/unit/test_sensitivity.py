"""Birth-time sensitivity (spec 5.11, Ruling R28)."""

import math
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from chart_fixtures import birth_of, load_chart
from vedic_engine import ephemeris
from vedic_engine.angles import nak_of, sign_of
from vedic_engine.constants import Graha
from vedic_engine.models import BirthInput, EngineWarning, Settings
from vedic_engine.panchang import elements_at, tithi
from vedic_engine.sensitivity import (
    SEARCH_MINUTES,
    SENSITIVE_MINUTES_PRIMARY,
    SENSITIVE_MINUTES_VARGA,
    SensitivityItem,
    sensitive_items,
    sensitivity,
)
from vedic_engine.timeutil import jd_from_utc, to_utc, utc_from_jd
from vedic_engine.varga import varga_sign

DEFAULT = Settings()
MINUTE = 1.0 / 1440.0
# The bisection resolves a change to 1 s; probe 2 s either side of the reported instant.
PROBE = 2.0 / 86400.0
ITEMS = ("lagna", "moon_nakshatra_pada", "tithi", "d9_lagna", "d10_lagna")
PRIMARY = ("lagna", "moon_nakshatra_pada", "tithi")
VARGA = ("d9_lagna", "d10_lagna")


@pytest.fixture(autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


def _value_fns(b: BirthInput) -> dict[str, Callable[[float], object]]:
    def asc(t: float) -> float:
        return ephemeris.ascendant(t, b.lat, b.lon, DEFAULT)

    def lon(t: float, g: Graha) -> float:
        return ephemeris.body_longitude(t, g, DEFAULT)

    return {
        "lagna": lambda t: sign_of(asc(t)),
        "moon_nakshatra_pada": lambda t: nak_of(lon(t, Graha.MOON)),
        "tithi": lambda t: tithi(lon(t, Graha.SUN), lon(t, Graha.MOON)),
        "d9_lagna": lambda t: varga_sign(asc(t), 9),
        "d10_lagna": lambda t: varga_sign(asc(t), 10),
    }


def _jd(b: BirthInput) -> float:
    return jd_from_utc(to_utc(b.local, b.tz, b.fold))


def _by_name(items: tuple[SensitivityItem, ...]) -> dict[str, SensitivityItem]:
    return {i.item: i for i in items}


def _expected_triggers(items: tuple[SensitivityItem, ...]) -> tuple[str, ...]:
    """R28 restated independently: primary items within 5 min, D9/D10 lagna within 1 min."""
    out = []
    for i in items:
        limit = 5.0 if i.item in PRIMARY else 1.0
        if min(i.minutes_before, i.minutes_after) <= limit:
            out.append(i.item)
    return tuple(out)


def _warned_items(warnings: tuple[EngineWarning, ...]) -> tuple[str, ...]:
    """Items named by the birth_time_sensitive warning (the list before the colon)."""
    sensitive = [w for w in warnings if w.code == "birth_time_sensitive"]
    if not sensitive:
        return ()
    assert len(sensitive) == 1
    return tuple(sensitive[0].message.split(":", 1)[0].split(", "))


def _check(chart: str) -> tuple[dict[str, SensitivityItem], tuple[str, ...]]:
    items, warnings = sensitivity(birth_of(load_chart(chart)), DEFAULT)
    triggers = sensitive_items(items)
    assert triggers == _expected_triggers(items)
    assert _warned_items(warnings) == triggers
    return _by_name(items), triggers


def test_thresholds() -> None:
    assert (SENSITIVE_MINUTES_PRIMARY, SENSITIVE_MINUTES_VARGA) == (5, 1)


def test_sensitivity_flags_boundary_chart() -> None:
    # Lagna ~1.4 arcmin after the start of Simha (also a D9 and D10 edge): changed seconds ago.
    items, triggers = _check("varanasi_1984_lagna_boundary")
    assert triggers == ("lagna", "d9_lagna", "d10_lagna")
    assert 0.0 < items["lagna"].minutes_before < 1.0


def test_moon_boundary_chart_flagged() -> None:
    # Moon ~1 arcmin into Ashlesha: it entered about two minutes before birth.
    items, triggers = _check("toronto_1971_moon_boundary")
    assert triggers == ("moon_nakshatra_pada",)
    assert 1.0 < items["moon_nakshatra_pada"].minutes_before < SENSITIVE_MINUTES_PRIMARY


def test_india_1947_tithi_triggers_but_not_d9_d10() -> None:
    items, triggers = _check("new_delhi_1947")
    assert triggers == ("tithi",)
    # The tithi ends ~34 s after birth, the same instant panchang reports as its end time.
    b = birth_of(load_chart("new_delhi_1947"))
    jd = _jd(b)
    ends = elements_at(jd, b.lat, b.lon, b.alt, DEFAULT).tithi.ends_utc
    seconds = (ends - utc_from_jd(jd)).total_seconds()
    assert 33.0 < seconds < 35.0
    assert abs(items["tithi"].minutes_after * 60.0 - seconds) <= 1.0
    # D9 changed ~3.9 min before and D10 changes ~4.6 min after: inside 5, outside 1 minute.
    assert SENSITIVE_MINUTES_VARGA < items["d9_lagna"].minutes_before < SENSITIVE_MINUTES_PRIMARY
    assert SENSITIVE_MINUTES_VARGA < items["d10_lagna"].minutes_after < SENSITIVE_MINUTES_PRIMARY


def test_insensitive_golden_chart_has_no_warning() -> None:
    items, warnings = sensitivity(birth_of(load_chart("auckland_2010_dst")), DEFAULT)
    assert sensitive_items(items) == ()
    assert warnings == ()
    for i in items:
        nearest = min(i.minutes_before, i.minutes_after)
        assert nearest > (SENSITIVE_MINUTES_PRIMARY if i.item in PRIMARY else 1.0)


def test_items_in_spec_order() -> None:
    items, _ = sensitivity(birth_of(load_chart("new_delhi_1947")), DEFAULT)
    assert tuple(i.item for i in items) == ITEMS


def test_range_edge_distinguished_from_no_change() -> None:
    # One hour after the supported range starts (1800-01-01 06:00 UT): the backward search
    # stops at the range edge after 60 minutes.
    b = BirthInput(datetime(1800, 1, 1, 7, 0), "UTC", 51.5, 0.0)
    items, _ = sensitivity(b, DEFAULT)
    edged = [i for i in items if i.edge_before]
    assert edged, "some item must run into the range start"
    for i in items:
        assert not i.edge_after
        assert i.edge_before == math.isinf(i.minutes_before)
        if not i.edge_before:
            assert i.minutes_before <= 60.0
    # A mid-range birth reports plain "no change in window": inf without the edge flag.
    far, _ = sensitivity(birth_of(load_chart("new_delhi_1947")), DEFAULT)
    tithi_item = _by_name(far)["tithi"]
    assert math.isinf(tithi_item.minutes_before) and not tithi_item.edge_before
    assert not any(i.edge_before or i.edge_after for i in far)


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
    assert _warned_items(warnings) == _expected_triggers(items)
