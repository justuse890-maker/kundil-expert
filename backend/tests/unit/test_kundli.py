"""Kundli orchestrator (spec 3, 4, 8)."""

import dataclasses
import json
from datetime import date, datetime
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from vedic_engine import __version__, ephemeris
from vedic_engine.angles import nak_of, sign_of
from vedic_engine.bhava import BhavaFact
from vedic_engine.constants import RASHIS, SEVEN, Graha
from vedic_engine.dasha.vimshottari import balance
from vedic_engine.dignity import Dignity
from vedic_engine.kundli import Kundli, build_kundli
from vedic_engine.models import BirthInput, Settings
from vedic_engine.names import syllable
from vedic_engine.varga import VARGAS, varga_sign

# Mean Rahu in sidereal Vrishabha (its default exaltation sign), Ketu in Vrishchika.
DELHI_1947 = BirthInput(datetime(1947, 8, 15, 0, 0), "Asia/Kolkata", 28.6139, 77.2090)
# Mean Rahu in Mithuna, Ketu in Dhanu: no node exaltation or debilitation.
DELHI_2002 = BirthInput(datetime(2002, 1, 1, 12, 0), "Asia/Kolkata", 28.6139, 77.2090)
# 70 N on the June solstice: polar latitude and midnight sun.
POLAR = BirthInput(datetime(2000, 6, 21, 12, 0), "Europe/Oslo", 70.0, 25.0)


@pytest.fixture(autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


@cache
def _build(b: BirthInput) -> Kundli:
    return build_kundli(b)


def _jsonable(x: Any) -> Any:
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        return {f.name: _jsonable(getattr(x, f.name)) for f in dataclasses.fields(x)}
    if isinstance(x, Enum):
        return x.value
    if isinstance(x, dict):
        return {str(_jsonable(k)): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (datetime, date)):
        return x.isoformat()
    return x


def _serialise(k: Kundli) -> str:
    return json.dumps(_jsonable(k), sort_keys=True, ensure_ascii=False)


def _codes(k: Kundli) -> list[str]:
    return [w.code for w in k.warnings]


def test_kundli_deterministic() -> None:
    a = _serialise(build_kundli(DELHI_1947))
    b = _serialise(build_kundli(DELHI_1947))
    assert a == b
    assert '"vimshottari"' in a and '"shadbala"' in a
    assert '"bhavas_detail"' in a and '"vargottama"' in a
    detail = json.loads(a)["bhavas_detail"]
    assert detail[0]["lord"] == "venus" and detail[0]["occupants"] == ["rahu"]  # enums as values
    assert json.loads(a)["vargottama"].keys() == {g.value for g in Graha}


def test_meta() -> None:
    k = _build(DELHI_1947)
    assert set(k.meta) == {
        "engine_version",
        "settings",
        "ayanamsa_deg",
        "jd_ut",
        "time_known",
        "lagna_basis",
        "ephemeris_files",
    }
    assert k.meta["engine_version"] == __version__
    assert k.meta["settings"] == dataclasses.asdict(Settings())
    assert k.meta["ephemeris_files"] == list(ephemeris.EPHE_FILES)
    assert k.meta["ayanamsa_deg"] == ephemeris.ayanamsa(k.meta["jd_ut"], Settings())


def test_composes_the_modules() -> None:
    k = _build(DELHI_1947)
    moon = k.grahas[Graha.MOON].lon
    assert set(k.grahas) == set(Graha)
    assert k.bhavas[0] == sign_of(k.lagna_lon) and len(k.bhavas) == 12
    assert set(k.vargas) == set(VARGAS)
    assert k.vargas[1] == {
        **{g.value: sign_of(p.lon) for g, p in k.grahas.items()},
        "lagna": sign_of(k.lagna_lon),
    }
    assert set(k.dignity) == set(k.combust) == set(k.avastha) == set(Graha)
    assert set(k.shadbala) == set(SEVEN)
    assert k.vimshottari[0].lord == balance(moon)[0].value
    assert max(_depth(p) for p in k.vimshottari) == 3
    assert max(_depth(p) for p in k.yogini) == 3
    assert sum(k.ashtakavarga["sav"]) == 337
    assert set(k.ashtakavarga["bav"]) == set(SEVEN)
    assert k.name_syllable == syllable(*nak_of(moon))
    assert tuple(i.item for i in k.sensitivity) == (
        "lagna", "moon_nakshatra_pada", "tithi", "d9_lagna", "d10_lagna",
    )  # fmt: skip


def test_house_facts_for_india_1947() -> None:
    k = _build(DELHI_1947)
    h = k.bhavas_detail
    assert len(h) == 12 and all(isinstance(f, BhavaFact) for f in h)
    assert [f.rashi for f in h] == list(k.bhavas)
    assert (h[0].rashi, h[0].lord, h[0].lord_house) == (RASHIS.index("vrishabha"), Graha.VENUS, 3)
    assert h[0].occupants == (Graha.RAHU,)  # mean Rahu in the lagna sign
    assert h[1].occupants == (Graha.MARS,)
    assert h[2].occupants == (Graha.SUN, Graha.MOON, Graha.MERCURY, Graha.VENUS, Graha.SATURN)
    assert h[5].occupants == (Graha.JUPITER,)
    assert h[6].occupants == (Graha.KETU,)
    assert h[8].aspected_by == (
        Graha.SUN,
        Graha.MOON,
        Graha.MARS,
        Graha.MERCURY,
        Graha.VENUS,
        Graha.SATURN,
    )


def test_house_facts_invariants_on_every_test_chart() -> None:
    for b in (DELHI_1947, DELHI_2002, POLAR):
        k = _build(b)
        assert sorted(g for f in k.bhavas_detail for g in f.occupants) == sorted(Graha)
        assert all(1 <= f.lord_house <= 12 and f.karakas for f in k.bhavas_detail)


def test_vargottama_matches_d1_d9() -> None:
    for b in (DELHI_1947, DELHI_2002):
        k = _build(b)
        assert set(k.vargottama) == set(Graha)
        for g, p in k.grahas.items():
            assert k.vargottama[g] == (varga_sign(p.lon, 1) == varga_sign(p.lon, 9))
            # consistent with the stored D1 and D9 charts
            assert k.vargottama[g] == (k.vargas[1][g.value] == k.vargas[9][g.value])


def _depth(p: Any) -> int:
    return 1 + max((_depth(c) for c in p.children), default=0)


def test_vargas_and_depth_arguments() -> None:
    k = build_kundli(DELHI_1947, vargas=(1, 9), dasha_depth=1)
    assert set(k.vargas) == {1, 9}
    assert all(not p.children for p in k.vimshottari)


def test_polar_warning() -> None:
    k = _build(POLAR)
    assert "polar_latitude" in _codes(k)
    # Shadbala's polar sunrise warning reaches the kundli (Ruling R26).
    assert "polar_sunrise" in _codes(k)


def test_no_polar_warning_below_66_5() -> None:
    assert "polar_latitude" not in _codes(_build(DELHI_1947))
    assert "polar_sunrise" not in _codes(_build(DELHI_1947))


def test_node_dignity_flagged() -> None:
    k = _build(DELHI_1947)
    assert k.dignity[Graha.RAHU] is Dignity.EXALTED
    assert k.dignity[Graha.KETU] is Dignity.EXALTED  # Vrishchika, the default Ketu exaltation
    assert "school_dependent" in _codes(k)


def test_node_dignity_not_flagged_when_neutral() -> None:
    k = _build(DELHI_2002)
    assert k.dignity[Graha.RAHU] is Dignity.NEUTRAL
    assert k.dignity[Graha.KETU] is Dignity.NEUTRAL
    assert "school_dependent" not in _codes(k)


def test_warnings_sorted_and_unique() -> None:
    for b in (DELHI_1947, DELHI_2002, POLAR):
        k = _build(b)
        keys = [(w.code, w.message) for w in k.warnings]
        assert keys == sorted(set(keys))


def test_no_internal_names_in_any_warning_message() -> None:
    import re

    from chart_fixtures import CHART_PATHS, birth_of, load_chart
    from vedic_engine.kundli import build_kundli

    seen = 0
    for path in CHART_PATHS:
        k = build_kundli(birth_of(load_chart(path)))
        for w in k.warnings:
            seen += 1
            assert not re.search(r"\b[a-z]+_[a-z0-9_]+\b", w.message), w.message
            assert not re.search(r"\b[A-Z]{2,}(?:_[A-Z]+)+\b", w.message), w.message
    assert seen > 5
