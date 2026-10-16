"""Ashtakavarga: Bhinnashtakavarga (BAV) and Sarvashtakavarga (SAV), BPHS Ch 66."""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import cache
from importlib import resources

from vedic_engine.constants import SEVEN, Graha

CONTRIBUTORS: tuple[str, ...] = (*(g.value for g in SEVEN), "lagna")


@cache
def _table() -> dict[str, dict[str, tuple[int, ...]]]:
    """Benefic houses per target graha and contributor (BPHS Ch 66 verses 43-60)."""
    text = (
        resources.files("vedic_engine").joinpath("data/ashtakavarga_bphs.json").read_text("utf-8")
    )
    raw = json.loads(text)
    return {g.value: {c: tuple(raw[g.value][c]) for c in CONTRIBUTORS} for g in SEVEN}


def bav(signs: Mapping[str, int]) -> dict[Graha, tuple[int, ...]]:
    """Bindus per rashi (index 0..11) in each of Su..Sa's Bhinnashtakavarga.

    ``signs`` maps the seven graha values plus ``"lagna"`` to a rashi index 0..11.
    A contributor in rashi c whose benefic house is h gives a bindu to rashi (c + h - 1) % 12.
    """
    table = _table()
    result: dict[Graha, tuple[int, ...]] = {}
    for target in SEVEN:
        bindus = [0] * 12
        for contributor, houses in table[target.value].items():
            base = signs[contributor]
            for house in houses:
                bindus[(base + house - 1) % 12] += 1
        result[target] = tuple(bindus)
    return result


def sav(bav_table: Mapping[Graha, tuple[int, ...]]) -> tuple[int, ...]:
    """Sarvashtakavarga: per-rashi sum of the seven BAVs."""
    return tuple(sum(bav_table[g][r] for g in SEVEN) for r in range(12))
