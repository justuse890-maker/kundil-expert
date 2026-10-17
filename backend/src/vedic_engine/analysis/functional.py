"""Functional nature of the grahas for a lagna (BPHS Ch 34, "Yoga Karakas"; Ruling U5).

The role comes from Parasara's own per-lagna lists (BPHS Ch 34 vv. 19-44), transcribed in
``data/functional_bphs.json``. That table wins, including for lagna lords (Tula Venus and
Vrishchika Mars are "neutral"; Vrishabha Venus is a malefic). Precedence per graha:

1. Rahu, Ketu: NEUTRAL with a ``node_note`` (no sign of their own here; vv. 16-17).
2. Named by the verse as causing (raja)yoga: YOGAKARAKA (``source="bphs_lagna"``).
3. Called malefic by the verse: MALEFIC.
4. Lord of a kendra (4, 7, 10) and a trikona (5, 9), not called malefic: YOGAKARAKA by the
   general verse 13 (``source="bphs_v13"``; Leo Mars, Libra Saturn).
5. Called auspicious / neutral by the verse: BENEFIC / NEUTRAL.
6. Not classified by the verse: the generic lordship rules below (``source="rule"``).

MARAKA is additional, never a replacement: a graha the verse names as a killer, or the lord of the
2nd or 7th (BPHS Ch 44) other than the lagna lord, gets ``roles = (primary, MARAKA)``.

Generic lordship rules (BPHS Ch 34 vv. 2-7, 8-10, 13, 14), first match wins. They decide only
case 6 and always supply ``rule``, ``rule_role`` and the ``why`` text:

a. lagna lord: BENEFIC; b. kendra + trikona lord: YOGAKARAKA; c. trikona lord: BENEFIC;
d. lord of 3, 6 or 11: MALEFIC; e. lord of 8 (not Sun or Moon, whose 8th lordship "is not
evil"): MALEFIC; f. kendra lord: NEUTRAL (kendradhipati dosha for a natural benefic, otherwise a
malefic owning a kendra); g. lord of 2 / 12 / the luminaries' 8th only: NEUTRAL.

Natural benefics: Jupiter, Venus, Mercury and the waxing Moon (vv. 8-10). Phase 1 treats Mercury
as a benefic unconditionally (association is not evaluated). Not modelled: node yogakaraka by
relation (v. 17), conjunction yogas the verses mention (kept as notes).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from importlib import resources
from types import MappingProxyType
from typing import Any

from vedic_engine.constants import RASHI_LORD, RASHIS, Graha
from vedic_engine.dignity import MOOLATRIKONA
from vedic_engine.lagna import house_of

KENDRAS = frozenset({1, 4, 7, 10})
TRIKONAS = frozenset({1, 5, 9})
DUSTHANAS_3_6_11 = frozenset({3, 6, 11})
MARAKA_HOUSES = frozenset({2, 7})
_KENDRAS_NOT_LAGNA = frozenset({4, 7, 10})
_TRIKONAS_NOT_LAGNA = frozenset({5, 9})
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

    ``source`` says who decided ``role``: "bphs_lagna" (the per-lagna verse), "bphs_v13"
    (kendra + trikona lord, verse 13), "rule" (generic lordship rules) or "node". ``rule`` and
    ``rule_role`` are always the generic rule's key and result, for comparison and ``why``.
    ``text`` and ``ref`` describe the deciding source. ``maraka_ref`` is set exactly when MARAKA
    is in ``roles``. ``note`` is the per-lagna verse's condition on this graha, if any.
    """

    graha: Graha
    role: Role
    roles: tuple[Role, ...]
    houses: tuple[int, ...]
    source: str
    rule: str
    rule_role: Role
    text: str
    why: str
    ref: str
    maraka_ref: str | None = None
    note: str | None = None
    node_note: str | None = None


def _freeze(x: Any) -> Any:
    if isinstance(x, dict):
        return MappingProxyType({k: _freeze(v) for k, v in x.items()})
    if isinstance(x, list):
        return tuple(_freeze(v) for v in x)
    return x


@cache
def load_data(name: str) -> Mapping[str, Any]:
    """Parsed ``analysis/data/<name>.json``, read-only (mappings are proxies, lists tuples)."""
    path = resources.files("vedic_engine.analysis").joinpath(f"data/{name}.json")
    frozen: Mapping[str, Any] = _freeze(json.loads(path.read_text("utf-8")))
    return frozen


def houses_ruled(graha: Graha, lagna_sign: int) -> tuple[int, ...]:
    """Whole-sign houses (1-12, ascending) whose sign ``graha`` rules; () for the nodes."""
    return tuple(sorted(house_of(s, lagna_sign) for s in range(12) if RASHI_LORD[s] == graha))


def _is_natural_benefic(graha: Graha, moon_is_waxing: bool) -> bool:
    if graha == Graha.MOON:
        return moon_is_waxing
    return graha in _ALWAYS_BENEFIC


def rule_role(graha: Graha, houses: frozenset[int], moon_is_waxing: bool) -> tuple[Role, str]:
    """Generic lordship rules a-g (module docstring): (role, rule key in grahas.json)."""
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


def _node_role(graha: Graha, lagna_name: str) -> FunctionalRole:
    node = load_data("grahas")["rules"]["node"]
    return FunctionalRole(
        graha=graha,
        role=Role.NEUTRAL,
        roles=(Role.NEUTRAL,),
        houses=(),
        source="node",
        rule="node",
        rule_role=Role.NEUTRAL,
        text=node["text"],
        why=f"{graha.value} owns no house for {lagna_name} lagna",
        ref=node["ref"],
        node_note=node["node_note"],
    )


def _why(graha: Graha, lagna_sign: int, houses: tuple[int, ...], rule: str, r_role: Role) -> str:
    owned = ", ".join(str(h) for h in houses)
    mt = house_of(MOOLATRIKONA[graha][0], lagna_sign)
    return (
        f"{graha.value} rules house {owned} for {RASHIS[lagna_sign]} lagna "
        f"(moolatrikona in house {mt}); lordship rule: {rule.replace('_', ' ')} -> {r_role.value}"
    )


def _role_of(graha: Graha, lagna_sign: int, moon_is_waxing: bool) -> FunctionalRole:
    lagna_name = RASHIS[lagna_sign]
    if graha in _NODES:
        return _node_role(graha, lagna_name)
    rules = load_data("grahas")["rules"]
    entry = load_data("functional_bphs")["lagnas"][lagna_name]
    verse_ref = f"BPHS Ch 34 vv. {entry['verses']} (Santhanam p. {entry['pages']})"
    houses = houses_ruled(graha, lagna_sign)
    owned = frozenset(houses)
    r_role, rule = rule_role(graha, owned, moon_is_waxing)
    g = graha.value
    kendra_trikona = bool(owned & _KENDRAS_NOT_LAGNA and owned & _TRIKONAS_NOT_LAGNA)

    role: Role
    if g in entry["yogakaraka"]:
        role, source, category = Role.YOGAKARAKA, "bphs_lagna", "yogakaraka"
    elif g in entry["malefic"]:
        role, source, category = Role.MALEFIC, "bphs_lagna", "malefic"
    elif kendra_trikona:
        role, source, category = Role.YOGAKARAKA, "bphs_v13", ""
    elif g in entry["benefic"]:
        role, source, category = Role.BENEFIC, "bphs_lagna", "benefic"
    elif g in entry["neutral"]:
        role, source, category = Role.NEUTRAL, "bphs_lagna", "neutral"
    else:
        role, source, category = r_role, "rule", ""

    if source == "bphs_lagna":
        table = rules["bphs_lagna"]
        text = table["text"].format(category=table["categories"][category])
        ref = verse_ref
    elif source == "bphs_v13":
        text, ref = rules["yogakaraka"]["text"], f"{rules['yogakaraka']['ref']}; {verse_ref}"
    else:
        text, ref = rules[rule]["text"], rules[rule]["ref"]

    maraka_ref: str | None = None
    if g in entry["maraka"]:
        maraka_ref = verse_ref
    elif rule != "lagna_lord" and owned & MARAKA_HOUSES:
        maraka_ref = rules["maraka"]["ref"]

    return FunctionalRole(
        graha=graha,
        role=role,
        roles=(role, Role.MARAKA) if maraka_ref else (role,),
        houses=houses,
        source=source,
        rule=rule,
        rule_role=r_role,
        text=text,
        why=_why(graha, lagna_sign, houses, rule, r_role),
        ref=ref,
        maraka_ref=maraka_ref,
        note=entry["notes"].get(g),
    )


def functional_roles(lagna_sign: int, moon_is_waxing: bool = True) -> dict[Graha, FunctionalRole]:
    """Functional nature of every graha for a lagna sign (0-11), in ``Graha`` order.

    ``moon_is_waxing`` is the natal paksha (see ``dasha_judgement.moon_waxing``); it decides
    whether the Moon's kendra lordship is cited as kendradhipati dosha or as a malefic's.
    """
    if not 0 <= lagna_sign < 12:
        raise ValueError(f"lagna_sign must be 0-11, got {lagna_sign}")
    return {g: _role_of(g, lagna_sign, moon_is_waxing) for g in Graha}
