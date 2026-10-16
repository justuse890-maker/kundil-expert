"""Golden check: Shadbala of B. V. Raman's worked example (Graha and Bhava Balas, 2nd ed. 1942).

The example's own printed inputs (longitudes, cusps, ayanamsa, times, ahargana, mean longitudes
and seeghrochchas) go into ``shadbala_from_inputs``, so this checks the formulas, not the
ephemeris. Every printed component must agree within SHADBALA_VIRUPA. Source, pages and the
book's misprints are recorded in fixtures/golden/shadbala_bphs_example.json.
"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tolerances import SHADBALA_VIRUPA
from vedic_engine.constants import SEVEN, Graha
from vedic_engine.shadbala import (
    ShadbalaInputs,
    ShadbalaRow,
    ahargana_lords,
    raman_mean_positions,
    shadbala_from_inputs,
)

pytestmark = pytest.mark.golden

FIXTURE = (
    Path(__file__).resolve().parent.parent.parent
    / "fixtures"
    / "golden"
    / "shadbala_bphs_example.json"
)
DATA: dict[str, Any] = json.loads(FIXTURE.read_text("utf-8"))
INP: dict[str, Any] = DATA["inputs"]
PRINTED: dict[str, Any] = DATA["printed"]

TOP_LEVEL = ("sthana", "dig", "kaala", "cheshta", "naisargika", "drik", "total_virupa")
SUB = (
    "uchcha", "saptavargaja", "ojhayugma", "kendradi", "drekkana",
    "natonnata", "paksha", "tribhaga", "abda", "masa", "vara", "hora", "ayana", "yuddha",
)  # fmt: skip


def _dm(v: list[int]) -> float:
    return v[0] + v[1] / 60.0


def _inputs() -> ShadbalaInputs:
    ahas = _dm(INP["ahas_ghati"])
    birth = _dm(INP["birth_ghati_after_sunrise"])
    lon = {g: _dm(INP["longitudes_dm"][g.value]) for g in SEVEN}
    return ShadbalaInputs(
        lon=lon,
        asc=_dm(INP["ascendant_dm"]),
        mc=_dm(INP["midheaven_dm"]),
        ayanamsa=_dm(INP["ayanamsa_dm"]),
        apparent_hours=_dm(INP["apparent_time_from_midnight_hm"]),
        is_day=INP["is_day"],
        part_elapsed=birth / ahas,
        hours_from_sunrise=birth / 2.5,  # 1 hour = 2.5 ghatis
        ahargana=INP["ahargana"],
        mean_lon={g: INP["mean_longitudes"][g.value] for g in SEVEN[2:]},
        seeghrochcha={g: INP["seeghrochcha"][g.value] for g in SEVEN[2:]},
    )


@pytest.fixture(scope="module")
def rows() -> dict[Graha, ShadbalaRow]:
    return shadbala_from_inputs(_inputs())


def _value(row: ShadbalaRow, name: str) -> float:
    return row.components[name] if name in SUB else float(getattr(row, name))


# Printed values that contradict the book's own rules and tables; see the fixture's
# "errata_noted". Engine minus printed saptavargaja, in virupas:
# * Mars: the p. 22 Trimsamsa column gives Swa (30). Mars at 229 49 (Vrischika 19 49) is in
#   Jupiter's trimsamsa (even sign, 12-20 deg), Sama per p. 17 (7.5). Swa is what the p. 2
#   misprint 299 49 (Makara 29 49, Mars's trimsamsa) gives. Every other Mars varga on p. 22
#   matches 229 49.
# * Saturn: the p. 22 Saptamsa column gives Sama (7.5). Saturn at Simha 4 51 is past the first
#   saptamsa (4 17), so its saptamsa is Kanya, lord Mercury, Adhi Mitra per p. 17 (22.5).
# Sthana and the totals carry the same differences.
KNOWN_MISPRINT = {Graha.MARS: -22.5, Graha.SATURN: 15.0}
_CARRIES_MISPRINT = ("saptavargaja", "sthana", "total_virupa")


def _cases() -> list[Any]:
    cases = []
    for g in SEVEN:
        for name in TOP_LEVEL + SUB:
            marks = []
            if g in KNOWN_MISPRINT and name in _CARRIES_MISPRINT:
                marks = [pytest.mark.xfail(strict=True, reason="book misprint, KNOWN_MISPRINT")]
            cases.append(pytest.param(g, name, marks=marks, id=f"{g.value}-{name}"))
    return cases


@pytest.mark.parametrize(("graha", "name"), _cases())
def test_bphs_example_components(rows: dict[Graha, ShadbalaRow], graha: Graha, name: str) -> None:
    printed = PRINTED[name]["values"][SEVEN.index(graha)]
    got = _value(rows[graha], name)
    assert abs(got - printed) <= SHADBALA_VIRUPA, f"{graha} {name}: {got:.3f} vs {printed}"


@pytest.mark.parametrize("graha", list(KNOWN_MISPRINT), ids=[g.value for g in KNOWN_MISPRINT])
def test_bphs_example_misprints_are_exactly_the_documented_ones(
    rows: dict[Graha, ShadbalaRow], graha: Graha
) -> None:
    for name in _CARRIES_MISPRINT:
        printed = PRINTED[name]["values"][SEVEN.index(graha)]
        diff = _value(rows[graha], name) - printed
        assert abs(diff - KNOWN_MISPRINT[graha]) <= SHADBALA_VIRUPA, f"{graha} {name}: {diff}"


def test_ahargana_lords_of_example() -> None:
    """Raman pp. 43-45: ahargana 33,405 -> year Saturn, month Mercury, day Mercury."""
    assert ahargana_lords(INP["ahargana"]) == (Graha.SATURN, Graha.MERCURY, Graha.MERCURY)


def test_cheshta_from_raman_mean_motions() -> None:
    """Raman's tables (pp. 97-101) reproduce the example's Chesta bala from the interval alone.

    The mean longitudes and seeghrochchas are recomputed from the total interval (p. 64) and
    year; the printed Jupiter mean (66.91) carries a misprinted table entry (800 days printed
    66.58 for 66.48, p. 98), which moves Chesta bala by under 0.02 virupa.
    """
    mean, sighra = raman_mean_positions(INP["total_interval_days"], INP["year"])
    rows = shadbala_from_inputs(replace(_inputs(), mean_lon=mean, seeghrochcha=sighra))
    for g in SEVEN[2:]:
        printed = PRINTED["cheshta"]["values"][SEVEN.index(g)]
        assert abs(rows[g].cheshta - printed) <= SHADBALA_VIRUPA
