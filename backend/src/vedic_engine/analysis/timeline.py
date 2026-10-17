"""24-month timeline: dasha periods judged, transit overlays, monthly ratings, best/worst windows.

``timeline(k, now_utc, months=24)`` covers the window ``[now, now + months)`` (calendar months,
day clamped to the month's length):

* ``items``: every Vimshottari antar and pratyantar overlapping the window, with their true
  (unclipped) start and end, judged with ``judge_period((maha, antar[, pratyantar]))``. Antars
  come first, then pratyantars; within a level they are contiguous and in time order.
* ``transits``: Saturn and Jupiter sign segments over the window (exact ingress times from
  ``transit.sign_ingresses``), each read from the natal Moon sign (Phaladeepika Ch 26 v. 1):
  Jupiter supportive in houses 2, 5, 7, 9, 11 (v. 2, v. 7); Saturn supportive in 3, 6, 11 (v. 2,
  v. 5); Sade Sati / Dhaiya phases come from ``doshas.sade_sati``. Weights in ``transit.json``
  ``deltas`` are interpretive. Vedha is not modelled.
* ``months``: one ``MonthRating`` per calendar month from ``now``. Its score is the time-weighted
  mean of the overlapping pratyantars' judgement scores plus the time-weighted transit deltas,
  rounded half up and clamped to -100..100; nature uses the ``judge_period`` thresholds.
* ``best_windows`` / ``challenging_windows``: the 3 highest / lowest rated months, ties broken
  by the earlier start, so the choice is deterministic. "Challenging" is relative: a window
  keeps its own ``nature``, which may still be "mixed" or "favourable".

Traditional Jyotish interpretation: guidance, not certainty.
"""

import calendar
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from math import floor

from vedic_engine import ephemeris
from vedic_engine.analysis.areas import AREAS
from vedic_engine.analysis.dasha_judgement import (
    CHALLENGING_BELOW,
    FAVOURABLE_ABOVE,
    Nature,
    PeriodJudgement,
    judge_period,
)
from vedic_engine.analysis.functional import load_data
from vedic_engine.angles import sign_of
from vedic_engine.constants import RASHIS, Graha
from vedic_engine.dasha import DashaPeriod
from vedic_engine.dasha.vimshottari import subtree
from vedic_engine.doshas import sade_sati
from vedic_engine.kundli import Kundli
from vedic_engine.models import InputError, Settings
from vedic_engine.timeutil import jd_from_utc, utc_from_jd
from vedic_engine.transit import sign_ingresses

JUPITER_GOOD = frozenset({2, 5, 7, 9, 11})
SATURN_GOOD = frozenset({3, 6, 11})
WINDOWS = 3


@dataclass(frozen=True, slots=True)
class TransitOverlay:
    """Saturn or Jupiter in one sign over ``[start_utc, end_utc)`` (clipped to the window)."""

    graha: Graha
    sign: int  # 0-11
    house: int  # 1-12 from the natal Moon sign
    start_utc: datetime
    end_utc: datetime
    code: str
    delta: int
    text_en: str
    text_hi: str
    why: tuple[str, ...]
    ref: str


@dataclass(frozen=True, slots=True)
class TimelineItem:
    level: str  # "antar" | "pratyantar"
    lords: tuple[str, ...]  # maha, antar[, pratyantar]
    start_utc: datetime
    end_utc: datetime
    judgement: PeriodJudgement
    areas: tuple[str, ...]  # life-area keys whose houses the lords rule or occupy
    advice_key: str  # "advice.<nature>" in decisions.json
    why: tuple[str, ...]
    ref: str


@dataclass(frozen=True, slots=True)
class WindowReason:
    code: str
    text_en: str
    text_hi: str
    why: tuple[str, ...]
    ref: str


@dataclass(frozen=True, slots=True)
class MonthRating:
    start_utc: datetime
    end_utc: datetime
    score: int
    nature: Nature
    dasha_score: float
    transit_score: float
    reasons: tuple[WindowReason, ...]


@dataclass(frozen=True, slots=True)
class Timeline:
    now_utc: datetime
    end_utc: datetime
    items: tuple[TimelineItem, ...]
    transits: tuple[TransitOverlay, ...]
    months: tuple[MonthRating, ...]
    best_windows: tuple[MonthRating, ...]
    challenging_windows: tuple[MonthRating, ...]


def add_months(dt: datetime, n: int) -> datetime:
    """``dt`` moved ``n`` calendar months, the day clamped to the target month's length."""
    y, m = divmod(dt.month - 1 + n, 12)
    year, month = dt.year + y, m + 1
    return dt.replace(year=year, month=month, day=min(dt.day, calendar.monthrange(year, month)[1]))


def settings_of(k: Kundli) -> Settings:
    return Settings(**k.meta["settings"])


def nature_of(score: float) -> Nature:
    if score > FAVOURABLE_ABOVE:
        return "favourable"
    if score < CHALLENGING_BELOW:
        return "challenging"
    return "mixed"


def _containing(periods: Sequence[DashaPeriod], at: datetime, what: str) -> DashaPeriod:
    for p in periods:
        if p.start_utc <= at < p.end_utc:
            return p
    raise InputError(f"{at.isoformat()} is outside this chart's {what} span")


def current_periods(k: Kundli, at: datetime) -> tuple[DashaPeriod, DashaPeriod, DashaPeriod]:
    """Vimshottari maha, antar and pratyantar running at ``at`` (expanded with ``subtree``)."""
    settings = settings_of(k)
    maha = _containing(k.vimshottari, at, "dasha")
    antar = _containing(subtree(maha, settings, 1).children, at, "dasha")
    pratyantar = _containing(subtree(antar, settings, 1).children, at, "dasha")
    return maha, antar, pratyantar


def _overlaps(start: datetime, end: datetime, a: datetime, b: datetime) -> bool:
    return start < b and end > a


def _seconds(start: datetime, end: datetime, a: datetime, b: datetime) -> float:
    return max(0.0, (min(end, b) - max(start, a)).total_seconds())


def area_keys(houses: Sequence[int]) -> tuple[str, ...]:
    table = load_data("decisions")["area_houses"]
    return tuple(a for a in AREAS if set(table[a]) & set(houses))


def _label(g: str) -> tuple[str, str]:
    node = load_data("areas")["labels"]["grahas"][g]
    return node["en"], node["hi"]


def lords_text(lords: Sequence[str]) -> tuple[str, str]:
    labels = [_label(g) for g in lords]
    return "–".join(en for en, _ in labels), "–".join(hi for _, hi in labels)


def _item(k: Kundli, level: str, chain: tuple[DashaPeriod, ...]) -> TimelineItem:
    lords = tuple(p.lord for p in chain)
    j = judge_period(k, tuple(Graha(x) for x in lords))
    last = chain[-1]
    return TimelineItem(
        level=level,
        lords=lords,
        start_utc=last.start_utc,
        end_utc=last.end_utc,
        judgement=j,
        areas=area_keys(j.areas),
        advice_key=f"advice.{j.nature}",
        why=(
            f"{level} {'-'.join(lords)}: {last.start_utc:%Y-%m-%d} to {last.end_utc:%Y-%m-%d}",
            f"judge_period score {j.score} ({j.nature})",
            f"lords rule or occupy houses {', '.join(map(str, j.areas))}",
        ),
        ref=load_data("transit")["dasha"]["ref"],
    )


def _dasha_items(k: Kundli, now: datetime, end: datetime) -> tuple[TimelineItem, ...]:
    settings = settings_of(k)
    antars: list[TimelineItem] = []
    pratyantars: list[TimelineItem] = []
    for maha in k.vimshottari:
        if not _overlaps(maha.start_utc, maha.end_utc, now, end):
            continue
        for antar in subtree(maha, settings, 2).children:
            if not _overlaps(antar.start_utc, antar.end_utc, now, end):
                continue
            antars.append(_item(k, "antar", (maha, antar)))
            for p in antar.children:
                if _overlaps(p.start_utc, p.end_utc, now, end):
                    pratyantars.append(_item(k, "pratyantar", (maha, antar, p)))
    if not antars or antars[0].start_utc > now or antars[-1].end_utc < end:
        raise InputError(f"the window from {now.isoformat()} is outside this chart's dasha span")
    return (*antars, *pratyantars)


def _overlay(
    g: Graha, sign: int, house: int, start: datetime, end: datetime, phase: str | None
) -> TransitOverlay:
    data = load_data("transit")
    if g == Graha.JUPITER:
        code = "jupiter_good" if house in JUPITER_GOOD else "jupiter_other"
        delta_key = code
    elif house in SATURN_GOOD:
        code = delta_key = "saturn_good"
    elif phase is not None:
        code, delta_key = phase, "saturn_phase"
    else:
        code = delta_key = "saturn_other"
    rule = data["rules"][code]
    ordinal = data["ordinals"][str(house)]
    return TransitOverlay(
        graha=g,
        sign=sign,
        house=house,
        start_utc=start,
        end_utc=end,
        code=code,
        delta=data["deltas"][delta_key],
        text_en=rule["en"].format(house=ordinal["en"]),
        text_hi=rule["hi"].format(house=ordinal["hi"]),
        why=(
            f"{g.value} in {RASHIS[sign]} from {start:%Y-%m-%d} to {end:%Y-%m-%d}",
            f"house {house} from the natal Moon sign"
            + (f"; engine phase {phase}" if phase else ""),
        ),
        ref=rule["ref"],
    )


def transits(k: Kundli, now: datetime, end: datetime) -> tuple[TransitOverlay, ...]:
    """Saturn and Jupiter sign segments over ``[now, end)``, read from the natal Moon sign."""
    settings = settings_of(k)
    moon_lon = k.grahas[Graha.MOON].lon
    moon_sign = sign_of(moon_lon)
    jd0, jd1 = jd_from_utc(now), jd_from_utc(end)
    phases, _ = sade_sati(moon_lon, jd0, settings, years=max(1, (end.year - now.year) + 1))
    out: list[TransitOverlay] = []
    for g in (Graha.SATURN, Graha.JUPITER):
        segments = [(now, sign_of(ephemeris.body_longitude(jd0, g, settings)))]
        segments += [(utc_from_jd(jd), s) for jd, s in sign_ingresses(g, jd0, jd1, settings)]
        for i, (start, sign) in enumerate(segments):
            seg_end = segments[i + 1][0] if i + 1 < len(segments) else end
            phase = None
            if g == Graha.SATURN:
                mid = start + (seg_end - start) / 2
                phase = next((p.kind for p in phases if p.start_utc <= mid < p.end_utc), None)
            house = (sign - moon_sign) % 12 + 1
            out.append(_overlay(g, sign, house, start, seg_end, phase))
    return tuple(out)


def _round_half_up(x: float) -> int:
    return floor(x + 0.5)


def _month(
    start: datetime,
    end: datetime,
    pratyantars: Sequence[TimelineItem],
    overlays: Sequence[TransitOverlay],
) -> MonthRating:
    total = (end - start).total_seconds()
    tdata = load_data("transit")
    reasons: list[tuple[float, WindowReason]] = []
    dasha = 0.0
    for p in pratyantars:
        s = _seconds(p.start_utc, p.end_utc, start, end)
        if s <= 0:
            continue
        dasha += p.judgement.score * s / total
        en, hi = lords_text(p.lords)
        nat = tdata["natures"][p.judgement.nature]
        tpl = tdata["dasha"]
        reasons.append(
            (
                s,
                WindowReason(
                    code=f"dasha:{'-'.join(p.lords)}",
                    text_en=tpl["en"].format(lords=en, score=p.judgement.score, nature=nat["en"]),
                    text_hi=tpl["hi"].format(lords=hi, score=p.judgement.score, nature=nat["hi"]),
                    why=(*p.why, f"covers {s / total:.0%} of the month"),
                    ref=p.ref,
                ),
            )
        )
    transit = 0.0
    for t in overlays:
        s = _seconds(t.start_utc, t.end_utc, start, end)
        if s <= 0:
            continue
        transit += t.delta * s / total
        reasons.append(
            (
                s,
                WindowReason(
                    code=f"transit:{t.code}",
                    text_en=t.text_en,
                    text_hi=t.text_hi,
                    why=(*t.why, f"weight {t.delta:+d}, covers {s / total:.0%} of the month"),
                    ref=t.ref,
                ),
            )
        )
    score = max(-100, min(100, _round_half_up(dasha + transit)))
    ordered = sorted(enumerate(reasons), key=lambda x: (-x[1][0], x[0]))  # stable by overlap
    return MonthRating(
        start_utc=start,
        end_utc=end,
        score=score,
        nature=nature_of(score),
        dasha_score=dasha,
        transit_score=transit,
        reasons=tuple(r for _, (_, r) in ordered),
    )


def timeline(k: Kundli, now_utc: datetime, months: int = 24) -> Timeline:
    """Dasha items, transit overlays and monthly ratings for ``[now, now + months)``."""
    if now_utc.tzinfo is None:
        raise InputError("now_utc must be timezone-aware")
    if months < 1:
        raise ValueError(f"months must be >= 1, got {months}")
    end = add_months(now_utc, months)
    items = _dasha_items(k, now_utc, end)
    overlays = transits(k, now_utc, end)
    pratyantars = [i for i in items if i.level == "pratyantar"]
    ratings = tuple(
        _month(add_months(now_utc, i), add_months(now_utc, i + 1), pratyantars, overlays)
        for i in range(months)
    )
    n = min(WINDOWS, len(ratings))
    return Timeline(
        now_utc=now_utc,
        end_utc=end,
        items=items,
        transits=overlays,
        months=ratings,
        best_windows=tuple(sorted(ratings, key=lambda m: (-m.score, m.start_utc))[:n]),
        challenging_windows=tuple(sorted(ratings, key=lambda m: (m.score, m.start_utc))[:n]),
    )
