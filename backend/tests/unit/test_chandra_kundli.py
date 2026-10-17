"""Chandra kundli for an unknown birth time (Task 16)."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vedic_engine import ephemeris
from vedic_engine.angles import nak_of, sign_of
from vedic_engine.constants import NAKSHATRAS, Graha
from vedic_engine.kundli import Kundli, build_kundli
from vedic_engine.models import BirthInput, Settings
from vedic_engine.timeutil import jd_from_utc

DELHI_1947 = BirthInput(
    datetime(1947, 8, 15, 0, 0), "Asia/Kolkata", 28.6139, 77.2090, time_known=False
)
KARKA = 3


@pytest.fixture(autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


def _codes(k: Kundli) -> dict[str, str]:
    return {w.code: w.message for w in k.warnings}


def test_lagna_is_the_moon_and_time_dependent_outputs_are_omitted() -> None:
    k = build_kundli(DELHI_1947)
    moon = k.grahas[Graha.MOON].lon
    assert sign_of(k.lagna_lon) == KARKA == sign_of(moon)
    assert k.lagna_lon == moon
    assert k.bhavas[0] == KARKA
    assert k.meta["lagna_basis"] == "moon"
    assert k.meta["time_known"] is False
    assert k.shadbala is None
    assert k.sensitivity == ()
    assert "time_unknown" in _codes(k)
    assert "approximate" in _codes(k)["time_unknown"]
    assert "birth_time_sensitive" not in _codes(k)


def test_positions_are_those_of_local_noon() -> None:
    noon = build_kundli(replace(DELHI_1947, local=datetime(1947, 8, 15, 12, 0), time_known=True))
    unknown = build_kundli(DELHI_1947)
    assert unknown.meta["jd_ut"] == noon.meta["jd_ut"]
    assert unknown.grahas == noon.grahas
    assert unknown.panchang == noon.panchang
    assert unknown.vimshottari == noon.vimshottari


def test_moon_nakshatra_uncertain_lists_every_pada_of_the_day() -> None:
    k = build_kundli(DELHI_1947)
    msg = _codes(k)["moon_nakshatra_uncertain"]
    # Independent hourly sampling over the local civil day (IST = UTC+5:30).
    start = jd_from_utc(datetime(1947, 8, 14, 18, 30, tzinfo=UTC))
    day_naks = {
        nak_of(ephemeris.body_longitude(start + h / 24.0, Graha.MOON, Settings()))[0]
        for h in range(24)
    }
    assert len(day_naks) >= 2  # the Moon changes nakshatra on this day
    for nak in day_naks:
        assert NAKSHATRAS[nak] in msg
    assert "approximate" in msg


def test_known_time_kundli_is_unchanged_in_shape() -> None:
    k = build_kundli(replace(DELHI_1947, time_known=True))
    assert k.meta["lagna_basis"] == "ascendant"
    assert k.meta["time_known"] is True
    assert k.shadbala is not None
    assert len(k.sensitivity) > 0
    assert "time_unknown" not in _codes(k)
