"""Friendly wording for ``why`` facts (ruling U14a/U14b).

The engine builds ``why`` strings as precise, technical facts (``rahu strength 85/100 ->
(85 - 50) / 2``). People should read plain sentences ("Rahu is strong (85/100)"). ``friendly``
rewrites one raw fact; ``split_why`` returns the friendly list plus the raw facts that were
changed, which the API ships separately as ``detail`` for a collapsed "Calculation details" view.

Every rewrite keeps the facts and only changes the wording; names of grahas and signs are
capitalised everywhere (U14b).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

GRAHA_NAMES = ("sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu")
RASHI_NAMES = (
    "mesha", "vrishabha", "mithuna", "karka", "simha", "kanya",
    "tula", "vrishchika", "dhanu", "makara", "kumbha", "meena",
)  # fmt: skip

_G = "|".join(GRAHA_NAMES)
_R = "|".join(RASHI_NAMES)
_NAME_RE = re.compile(rf"\b({_G}|{_R})\b")
_ORD = {1: "1st", 2: "2nd", 3: "3rd"}

_DIGNITY = {
    "exalted": "exalted",
    "debilitated": "debilitated",
    "own": "in its own sign",
    "moolatrikona": "in its moolatrikona sign",
    "great friend": "in a great friend's sign",
    "friend": "in a friend's sign",
    "neutral": "in a neutral sign",
    "enemy": "in an enemy's sign",
    "great enemy": "in a great enemy's sign",
}
_ROLE = {
    "benefic": "a functional benefic",
    "malefic": "a functional malefic",
    "neutral": "functionally neutral",
    "yogakaraka": "a yogakaraka (especially auspicious)",
}


def _fm(pattern: str, s: str) -> re.Match[str] | None:
    return re.fullmatch(pattern, s, re.IGNORECASE)


def ordinal(n: int) -> str:
    return _ORD.get(n, f"{n}th") if n not in (11, 12, 13) else f"{n}th"


def cap_names(s: str) -> str:
    """Capitalise graha and sign names, then the first letter of the sentence."""
    s = _NAME_RE.sub(lambda m: m.group(1).capitalize(), s)
    return s[:1].upper() + s[1:]


def _houses(txt: str) -> str:
    nums = [x.strip() for x in txt.split(",")]
    return f"house {nums[0]}" if len(nums) == 1 else f"houses {' and '.join(nums)}"


def _band(score: int) -> str:
    return "strong" if score >= 70 else "moderately strong" if score >= 45 else "weak"


def _rewrite(s: str) -> str:
    if m := _fm(rf"({_G}) strength (\d+)/100 -> \(\d+ - 50\) / 2", s):
        return f"{m[1]} is {_band(int(m[2]))} ({m[2]}/100)"
    if m := _fm(rf"({_G}) strength (\d+)/100 \((?:no factors|.*)\)", s):
        return f"{m[1]} strength {m[2]}/100"
    if m := _fm(rf"({_G}) Shadbala ratio [\d.]+ \((>=|<) 1\)", s):
        side = "above" if m[2] == ">=" else "below"
        return f"{m[1]} has Shadbala {side} the classical minimum"
    if m := _fm(rf"({_G}) is in house (\d+) \(kendra/trikona\)", s):
        return f"{m[1]} is in house {m[2]}, a supportive (kendra or trikona) house"
    if m := _fm(rf"({_G}) is in house (\d+) \(6/8/12\)", s):
        return f"{m[1]} is in house {m[2]}, a difficult (6th, 8th or 12th) house"
    if m := _fm(rf"({_G}) is ([a-z ]+) in D1", s):
        d = _DIGNITY.get(m[2])
        return f"{m[1]} is {d} in the birth chart" if d else s
    if m := _fm(rf"({_G}) is in ({_R}) in D9 \(([a-z ]+)\)", s):
        d = _DIGNITY.get(m[3], m[3])
        return f"{m[1]} is {d} ({m[2]}) in the Navamsa (D9)"
    if m := _fm(rf"({_G}) is vargottama", s):
        return f"{m[1]} is vargottama (same sign in D1 and D9)"
    if m := _fm(rf"({_G}) is combust", s):
        return f"{m[1]} is combust (too close to the Sun)"
    if m := _fm(rf"({_G}) is in the same sign as ({_G})", s):
        return f"{m[1]} and {m[2]} are in the same sign"
    if m := _fm(rf"({_G}) is (\d+) from ({_G}) \(.*\)", s):
        return f"{m[1]} is the {ordinal(int(m[2]))} sign from {m[3]}"
    if m := _fm(rf"({_G}) (rules|occupies) house (\d+)", s):
        return f"{m[1]} {m[2]} the {ordinal(int(m[3]))} house"
    if m := _fm(rf"({_G}) owns no house for ({_R}) lagna(?:; decided by: \w+)?", s):
        return f"{m[1]} owns no house for {m[2]} lagna (a node)"
    # lordship: "[G is ROLE for this lagna/chart:] G rules house A, B for X lagna (...); lordship
    # rule: R -> role[; decided by: S[; note]]"
    if m := _fm(
        rf"(?:({_G}) is (benefic|malefic|neutral|yogakaraka) for this (lagna|chart \(Moon-based\)): )?"
        rf"({_G}) rules house ([\d, ]+) for ({_R}) lagna \(moolatrikona in house \d+\); "
        rf"lordship rule: [^;]*? -> (\w+)(?:; decided by: .*)?",
        s,
    ):
        role = m[2] or m[7]
        where = "this chart (Moon-based)" if m[3] and m[3] != "lagna" else "this lagna"
        return (
            f"{m[4]} rules {_houses(m[5])} for {m[6]} lagna, so it is "
            f"{_ROLE.get(role, role)} for {where}"
        )
    if m := _fm(
        r"(antar|pratyantar) ([a-z]+(?:-[a-z]+)+): (\d{4}-\d\d-\d\d) to (\d{4}-\d\d-\d\d)", s
    ):
        label = "Antardasha" if m[1] == "antar" else "Pratyantar"
        lords = "–".join(x.capitalize() for x in m[2].split("-"))
        return f"{label} {lords}: {m[3]} to {m[4]}"
    if m := _fm(r"antar ([A-Za-z]+–[A-Za-z]+): judge_period score (-?\d+) \((\w+)\)", s):
        return f"Antardasha {m[1]}: overall score {m[2]} ({m[3]})"
    if m := _fm(r"current (maha|antar) dasha lord (\w+) \((.*)\)", s):
        label = "Mahadasha" if m[1] == "maha" else "Antardasha"
        return f"Current {label} lord: {m[2].capitalize()} ({m[3]})"
    if m := _fm(r"(house \d+ from the natal Moon sign); engine phase (\w+)", s):
        return f"{m[1]} ({m[2].replace('_', ' ').replace('sade sati', 'Sade Sati')})"
    if m := _fm(r"([a-z]+): houses (\d+)", s):
        return f"{m[1].capitalize()}: house {m[2]}"
    return s


def friendly(raw: str) -> str:
    """The plain-language form of one raw fact (names capitalised, no internal notation)."""
    return cap_names(_rewrite(raw))


def split_why(raw: Iterable[str]) -> tuple[list[str], list[str]]:
    """``(why, detail)``: friendly sentences, and the raw facts that differ from them."""
    why: list[str] = []
    detail: list[str] = []
    for r in raw:
        f = friendly(r)
        why.append(f)
        if f.lower() != r.lower():
            detail.append(r)
    return why, detail


def with_why(out: dict[str, object], raw: Iterable[str]) -> dict[str, object]:
    """Set ``why`` (friendly) and, only when something was reworded, ``detail`` (raw)."""
    why, detail = split_why(raw)
    out["why"] = why
    if detail:
        out["detail"] = detail
    return out
