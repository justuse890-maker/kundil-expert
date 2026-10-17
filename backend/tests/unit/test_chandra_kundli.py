"""Chandra kundli for an unknown birth time (Task 16)."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vedic_engine import ephemeris
from vedic_engine import kundli as kundli_mod
from vedic_engine.angles import nak_of, sign_of
from vedic_engine.constants import NAKSHATRAS, Graha
from vedic_engine.kundli import Kundli, build_kundli
from vedic_engine.models import BirthInput, Settings
from vedic_engine.timeutil import NonexistentTimeError, jd_from_utc

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


def test_pada_only_change_gives_no_nakshatra_warning() -> None:
    # 2024-01-31 (IST): the Moon stays in one nakshatra all day (hourly-sampled check below)
    b = replace(DELHI_1947, local=datetime(2024, 1, 31, 0, 0))
    start = jd_from_utc(datetime(2024, 1, 30, 18, 30, tzinfo=UTC))
    cells = {
        nak_of(ephemeris.body_longitude(start + h / 48.0, Graha.MOON, Settings()))
        for h in range(48)
    }
    assert len({n for n, _ in cells}) == 1 and len(cells) > 1  # pada changes, nakshatra not
    assert "moon_nakshatra_uncertain" not in _codes(build_kundli(b))


def test_time_of_day_is_ignored_when_time_unknown() -> None:
    a = build_kundli(DELHI_1947)
    b = build_kundli(replace(DELHI_1947, local=datetime(1947, 8, 15, 18, 0)))
    assert a == b


def test_manglik_from_lagna_is_dropped_for_chandra_lagna() -> None:
    k = build_kundli(DELHI_1947)
    assert k.manglik.from_lagna is None
    assert "lagna_is_moon" in _codes(k)
    known = build_kundli(replace(DELHI_1947, time_known=True))
    assert isinstance(known.manglik.from_lagna, bool)
    assert "lagna_is_moon" not in _codes(known)


def test_dst_gap_at_noon_uses_thirteen_hundred(monkeypatch: pytest.MonkeyPatch) -> None:
    real = kundli_mod.to_utc

    def gap_at_noon(local: datetime, tz: str, fold: int | None = None) -> datetime:
        if local.hour == 12 and local.minute == 0:
            raise NonexistentTimeError("synthetic DST gap")
        return real(local, tz, fold)

    monkeypatch.setattr(kundli_mod, "to_utc", gap_at_noon)
    k = build_kundli(DELHI_1947)
    expected = jd_from_utc(datetime(1947, 8, 15, 13, 0).replace(tzinfo=UTC)) - 5.5 / 24
    assert k.meta["jd_ut"] == pytest.approx(expected)
    assert "13:00" in _codes(k)["time_unknown"]


def test_lmt_and_fixed_offset_kundlis_build() -> None:
    lmt = build_kundli(
        BirthInput(datetime(1900, 1, 1, 12, 0), "Asia/Kolkata", 22.57, 88.3639, lmt=True)
    )
    fixed = build_kundli(BirthInput(datetime(1900, 1, 1, 12, 0), "UTC+05:53:20", 22.57, 88.3639))
    # LMT is 5:53:27.336 vs the fixed 5:53:20: the LMT instant is 7.336 s earlier
    assert fixed.meta["jd_ut"] - lmt.meta["jd_ut"] == pytest.approx(7.336 / 86400.0, abs=1e-8)
    assert lmt.shadbala is not None and fixed.shadbala is not None
    assert sign_of(lmt.lagna_lon) == sign_of(fixed.lagna_lon)
