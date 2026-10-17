"""Planet strength: a 0-100 score built from classical indicators, each a traceable ``Factor``.

Start at ``BASE`` (50), add every applicable factor, clamp to 0-100. Weights (refs per factor
are in ``data/grahas.json`` under ``strength_factors``):

* ``dignity`` (rashi chart): exalted +25, moolatrikona +20, own +15, great friend +10,
  friend +5, neutral 0, enemy -5, great enemy -10, debilitated -20.
* ``shadbala``: ratio (rupa / required rupa) >= 1: +15, otherwise -10. Rahu and Ketu have no
  Shadbala, so they get no factor.
* ``combust``: -15.
* ``house``: kendra or trikona (1, 4, 5, 7, 9, 10) +10; 6th, 8th or 12th -10.
* ``vargottama``: +10.
* ``d9_dignity``: exalted or own sign in the navamsa +10, debilitated -10 (``d9_dignity``).

Only factors with a non-zero delta are listed. The score counts agreeing indicators; it is not a
probability.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from vedic_engine.analysis.functional import KENDRAS, TRIKONAS, load_data
from vedic_engine.angles import sign_of
from vedic_engine.constants import RASHI_LORD, RASHIS, Graha
from vedic_engine.dignity import EXALT_SIGN, NODE_DIGNITY_SCHOOL, Dignity
from vedic_engine.lagna import house_of

BASE = 50
DIGNITY_DELTA: dict[Dignity, int] = {
    Dignity.EXALTED: 25,
    Dignity.MOOLATRIKONA: 20,
    Dignity.OWN: 15,
    Dignity.GREAT_FRIEND: 10,
    Dignity.FRIEND: 5,
    Dignity.NEUTRAL: 0,
    Dignity.ENEMY: -5,
    Dignity.GREAT_ENEMY: -10,
    Dignity.DEBILITATED: -20,
}
SHADBALA_STRONG = 15
SHADBALA_WEAK = -10
COMBUST = -15
HOUSE_GOOD = 10
HOUSE_BAD = -10
DUSTHANAS = frozenset({6, 8, 12})
VARGOTTAMA = 10
D9_GOOD = 10
D9_BAD = -10


class _HasLon(Protocol):
    @property
    def lon(self) -> float: ...


class _HasRatio(Protocol):
    @property
    def ratio(self) -> float: ...


class ChartFacts(Protocol):
    """The ``Kundli`` fields the analysis reads; test fixtures may supply just these."""

    @property
    def lagna_lon(self) -> float: ...
    @property
    def grahas(self) -> Mapping[Graha, _HasLon]: ...
    @property
    def dignity(self) -> Mapping[Graha, Dignity]: ...
    @property
    def combust(self) -> Mapping[Graha, bool]: ...
    @property
    def shadbala(self) -> Mapping[Graha, _HasRatio]: ...
    @property
    def vargottama(self) -> Mapping[Graha, bool]: ...
    @property
    def vargas(self) -> Mapping[int, Mapping[str, int]]: ...


@dataclass(frozen=True, slots=True)
class Factor:
    name: str
    delta: int
    why: str
    ref: str


@dataclass(frozen=True, slots=True)
class Strength:
    score: int
    factors: tuple[Factor, ...]


def d9_dignity(graha: Graha, d9_sign: int) -> Dignity | None:
    """Dignity by sign alone in the navamsa: EXALTED, DEBILITATED, OWN or None.

    Degrees within a navamsa sign carry no meaning, so moolatrikona and relationships are not
    used; a moolatrikona sign counts as OWN (or EXALTED for the Moon and Mercury, whose
    moolatrikona is their exaltation sign). Rahu and Ketu use ``NODE_DIGNITY_SCHOOL`` and have no
    own sign.
    """
    if graha in (Graha.RAHU, Graha.KETU):
        exalt = NODE_DIGNITY_SCHOOL[graha.value]["exalted"]
    else:
        exalt = EXALT_SIGN[graha]
    if d9_sign == exalt:
        return Dignity.EXALTED
    if d9_sign == (exalt + 6) % 12:
        return Dignity.DEBILITATED
    if RASHI_LORD[d9_sign] == graha:
        return Dignity.OWN
    return None


def graha_house(k: ChartFacts, g: Graha) -> int:
    """Whole-sign house (1-12) of ``g``."""
    return house_of(sign_of(k.grahas[g].lon), sign_of(k.lagna_lon))


def planet_strength(k: ChartFacts, g: Graha) -> Strength:
    refs = load_data("grahas")["strength_factors"]
    name = g.value
    raw: list[tuple[str, int, str]] = []

    dig = k.dignity[g]
    raw.append(("dignity", DIGNITY_DELTA[dig], f"{name} is {dig.value.replace('_', ' ')} in D1"))

    bala = k.shadbala.get(g)
    if bala is not None:
        strong = bala.ratio >= 1.0
        raw.append(
            (
                "shadbala",
                SHADBALA_STRONG if strong else SHADBALA_WEAK,
                f"{name} Shadbala ratio {bala.ratio:.2f} ({'>=' if strong else '<'} 1)",
            )
        )

    if k.combust.get(g, False):
        raw.append(("combust", COMBUST, f"{name} is combust"))

    house = graha_house(k, g)
    if house in KENDRAS or house in TRIKONAS:
        raw.append(("house", HOUSE_GOOD, f"{name} is in house {house} (kendra/trikona)"))
    elif house in DUSTHANAS:
        raw.append(("house", HOUSE_BAD, f"{name} is in house {house} (6/8/12)"))

    if k.vargottama.get(g, False):
        raw.append(("vargottama", VARGOTTAMA, f"{name} is vargottama"))

    d9_sign = k.vargas.get(9, {}).get(name)
    if d9_sign is not None:
        d9 = d9_dignity(g, d9_sign)
        why = f"{name} is in {RASHIS[d9_sign]} in D9"
        if d9 in (Dignity.EXALTED, Dignity.OWN):
            raw.append(("d9_dignity", D9_GOOD, f"{why} ({d9.value})"))
        elif d9 is Dignity.DEBILITATED:
            raw.append(("d9_dignity", D9_BAD, f"{why} ({d9.value})"))

    factors = tuple(Factor(name=n, delta=d, why=w, ref=refs[n]["ref"]) for n, d, w in raw if d != 0)
    score = BASE + sum(f.delta for f in factors)
    return Strength(score=max(0, min(100, score)), factors=factors)
