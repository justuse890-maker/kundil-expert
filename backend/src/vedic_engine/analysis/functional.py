"""Functional nature of the grahas for a lagna, by house lordship (BPHS Ch 34, "Yoga Karakas").

Whole-sign houses: house n is the nth sign from the lagna sign. Rules and their precedence
(first match wins); every rule's text and verse are in ``data/grahas.json``:

1. Rahu, Ketu: NEUTRAL, with a ``node_note`` (they own no sign for this purpose; BPHS Ch 34
   vv. 16-17).
2. Lagna lord: BENEFIC, even when it also owns the 8th (Mesha, Tula) or an evil house.
3. Owns a kendra (4, 7, 10) and a trikona (5, 9): YOGAKARAKA.
4. Owns a trikona: BENEFIC (trine lordship prevails over the 8th and over 3/6/11; BPHS Ch 34
   notes on v. 4: Saturn, lord of 8 and 9, is favourable for Mithuna).
5. Owns the 3rd, 6th or 11th: MALEFIC.
6. Owns the 8th: MALEFIC, except the Sun and Moon, whose 8th lordship "is not evil"
   (BPHS Ch 34 vv. 2-7; Phaladeepika Ch 20 v. 41); a luminary then falls through to rule 7/8.
7. Owns a kendra: NEUTRAL. A natural benefic loses its beneficence (kendradhipati dosha); a
   natural malefic stops being inauspicious but does not become benefic.
8. Otherwise (lord of the 2nd and/or 12th only): NEUTRAL; they act by association.

MARAKA is additional, never a replacement: the lord of the 2nd or 7th gets ``roles =
(primary, MARAKA)``. The lagna lord is exempt (rule 2, "always BENEFIC"; only Saturn for
Makara, lord of 1 and 2, is affected).

Natural benefics: Jupiter, Venus, Mercury and the waxing Moon (BPHS Ch 34 vv. 8-10). Phase 1
treats Mercury as a benefic unconditionally: association is not evaluated yet. The Moon's paksha
only changes which kendra rule is cited (7 either way gives NEUTRAL).

Not modelled yet: moolatrikona precedence between two lordships (BPHS Ch 34 notes on vv. 4, 15,
e.g. Saturn for Kanya), node yogakaraka by relation (v. 17), and grading within a group.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from importlib import resources
from typing import Any

from vedic_engine.constants import RASHI_LORD, RASHIS, Graha
from vedic_engine.lagna import house_of

KENDRAS = frozenset({1, 4, 7, 10})
TRIKONAS = frozenset({1, 5, 9})
DUSTHANAS_3_6_11 = frozenset({3, 6, 11})
MARAKA_HOUSES = frozenset({2, 7})
_LUMINARIES = frozenset({Graha.SUN, Graha.MOON})
_NODES = frozenset({Graha.RAHU, Graha.KETU})
_ALWAYS_BENEFIC = frozenset({Graha.JUPITER, Graha.VENUS, Graha.MERCURY})


class Role(StrEnum):
    YOGAKARAKA = "yogakaraka"
    BENEFIC = "benefic"
    MALEFIC = "malefic"
    NEUTRAL = "neutral"
    MARAKA = "maraka"


@dataclass(frozen=True, slots=True)
class FunctionalRole:
    """``role`` is the primary nature; ``roles`` is ``(role,)`` or ``(role, Role.MARAKA)``.

    ``rule`` is the key of the deciding rule in ``data/grahas.json``; ``text`` and ``ref`` come
    from it. ``why`` states the chart facts (houses owned). ``maraka_ref`` is set exactly when
    MARAKA is in ``roles``.
    """

    graha: Graha
    role: Role
    roles: tuple[Role, ...]
    houses: tuple[int, ...]
    rule: str
    text: str
    why: str
    ref: str
    maraka_ref: str | None = None
    node_note: str | None = None


@cache
def load_data(name: str) -> dict[str, Any]:
    """Parsed ``analysis/data/<name>.json``."""
    path = resources.files("vedic_engine.analysis").joinpath(f"data/{name}.json")
    data: dict[str, Any] = json.loads(path.read_text("utf-8"))
    return data


def houses_ruled(graha: Graha, lagna_sign: int) -> tuple[int, ...]:
    """Whole-sign houses (1-12, ascending) whose sign ``graha`` rules; () for the nodes."""
    return tuple(sorted(house_of(s, lagna_sign) for s in range(12) if RASHI_LORD[s] == graha))


def _is_natural_benefic(graha: Graha, moon_is_waxing: bool) -> bool:
    if graha == Graha.MOON:
        return moon_is_waxing
    return graha in _ALWAYS_BENEFIC


def _decide(graha: Graha, houses: frozenset[int], moon_is_waxing: bool) -> tuple[Role, str]:
    if 1 in houses:
        return Role.BENEFIC, "lagna_lord"
    if houses & KENDRAS and houses & TRIKONAS:
        return Role.YOGAKARAKA, "yogakaraka"
    if houses & TRIKONAS:
        return Role.BENEFIC, "trikona_lord"
    if houses & DUSTHANAS_3_6_11:
        return Role.MALEFIC, "dusthana_3_6_11"
    if 8 in houses and graha not in _LUMINARIES:
        return Role.MALEFIC, "eighth_lord"
    if houses & KENDRAS:
        if _is_natural_benefic(graha, moon_is_waxing):
            return Role.NEUTRAL, "kendradhipati_dosha"
        return Role.NEUTRAL, "malefic_kendra"
    if 8 in houses:
        return Role.NEUTRAL, "eighth_lord_luminary"
    return Role.NEUTRAL, "lord_2_12"


def _role_of(graha: Graha, lagna_sign: int, moon_is_waxing: bool) -> FunctionalRole:
    rules = load_data("grahas")["rules"]
    lagna_name = RASHIS[lagna_sign]
    if graha in _NODES:
        node = rules["node"]
        return FunctionalRole(
            graha=graha,
            role=Role.NEUTRAL,
            roles=(Role.NEUTRAL,),
            houses=(),
            rule="node",
            text=node["text"],
            why=f"{graha.value} owns no house for {lagna_name} lagna",
            ref=node["ref"],
            node_note=node["node_note"],
        )
    houses = houses_ruled(graha, lagna_sign)
    role, rule = _decide(graha, frozenset(houses), moon_is_waxing)
    maraka = rule != "lagna_lord" and bool(MARAKA_HOUSES & set(houses))
    owned = ", ".join(str(h) for h in houses)
    return FunctionalRole(
        graha=graha,
        role=role,
        roles=(role, Role.MARAKA) if maraka else (role,),
        houses=houses,
        rule=rule,
        text=rules[rule]["text"],
        why=f"{graha.value} rules house {owned} for {lagna_name} lagna",
        ref=rules[rule]["ref"],
        maraka_ref=rules["maraka"]["ref"] if maraka else None,
    )


def functional_roles(lagna_sign: int, moon_is_waxing: bool = True) -> dict[Graha, FunctionalRole]:
    """Functional nature of every graha for a lagna sign (0-11), in ``Graha`` order.

    ``moon_is_waxing`` is the natal paksha (see ``dasha_judgement.moon_waxing``); it decides
    whether the Moon's kendra lordship is cited as kendradhipati dosha or as a malefic's.
    """
    if not 0 <= lagna_sign < 12:
        raise ValueError(f"lagna_sign must be 0-11, got {lagna_sign}")
    return {g: _role_of(g, lagna_sign, moon_is_waxing) for g in Graha}
