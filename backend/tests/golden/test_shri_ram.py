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
