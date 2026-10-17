"""Judgement of a dasha period (maha, maha + antar, ...) from its lords' nature and strength.

For each lord (Phaladeepika Ch 20 v. 41 applies the BPHS Ch 34 lordship rules to dashas):

* base from the primary functional role: yogakaraka +40, benefic +25, neutral 0, malefic -25;
  maraka (an additional role) -10 more;
* plus ``(strength - 50) / 2`` from ``planet_strength`` (0-100), i.e. -25..+25.

The period score is the mean of the lords' contributions plus, for each consecutive pair
(maha-antar, antar-pratyantar, ...), the mutual position of the two lords counted sign to sign:
6/8 or 2/12 from each other -15; kendra or trikona from each other (same sign counts as
kendra) +10; 3/11 adds nothing (Phaladeepika Ch 20 vv. 29, 42). The result is rounded
(``strength.round_half_up``) and clamped to -100..100. Nature: score > 20 "favourable", < -20
"challenging", otherwise "mixed".

Activated ``areas`` are the houses each lord owns and occupies (Rahu and Ketu own none).

``Reason.delta`` is per lord: each rule's nominal contribution to *that lord's* score, not to the
period score. The period score is the mean of the lords' scores plus the pair (mutual) terms, so
with two lords a role reason of +40 moves the period score by +20, while a ``mutual:*`` reason's
delta is added to the period score as is. ``strength:<factor>`` reasons break the ``strength``
reason down: each carries half its factor's weight, matching the ``/ 2`` scaling (when the 0-100
clamp of the strength score binds they sum to more than the applied strength term).
"""

from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from vedic_engine.analysis.functional import Role, functional_roles, load_data
from vedic_engine.analysis.strength import ChartFacts, graha_house, planet_strength, round_half_up
from vedic_engine.angles import sign_of
from vedic_engine.constants import Graha

ROLE_BASE: dict[Role, int] = {
    Role.YOGAKARAKA: 40,
    Role.BENEFIC: 25,
    Role.NEUTRAL: 0,
    Role.MALEFIC: -25,
}
MARAKA_EXTRA = -10
MUTUAL_DUSTHANA = -15
MUTUAL_KENDRA_TRIKONA = 10
FAVOURABLE_ABOVE = 20
CHALLENGING_BELOW = -20

_MUTUAL_BAD = frozenset({2, 6, 8, 12})
_MUTUAL_GOOD = frozenset({1, 4, 5, 7, 9, 10})

Nature = Literal["favourable", "mixed", "challenging"]


@dataclass(frozen=True, slots=True)
class Reason:
    """``code`` is a stable machine key, e.g. ``role:yogakaraka``, ``occupies:3``."""

    code: str
    text: str
    why: str
    delta: float
    ref: str


@dataclass(frozen=True, slots=True)
class PeriodJudgement:
    score: int
    nature: Nature
    areas: tuple[int, ...]
    reasons: tuple[Reason, ...]


def nature_of(score: float) -> Nature:
    """Nature of a score: > ``FAVOURABLE_ABOVE`` favourable, < ``CHALLENGING_BELOW``
    challenging, otherwise mixed (shared by period judgements and month ratings)."""
    if score > FAVOURABLE_ABOVE:
        return "favourable"
    if score < CHALLENGING_BELOW:
        return "challenging"
    return "mixed"


def moon_waxing(k: ChartFacts) -> bool:
    """Shukla paksha: the Moon is less than 180 deg ahead of the Sun."""
    elongation = (k.grahas[Graha.MOON].lon - k.grahas[Graha.SUN].lon) % 360.0
    return elongation < 180.0


def _house_text(house: int) -> str:
    return ", ".join(load_data("houses")["houses"][str(house)]["en"])


def _lord_reasons(k: ChartFacts, g: Graha) -> tuple[float, list[Reason], set[int]]:
    period = load_data("grahas")["period_rules"]
    houses_data = load_data("houses")["houses"]
    role = functional_roles(sign_of(k.lagna_lon), moon_waxing(k))[g]
    reasons = [
        Reason(
            code=f"role:{role.role.value}",
            text=role.text,
            why=f"{role.why}; decided by: {role.source}" + (f"; {role.note}" if role.note else ""),
            delta=ROLE_BASE[role.role],
            ref=role.ref,
        )
    ]
    if role.node_note is not None:
        reasons.append(Reason("node_note", role.node_note, role.why, 0, role.ref))
    score: float = ROLE_BASE[role.role]
    if Role.MARAKA in role.roles:
        if role.maraka_ref is None:
            raise ValueError(f"{g.value} has the maraka role without a maraka_ref")
        rule = load_data("grahas")["rules"]["maraka"]
        reasons.append(Reason("role:maraka", rule["text"], role.why, MARAKA_EXTRA, role.maraka_ref))
        score += MARAKA_EXTRA

    strength = planet_strength(k, g)
    term = (strength.score - 50) / 2
    score += term
    reasons.append(
        Reason(
            code="strength",
            text=period["strength"]["text"],
            why=f"{g.value} strength {strength.score}/100 -> ({strength.score} - 50) / 2",
            delta=term,
            ref=period["strength"]["ref"],
        )
    )
    factor_text = load_data("grahas")["strength_factors"]
    reasons.extend(
        Reason(f"strength:{f.name}", factor_text[f.name]["text"], f.why, f.delta / 2, f.ref)
        for f in strength.factors
    )

    for h in role.houses:
        reasons.append(
            Reason(
                f"rules:{h}",
                f"{period['rules']['text']} House {h}: {_house_text(h)}.",
                f"{g.value} rules house {h}",
                0,
                f"{period['rules']['ref']}; {houses_data[str(h)]['ref']}",
            )
        )
    occupied = graha_house(k, g)
    reasons.append(
        Reason(
            f"occupies:{occupied}",
            f"{period['occupies']['text']} House {occupied}: {_house_text(occupied)}.",
            f"{g.value} occupies house {occupied}",
            0,
            f"{period['occupies']['ref']}; {houses_data[str(occupied)]['ref']}",
        )
    )
    return score, reasons, {*role.houses, occupied}


def _mutual(k: ChartFacts, a: Graha, b: Graha) -> Reason | None:
    period = load_data("grahas")["period_rules"]
    n = (sign_of(k.grahas[b].lon) - sign_of(k.grahas[a].lon)) % 12 + 1
    why = (
        f"{b.value} is in the same sign as {a.value}"
        if n == 1
        else f"{b.value} is {n} from {a.value} ({a.value} is {(14 - n) % 12 or 12} from {b.value})"
    )
    if n in _MUTUAL_BAD:
        rule = period["mutual_dusthana"]
        return Reason(
            "mutual:dvirdvadasha_shashtashtaka", rule["text"], why, MUTUAL_DUSTHANA, rule["ref"]
        )
    if n in _MUTUAL_GOOD:
        rule = period["mutual_kendra_trikona"]
        return Reason(
            "mutual:kendra_trikona", rule["text"], why, MUTUAL_KENDRA_TRIKONA, rule["ref"]
        )
    return None


def judge_period(k: ChartFacts, lords: tuple[Graha, ...]) -> PeriodJudgement:
    """Judge the period ruled by ``lords`` (maha first, then antar, ...)."""
    if not lords:
        raise ValueError("judge_period needs at least one lord")
    reasons: list[Reason] = []
    areas: set[int] = set()
    contributions: list[float] = []
    for g in lords:
        score, lord_reasons, lord_areas = _lord_reasons(k, g)
        contributions.append(score)
        reasons.extend(lord_reasons)
        areas |= lord_areas
    total = sum(contributions) / len(contributions)
    for a, b in pairwise(lords):
        mutual = _mutual(k, a, b)
        if mutual is not None:
            reasons.append(mutual)
            total += mutual.delta
    score = max(-100, min(100, round_half_up(total)))
    return PeriodJudgement(
        score=score, nature=nature_of(score), areas=tuple(sorted(areas)), reasons=tuple(reasons)
    )
