"""Shri Ram fixed-placement fixture (spec 1 corrections, spec 9 item 4)."""

import json
from pathlib import Path
from typing import Any

import pytest

from vedic_engine.constants import NAKSHATRAS, RASHIS, Graha
from vedic_engine.dignity import Dignity
from vedic_engine.kundli import PartialKundli, chart_from_placements

pytestmark = pytest.mark.golden

FIXTURE = Path(__file__).resolve().parent.parent.parent / "fixtures" / "golden" / "shri_ram.json"


def _load() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text())
    return data


def _lon(p: dict[str, Any]) -> float:
    return RASHIS.index(p["rashi"]) * 30.0 + float(p["deg"])


@pytest.fixture(scope="module")
def chart() -> PartialKundli:
    placements = _load()["placements"]
    lons = {Graha(k): _lon(v) for k, v in placements.items() if k != "lagna"}
    return chart_from_placements(_lon(placements["lagna"]), lons)


def test_fixture_provenance() -> None:
    data = _load()
    assert "Bala Kanda 18.8-9" in data["source"]
    assert data["verified_by"]


def test_shri_ram(chart: PartialKundli) -> None:
    exalted = {g for g, d in chart.dignity.items() if d is Dignity.EXALTED}
    assert exalted == {Graha.SUN, Graha.MARS, Graha.JUPITER, Graha.VENUS, Graha.SATURN}
    assert chart.dignity[Graha.MOON] is Dignity.OWN
    assert chart.vargas[1]["moon"] == chart.vargas[1]["jupiter"] == RASHIS.index("karka")
    assert chart.vargas[1]["lagna"] == RASHIS.index("karka")
    assert chart.maha_lord is Graha.JUPITER
    assert 0.0 < chart.balance_years <= 4.0
    assert chart.syllable[0] == "Hi"


def test_moon_in_punarvasu_pada_4(chart: PartialKundli) -> None:
    assert NAKSHATRAS[chart.nakshatra] == "punarvasu"
    assert chart.pada == 4


def test_all_vargas_present(chart: PartialKundli) -> None:
    from vedic_engine.varga import VARGAS

    assert set(chart.vargas) == set(VARGAS)
    assert all(
        set(v) == {*(g.value for g in chart.dignity), "lagna"} for v in chart.vargas.values()
    )


def test_house_facts(chart: PartialKundli) -> None:
    # Karka lagna; houses by sign: Moon and Jupiter in Karka (1), Saturn in Tula (4), Mars in
    # Makara (7), Venus in Meena (9), Sun in Mesha (10), Mercury in Vrishabha (11).
    h = chart.bhavas_detail
    assert len(h) == 12 and h[0].rashi == RASHIS.index("karka")
    assert h[0].lord is Graha.MOON and h[0].lord_house == 1
    assert h[0].occupants == (Graha.MOON, Graha.JUPITER)
    placed = {g: f.house for f in h for g in f.occupants}
    assert placed == {
        Graha.MOON: 1, Graha.JUPITER: 1, Graha.SATURN: 4, Graha.MARS: 7, Graha.VENUS: 9,
        Graha.SUN: 10, Graha.MERCURY: 11,
    }  # fmt: skip
    # Mars (Makara, house 7) aspects the 4th, 7th and 8th signs from it: Mesha, Karka, Simha;
    # Saturn (Tula, house 4) the 3rd, 7th and 10th: Dhanu, Mesha, Karka.
    assert Graha.MARS in h[0].aspected_by and Graha.SATURN in h[0].aspected_by
    assert h[9].aspected_by == (Graha.MARS, Graha.SATURN)  # Mesha, house 10


def test_vargottama(chart: PartialKundli) -> None:
    # Hand-worked D9: Moon 1 deg Karka (movable, 1st navamsa = Karka), Venus 27 deg Meena
    # (dual, 9th navamsa counted from Karka = Meena) and Mercury 15 deg Vrishabha (fixed, 5th
    # navamsa counted from Makara = Vrishabha) are vargottama; the other four are not.
    assert chart.vargottama == {
        Graha.SUN: False, Graha.MOON: True, Graha.MARS: False, Graha.MERCURY: True,
        Graha.JUPITER: False, Graha.VENUS: True, Graha.SATURN: False,
    }  # fmt: skip
