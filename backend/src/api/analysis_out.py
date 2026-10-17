"""Analysis results -> JSON for `/analysis` and `/daily` (conventions as in ``serialize``).

Every statement carries ``why`` (list of chart facts) and ``ref``; every instant is a
``*_utc`` / ``*_local`` pair (``serialize.instant``).
"""

from collections.abc import Mapping, Sequence

from api.serialize import Json, instant
from vedic_engine.analysis import (
    AreaReading,
    DailyGuidance,
    FunctionalRole,
    IncomeSource,
    LuckySet,
    MonthRating,
    PeriodJudgement,
    Statement,
    Timeline,
    TimelineItem,
    TransitOverlay,
    WindowReason,
)
from vedic_engine.analysis.daily import ColourPick, Decision, Hora
from vedic_engine.analysis.functional import load_data
from vedic_engine.constants import RASHIS, Graha
from vedic_engine.dasha import DashaPeriod

DISCLAIMER_EN = "Traditional Jyotish interpretation — guidance, not certainty."
DISCLAIMER_HI = "पारंपरिक ज्योतिष व्याख्या — मार्गदर्शन, निश्चितता नहीं।"


def disclaimer() -> Json:
    return {"disclaimer_en": DISCLAIMER_EN, "disclaimer_hi": DISCLAIMER_HI}


def statement(s: Statement) -> Json:
    return {"text_en": s.text_en, "text_hi": s.text_hi, "why": list(s.why), "ref": s.ref}


def area(key: str, a: AreaReading) -> Json:
    level = a.summary_key.split(".", 1)[1]
    tpl = load_data("areas")["summaries"][level]
    label = load_data("areas")["labels"]["areas"][key]
    return {
        "score": a.score,
        "summary_key": a.summary_key,
        "summary_en": tpl["en"].format(area=label["en"]),
        "summary_hi": tpl["hi"].format(area=label["hi"]),
        "statements": [statement(s) for s in a.statements],
    }


def income_source(s: IncomeSource) -> Json:
    return {
        "rank": s.rank,
        "type": s.type,
        "label_en": s.label_en,
        "label_hi": s.label_hi,
        "score": s.score,
        "planet": s.planet.value,
        "roles": list(s.roles),
        "why": list(s.why),
        "ref": s.ref,
    }


def lucky_set(s: LuckySet) -> Json:
    return {
        "graha": s.graha.value,
        "bases": list(s.bases),
        "items": [
            {
                "kind": i.kind,
                "value_en": i.value_en,
                "value_hi": i.value_hi,
                "source": i.source,
                "label": i.label,
                "label_hi": i.label_hi,
            }
            for i in s.items
        ],
    }


def functional_role(r: FunctionalRole) -> Json:
    return {
        "role": r.role.value,
        "roles": [x.value for x in r.roles],
        "houses": list(r.houses),
        "source": r.source,
        "text": r.text,
        "why": [r.why],
        "ref": r.ref,
        "maraka_ref": r.maraka_ref,
        "note": r.note,
        "node_note": r.node_note,
    }


def judgement(j: PeriodJudgement) -> Json:
    return {
        "score": j.score,
        "nature": j.nature,
        "houses": list(j.areas),
        "reasons": [
            {"code": r.code, "text": r.text, "why": [r.why], "delta": float(r.delta), "ref": r.ref}
            for r in j.reasons
        ],
    }


def period(p: DashaPeriod, j: PeriodJudgement, tz: str) -> Json:
    return {
        "lord": p.lord,
        **instant("start", p.start_utc, tz),
        **instant("end", p.end_utc, tz),
        "judgement": judgement(j),
    }


def timeline_item(i: TimelineItem, tz: str) -> Json:
    return {
        "level": i.level,
        "lords": list(i.lords),
        **instant("start", i.start_utc, tz),
        **instant("end", i.end_utc, tz),
        "score": i.judgement.score,
        "nature": i.judgement.nature,
        "areas": list(i.areas),
        "advice_key": i.advice_key,
        **_advice(i.advice_key),
        "judgement": judgement(i.judgement),
        "why": list(i.why),
        "ref": i.ref,
    }


def _advice(key: str) -> Json:
    node = load_data("decisions")["advice"][key.split(".", 1)[1]]
    return {"advice_en": node["en"], "advice_hi": node["hi"]}


def window_reason(r: WindowReason) -> Json:
    return {
        "code": r.code,
        "text_en": r.text_en,
        "text_hi": r.text_hi,
        "why": list(r.why),
        "ref": r.ref,
    }


def month(m: MonthRating, tz: str) -> Json:
    return {
        **instant("start", m.start_utc, tz),
        **instant("end", m.end_utc, tz),
        "score": m.score,
        "nature": m.nature,
        "dasha_score": m.dasha_score,
        "transit_score": m.transit_score,
        "reasons": [window_reason(r) for r in m.reasons],
    }


def transit(t: TransitOverlay, tz: str) -> Json:
    return {
        "graha": t.graha.value,
        "rashi": t.sign + 1,
        "rashi_key": RASHIS[t.sign],
        "house_from_moon": t.house,
        **instant("start", t.start_utc, tz),
        **instant("end", t.end_utc, tz),
        "code": t.code,
        "delta": t.delta,
        "text_en": t.text_en,
        "text_hi": t.text_hi,
        "why": list(t.why),
        "ref": t.ref,
    }


def periods(
    current: Sequence[tuple[str, DashaPeriod, PeriodJudgement]], tl: Timeline, tz: str
) -> Json:
    return {
        **instant("now", tl.now_utc, tz),
        **instant("window_end", tl.end_utc, tz),
        "current": {level: period(p, j, tz) for level, p, j in current},
        "timeline": [timeline_item(i, tz) for i in tl.items],
        "months": [month(m, tz) for m in tl.months],
        "best_windows": [month(m, tz) for m in tl.best_windows],
        "challenging_windows": [month(m, tz) for m in tl.challenging_windows],
        "transits": [transit(t, tz) for t in tl.transits],
    }


def analysis(
    areas: Mapping[str, AreaReading],
    income: Sequence[IncomeSource],
    lucky: Sequence[LuckySet],
    roles: Mapping[Graha, FunctionalRole],
    periods_json: Json,
    meta: Json,
) -> Json:
    return {
        "meta": meta,
        "areas": {k: area(k, a) for k, a in areas.items()},
        "income_sources": [income_source(s) for s in income],
        "lucky": [lucky_set(s) for s in lucky],
        "functional_roles": {g.value: functional_role(r) for g, r in roles.items()},
        "periods": periods_json,
        **disclaimer(),
    }


def _colour_pick(c: ColourPick | None) -> Json | None:
    if c is None:
        return None
    return {
        "graha": c.graha.value,
        "colour_en": c.en,
        "colour_hi": c.hi,
        "source": c.source,
        "text_en": c.text_en,
        "text_hi": c.text_hi,
        "why": list(c.why),
        "ref": c.ref,
    }


def _hora(h: Hora, tz: str) -> Json:
    return {
        "index": h.index + 1,
        "lord": h.lord.value,
        **instant("start", h.start_utc, tz),
        **instant("end", h.end_utc, tz),
        "colour_en": h.colour.en,
        "colour_hi": h.colour.hi,
        "colour_source": h.colour.source,
        "favourable": h.favourable,
        "avoid": h.avoid,
        "text_en": h.text_en,
        "text_hi": h.text_hi,
        "why": list(h.why),
        "ref": h.ref,
    }


def _decision(d: Decision) -> Json:
    return {
        "kind": d.kind,
        "category": d.category,
        "text_en": d.text_en,
        "text_hi": d.text_hi,
        "why": list(d.why),
        "ref": d.ref,
    }


def daily(g: DailyGuidance, lat: float, lon: float) -> Json:
    tz = g.tz
    return {
        "date": g.date.isoformat(),
        "tz": tz,
        "place": {"lat": lat, "lon": lon},
        "vaar": g.vaar,
        "vaar_lord": g.vaar_lord.value,
        **instant("sunrise", g.sunrise_utc, tz),
        **instant("sunset", g.sunset_utc, tz),
        **instant("next_sunrise", g.next_sunrise_utc, tz),
        "horas": [_hora(h, tz) for h in g.horas],
        "colour_today": _colour_pick(g.colour_today),
        "colour_avoid": _colour_pick(g.colour_avoid),
        "body_language": [statement(s) for s in g.body_language],
        "decisions": [_decision(d) for d in g.decisions],
        **disclaimer(),
    }
