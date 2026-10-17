"""Analysis results -> JSON for `/analysis` and `/daily` (conventions as in ``serialize``).

Every statement carries ``why`` (list of chart facts) and ``ref``; every instant is a
``*_utc`` / ``*_local`` pair (``serialize.instant``).
"""

import json
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
    Reason,
    Statement,
    Timeline,
    TimelineItem,
    TransitOverlay,
    WindowReason,
)
from vedic_engine.analysis.daily import ColourPick, Decision, Hora
from vedic_engine.analysis.friendly import cap_names, with_why
from vedic_engine.analysis.functional import load_data
from vedic_engine.constants import RASHIS, Graha
from vedic_engine.dasha import DashaPeriod

# Display precision of the month components and shares (the integer ``score`` is computed
# from the unrounded values with ``strength.round_half_up``).
SCORE_DECIMALS = 2
SHARE_DECIMALS = 3
SUMMARY_REASONS = 3  # timeline items' judgement reasons kept unless detail is "full"
DISCLAIMER_EN = "Traditional Jyotish interpretation — guidance, not certainty."
DISCLAIMER_HI = "पारंपरिक ज्योतिष व्याख्या — मार्गदर्शन, निश्चितता नहीं।"


def friendly_tree(o: object) -> None:
    """Rewrite every ``why`` list in ``o`` in place: friendly sentences, raw facts to ``detail``."""
    if isinstance(o, dict):
        raw = o.get("why")
        if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
            had = o.get("detail")
            with_why(o, raw)
            if had and "detail" not in o:
                o["detail"] = had
        for v in o.values():
            friendly_tree(v)
    elif isinstance(o, list):
        for v in o:
            friendly_tree(v)


def disclaimer() -> Json:
    return {"disclaimer_en": DISCLAIMER_EN, "disclaimer_hi": DISCLAIMER_HI}


def statement(s: Statement) -> Json:
    return with_why({"text_en": s.text_en, "text_hi": s.text_hi, "ref": s.ref}, s.why)


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
        "label_en": s.label_en[:1].upper() + s.label_en[1:],
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


class ReasonTable:
    """Period-judgement reasons, each stored once: the same lord gives the same role and
    strength reasons in every period it rules, so items list reason ids (``r1``, ``r2``, ... in
    first-use order, hence deterministic) and ``periods.reasons`` maps id -> reason."""

    def __init__(self) -> None:
        self.by_id: dict[str, Json] = {}
        self._ids: dict[str, str] = {}

    def add(self, r: Reason) -> str:
        entry: Json = {
            "code": r.code,
            "text": r.text,
            "delta": float(r.delta),
            "ref": r.ref,
        }
        with_why(entry, [r.why])
        if r.lord and r.level:
            # name whose period this is about: "Rahu (antardasha lord) is strong (85/100)"
            name = cap_names(r.lord)
            why = entry["why"]
            assert isinstance(why, list)
            if why and why[0].startswith(name):
                why[0] = f"{name} ({r.level} lord){why[0][len(name) :]}"
        key = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        if key not in self._ids:
            self._ids[key] = f"r{len(self._ids) + 1}"
            self.by_id[self._ids[key]] = entry
        return self._ids[key]


def judgement(j: PeriodJudgement, table: ReasonTable, top: int | None = None) -> Json:
    """``top``: keep only the ``top`` reasons with the largest |delta| (ties in original order).
    ``reasons`` lists ids into ``table``."""
    reasons = list(j.reasons)
    if top is not None:
        keep = sorted(range(len(reasons)), key=lambda i: (-abs(reasons[i].delta), i))[:top]
        reasons = [reasons[i] for i in sorted(keep)]
    return {
        "score": j.score,
        "nature": j.nature,
        "houses": list(j.areas),
        "reasons_total": len(j.reasons),
        "reasons": [table.add(r) for r in reasons],
    }


def period(
    p: DashaPeriod, j: PeriodJudgement, tz: str, table: ReasonTable, top: int | None
) -> Json:
    return {
        "lord": p.lord,
        **instant("start", p.start_utc, tz),
        **instant("end", p.end_utc, tz),
        "judgement": judgement(j, table, top),
    }


def timeline_item(i: TimelineItem, tz: str, table: ReasonTable, top: int | None) -> Json:
    out: Json = {
        "id": i.id,
        "level": i.level,
        "lords": list(i.lords),
        **instant("start", i.start_utc, tz),
        **instant("end", i.end_utc, tz),
        "score": i.judgement.score,
        "nature": i.judgement.nature,
        "areas": list(i.areas),
        "advice_key": i.advice_key,
        # score and nature are given once, at the item level
        "judgement": {
            k: v
            for k, v in judgement(i.judgement, table, top).items()
            if k not in ("score", "nature")
        },
        "why": list(i.why),
        "ref": i.ref,
    }
    return out


def _advice() -> Json:
    return {
        f"advice.{nature}": {"en": node["en"], "hi": node["hi"]}
        for nature, node in load_data("decisions")["advice"].items()
    }


def window_reason(r: WindowReason, full: bool = True) -> Json:
    """Full: the statement with ``why`` and ``ref``. Otherwise a pointer (``source`` is the id
    of the timeline item or transit entry, which carries the statement) and its ``share``."""
    head: Json = {"source": r.source, "share": round(r.share, SHARE_DECIMALS)}
    if not full:
        return head
    return {
        "code": r.code,
        **head,
        "text_en": r.text_en,
        "text_hi": r.text_hi,
        "why": list(r.why),
        "ref": r.ref,
    }


def month(m: MonthRating, tz: str, full: bool = True) -> Json:
    return {
        **instant("start", m.start_utc, tz),
        **instant("end", m.end_utc, tz),
        "score": m.score,
        "nature": m.nature,
        "dasha_score": round(m.dasha_score, SCORE_DECIMALS),
        "transit_score": round(m.transit_score, SCORE_DECIMALS),
        "reasons": [window_reason(r, full) for r in m.reasons],
    }


def transit(t: TransitOverlay, tz: str) -> Json:
    return {
        "id": t.id,
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
    current: Sequence[tuple[str, DashaPeriod, PeriodJudgement]],
    tl: Timeline,
    tz: str,
    full: bool = False,
) -> Json:
    note = load_data("transit")["scoring_note"]
    top = None if full else SUMMARY_REASONS
    table = ReasonTable()
    current_json = {level: period(p, j, tz, table, top) for level, p, j in current}
    timeline_json = [timeline_item(i, tz, table, top) for i in tl.items]
    return {
        "scoring_note": {"en": note["en"], "hi": note["hi"], "ref": note["ref"]},
        **instant("now", tl.now_utc, tz),
        **instant("window_end", tl.end_utc, tz),
        "advice": _advice(),
        "current": current_json,
        "timeline": timeline_json,
        "reasons": table.by_id,
        "months": [month(m, tz, full) for m in tl.months],
        "best_windows": [month(m, tz, full) for m in tl.best_windows],
        "challenging_windows": [month(m, tz, full) for m in tl.challenging_windows],
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
    out: Json = {
        "meta": meta,
        "areas": {k: area(k, a) for k, a in areas.items()},
        "income_sources": [income_source(s) for s in income],
        "lucky": [lucky_set(s) for s in lucky],
        "functional_roles": {g.value: functional_role(r) for g, r in roles.items()},
        "periods": periods_json,
        **disclaimer(),
    }
    friendly_tree(out)
    return out


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
    out: Json = {
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
    friendly_tree(out)
    return out
