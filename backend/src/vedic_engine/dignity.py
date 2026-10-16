"""Dignity, natural/temporal/compound relationships and combustion (spec 5.2, 5.5)."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Literal

from vedic_engine.angles import arc, deg_in_sign, sign_of
from vedic_engine.constants import RASHI_LORD, Graha


class Dignity(StrEnum):
    EXALTED = "exalted"
    DEBILITATED = "debilitated"
    MOOLATRIKONA = "moolatrikona"
    OWN = "own"
    GREAT_FRIEND = "great_friend"
    FRIEND = "friend"
    NEUTRAL = "neutral"
    ENEMY = "enemy"
    GREAT_ENEMY = "great_enemy"


Relation = Literal["friend", "neutral", "enemy"]

# School dependent: sign index (0-based) of exaltation; debilitation is the opposite sign.
NODE_DIGNITY_SCHOOL: dict[str, dict[str, int]] = {
    "rahu": {"exalted": 1},
    "ketu": {"exalted": 7},
}

_EXALT_SIGN = {
    Graha.SUN: 0, Graha.MOON: 1, Graha.MARS: 9, Graha.MERCURY: 5,
    Graha.JUPITER: 3, Graha.VENUS: 11, Graha.SATURN: 6,
}  # fmt: skip

# (sign, start_deg, end_deg) half-open [start, end)
_MOOLATRIKONA = {
    Graha.SUN: (4, 0.0, 20.0), Graha.MOON: (1, 3.0, 30.0), Graha.MARS: (0, 0.0, 12.0),
    Graha.MERCURY: (5, 15.0, 20.0), Graha.JUPITER: (8, 0.0, 10.0),
    Graha.VENUS: (6, 0.0, 15.0), Graha.SATURN: (10, 0.0, 20.0),
}  # fmt: skip

_FRIENDS = {
    Graha.SUN: (Graha.MOON, Graha.MARS, Graha.JUPITER),
    Graha.MOON: (Graha.SUN, Graha.MERCURY),
    Graha.MARS: (Graha.SUN, Graha.MOON, Graha.JUPITER),
    Graha.MERCURY: (Graha.SUN, Graha.VENUS),
    Graha.JUPITER: (Graha.SUN, Graha.MOON, Graha.MARS),
    Graha.VENUS: (Graha.MERCURY, Graha.SATURN),
    Graha.SATURN: (Graha.MERCURY, Graha.VENUS),
}
_ENEMIES = {
    Graha.SUN: (Graha.VENUS, Graha.SATURN),
    Graha.MOON: (),
    Graha.MARS: (Graha.MERCURY,),
    Graha.MERCURY: (Graha.MOON,),
    Graha.JUPITER: (Graha.MERCURY, Graha.VENUS),
    Graha.VENUS: (Graha.SUN, Graha.MOON),
    Graha.SATURN: (Graha.SUN, Graha.MOON, Graha.MARS),
}

_COMPOUND: dict[tuple[str, str], Dignity] = {
    ("friend", "friend"): Dignity.GREAT_FRIEND,
    ("friend", "enemy"): Dignity.NEUTRAL,
    ("neutral", "friend"): Dignity.FRIEND,
    ("neutral", "enemy"): Dignity.ENEMY,
    ("enemy", "friend"): Dignity.NEUTRAL,
    ("enemy", "enemy"): Dignity.GREAT_ENEMY,
}

_COMBUST_ORB = {
    Graha.MOON: 12.0, Graha.MARS: 17.0, Graha.MERCURY: 14.0,
    Graha.JUPITER: 11.0, Graha.VENUS: 10.0, Graha.SATURN: 15.0,
}  # fmt: skip
_COMBUST_ORB_RETRO = {Graha.MERCURY: 12.0, Graha.VENUS: 8.0}


def natural_relation(a: Graha, b: Graha) -> Relation:
    """Natural (BPHS Ch 3) relation of `a` toward `b`. Nodes have no table in Phase 1."""
    if a not in _FRIENDS or b not in _FRIENDS:
        raise ValueError("natural relations are defined for the seven grahas only")
    if a == b:
        raise ValueError("a graha has no relation to itself")
    if b in _FRIENDS[a]:
        return "friend"
    if b in _ENEMIES[a]:
        return "enemy"
    return "neutral"


def temporal_relation(a_sign: int, b_sign: int) -> Literal["friend", "enemy"]:
    """b in the 2nd, 3rd, 4th, 10th, 11th or 12th sign from a is a temporal friend."""
    return "friend" if (b_sign - a_sign) % 12 in (1, 2, 3, 9, 10, 11) else "enemy"


def dignity(graha: Graha, lon: float, positions: Mapping[Graha, float]) -> Dignity:
    sign = sign_of(lon)
    if graha in (Graha.RAHU, Graha.KETU):
        exalted = NODE_DIGNITY_SCHOOL[graha.value]["exalted"]
        if sign == exalted:
            return Dignity.EXALTED
        if sign == (exalted + 6) % 12:
            return Dignity.DEBILITATED
        return Dignity.NEUTRAL

    deg = deg_in_sign(lon)
    mt_sign, mt_start, mt_end = _MOOLATRIKONA[graha]
    exalt = _EXALT_SIGN[graha]
    if sign == (exalt + 6) % 12:
        return Dignity.DEBILITATED
    # Moolatrikona carves out the upper part of the exaltation sign (Moon, Mercury).
    in_mt = sign == mt_sign and mt_start <= deg < mt_end
    if sign == exalt and not (sign == mt_sign and deg >= mt_start):
        return Dignity.EXALTED
    if in_mt:
        return Dignity.MOOLATRIKONA
    lord = RASHI_LORD[sign]
    if lord == graha:
        return Dignity.OWN
    natural = natural_relation(graha, lord)
    temporal = temporal_relation(sign_of(positions[graha]), sign_of(positions[lord]))
    if natural == "neutral":
        return Dignity.FRIEND if temporal == "friend" else Dignity.ENEMY
    return _COMPOUND[(natural, temporal)]


def is_combust(graha: Graha, lon: float, sun_lon: float, retro: bool) -> bool:
    orb = _COMBUST_ORB.get(graha)
    if orb is None:
        return False
    if retro:
        orb = _COMBUST_ORB_RETRO.get(graha, orb)
    d = arc(lon, sun_lon)
    return min(d, 360.0 - d) <= orb
