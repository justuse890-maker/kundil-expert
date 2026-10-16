"""House facts for the House screen: bhava table, graha drishti, bhava karakas, vargottama.

Facts only, no interpretation. Everything is whole-sign (spec 5.3): house 1 is the lagna rashi
in full and a graha's house is the house of the sign it stands in.

* Drishti is the whole-sign Parashari graha drishti (BPHS Ch 26): every graha aspects the 7th
  sign from its own; Mars also the 4th and 8th, Jupiter the 5th and 9th, Saturn the 3rd and
  10th. "Aspects the nth" means the sign ``(from_sign + n - 1) % 12``. Rahu and Ketu aspect
  nothing unless ``NODE_ASPECTS_SCHOOL`` is switched to "5-7-9" (school dependent, off).
* The natural bhava karakas are ``data/karakas.json`` (BPHS Ch 32 vv. 31-34, Santhanam).
* Vargottama: the D1 sign equals the D9 sign.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib import resources

from vedic_engine.angles import sign_of
from vedic_engine.constants import RASHI_LORD, Graha
from vedic_engine.lagna import house_of
from vedic_engine.varga import varga_sign

# School dependent: "none" (default; Rahu and Ketu cast no drishti) or "5-7-9" (they aspect the
# 5th, 7th and 9th signs like Jupiter). Read at call time, so tests may monkeypatch it.
NODE_ASPECTS_SCHOOL = "none"
NODE_ASPECTS_SCHOOLS = ("none", "5-7-9")

_ASPECT_SEVENTH: tuple[int, ...] = (7,)
_ASPECTS: dict[Graha, tuple[int, ...]] = {
    Graha.MARS: (4, 7, 8),
    Graha.JUPITER: (5, 7, 9),
    Graha.SATURN: (3, 7, 10),
}
_NODE_ASPECTS: dict[str, tuple[int, ...]] = {"none": (), "5-7-9": (5, 7, 9)}
_NODES = (Graha.RAHU, Graha.KETU)


@dataclass(frozen=True, slots=True)
class BhavaFact:
    """One row of the bhava table; ``rashi`` is 0-11, ``house`` and ``lord_house`` are 1-12."""

    house: int
    rashi: int
    lord: Graha
    lord_house: int
    occupants: tuple[Graha, ...]
    aspected_by: tuple[Graha, ...]
    karakas: tuple[Graha, ...]


def drishti(graha: Graha, from_sign: int) -> tuple[int, ...]:
    """Signs (0-11) aspected by ``graha`` standing in ``from_sign``, in order of aspect number."""
    if NODE_ASPECTS_SCHOOL not in _NODE_ASPECTS:
        raise ValueError(
            f"NODE_ASPECTS_SCHOOL must be one of {NODE_ASPECTS_SCHOOLS}, "
            f"got {NODE_ASPECTS_SCHOOL!r}"
        )
    numbers = (
        _NODE_ASPECTS[NODE_ASPECTS_SCHOOL]
        if graha in _NODES
        else _ASPECTS.get(graha, _ASPECT_SEVENTH)
    )
    return tuple((from_sign + n - 1) % 12 for n in numbers)


@cache
def _karakas() -> dict[int, tuple[Graha, ...]]:
    """Natural bhava karakas per house 1-12 (BPHS Ch 32 vv. 31-34)."""
    text = resources.files("vedic_engine").joinpath("data/karakas.json").read_text("utf-8")
    houses = json.loads(text)["houses"]
    return {h: tuple(Graha(k) for k in houses[str(h)]) for h in range(1, 13)}


def bhava_facts(lagna_lon: float, lons: Mapping[Graha, float]) -> tuple[BhavaFact, ...]:
    """The twelve bhava rows, house 1 first.

    ``lons`` are sidereal longitudes and must include the seven classical grahas (every house
    lord is looked up in it); Rahu and Ketu are optional. ``occupants`` and ``aspected_by`` are in
    ``Graha`` enum order; ``aspected_by`` lists the grahas whose drishti falls on the house sign.
    """
    lagna_sign = sign_of(lagna_lon)
    signs = {g: sign_of(lon) for g, lon in lons.items()}
    graha_order = [g for g in Graha if g in signs]
    karakas = _karakas()
    facts: list[BhavaFact] = []
    for house in range(1, 13):
        rashi = (lagna_sign + house - 1) % 12
        lord = RASHI_LORD[rashi]
        facts.append(
            BhavaFact(
                house=house,
                rashi=rashi,
                lord=lord,
                lord_house=house_of(signs[lord], lagna_sign),
                occupants=tuple(g for g in graha_order if signs[g] == rashi),
                aspected_by=tuple(g for g in graha_order if rashi in drishti(g, signs[g])),
                karakas=karakas[house],
            )
        )
    return tuple(facts)


def vargottama(lons: Mapping[Graha, float]) -> dict[Graha, bool]:
    """True for each graha whose D1 sign equals its D9 sign."""
    return {g: varga_sign(lon, 1) == varga_sign(lon, 9) for g, lon in lons.items()}
