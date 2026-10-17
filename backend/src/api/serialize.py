"""Engine results -> JSON-ready dicts with stable snake_case keys (Rulings R30, R31).

* Indices are 1-based and travel with their key: ``{"rashi": 4, "rashi_key": "karka"}``.
* Every instant is a pair ``<name>_utc`` (ISO 8601, ``Z``) and ``<name>_local`` (ISO 8601 with the
  offset of the birth zone), rounded to whole seconds. An offset with a sub-minute part (LMT,
  1906 Madras time) is written ``+05:53:27``; a sub-second part is rounded.
* Degrees are unrounded floats; ``dms`` is the same value truncated (never rounded up to 30)
  to hundredths of an arcsecond.
* "No change found" (infinity) is ``null``; ``edge_*`` flags say a search stopped at the end of
  the supported ephemeris range.
"""

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from vedic_engine.angles import deg_in_sign, nak_of, sign_of
from vedic_engine.constants import NAKSHATRAS, RASHIS, Graha
from vedic_engine.dasha import DashaPeriod
from vedic_engine.dasha.yogini import YOGINI_LORD
from vedic_engine.kundli import Kundli
from vedic_engine.lagna import house_of
from vedic_engine.models import EngineWarning, GrahaPosition
from vedic_engine.panchang import DayPanchang, Element, PanchangAt
from vedic_engine.timeutil import to_local

Json = dict[str, Any]
_CENTI_ARCSEC_PER_DEG = 360_000


def dms(deg: float) -> str:
    """``12°34′56.78″`` for a non-negative degree value, truncated to 0.01 arcsec."""
    total = math.floor(deg * _CENTI_ARCSEC_PER_DEG)
    d, rest = divmod(total, 3600 * 100)
    m, cs = divmod(rest, 60 * 100)
    return f"{d}°{m:02d}′{cs // 100:02d}.{cs % 100:02d}″"


def _round_seconds(dt: datetime) -> datetime:
    return (dt + timedelta(microseconds=500_000)).replace(microsecond=0)


def iso_utc(dt: datetime) -> str:
    return _round_seconds(dt.astimezone(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_local(dt: datetime, tz: str) -> str:
    local = to_local(_round_seconds(dt.astimezone(UTC)), tz)
    offset = local.utcoffset()
    assert offset is not None
    seconds = round(offset.total_seconds())
    sign = "-" if seconds < 0 else "+"
    hh, rest = divmod(abs(seconds), 3600)
    mm, ss = divmod(rest, 60)
    zone = f"{sign}{hh:02d}:{mm:02d}" + (f":{ss:02d}" if ss else "")
    return _round_seconds(local.replace(tzinfo=None)).isoformat() + zone


def instant(name: str, dt: datetime | None, tz: str) -> Json:
    """``{name_utc, name_local}``; both null for ``dt`` of None."""
    if dt is None:
        return {f"{name}_utc": None, f"{name}_local": None}
    return {f"{name}_utc": iso_utc(dt), f"{name}_local": iso_local(dt, tz)}


def rashi(sign: int) -> Json:
    return {"rashi": sign + 1, "rashi_key": RASHIS[sign]}


def position(pos: GrahaPosition) -> Json:
    nak, pada = nak_of(pos.lon)
    return {
        "lon": pos.lon,
        "deg_in_sign": deg_in_sign(pos.lon),
        "dms": dms(deg_in_sign(pos.lon)),
        **rashi(sign_of(pos.lon)),
        "nakshatra": nak + 1,
        "nakshatra_key": NAKSHATRAS[nak],
        "pada": pada,
        "lat": pos.lat,
        "speed": pos.speed,
        "retro": pos.retro,
    }


def lagna(lon: float) -> Json:
    nak, pada = nak_of(lon)
    return {
        "lon": lon,
        "deg_in_sign": deg_in_sign(lon),
        "dms": dms(deg_in_sign(lon)),
        **rashi(sign_of(lon)),
        "nakshatra": nak + 1,
        "nakshatra_key": NAKSHATRAS[nak],
        "pada": pada,
    }


def warnings(items: tuple[EngineWarning, ...]) -> list[Json]:
    return [{"code": w.code, "message": w.message} for w in items]


def element(e: Element, tz: str, *, one_based: bool = False, **extra: Any) -> Json:
    return {
        "key": e.key,
        "index": e.index + 1 if one_based else e.index,
        **extra,
        **instant("ends", e.ends_utc, tz),
    }


def panchang_at(p: PanchangAt, tz: str) -> Json:
    """Tithi 1-30, yoga 1-27 as in the engine; nakshatra (1-27) and karana (1-60) made 1-based."""
    return {
        "tithi": element(p.tithi, tz),
        "paksha": p.paksha,
        "nakshatra": element(p.nakshatra, tz, one_based=True, pada=p.pada),
        "yoga": element(p.yoga, tz),
        "karana": element(p.karana, tz, one_based=True),
        "vaar": p.vaar,
    }


def day_panchang(d: DayPanchang, tz: str) -> Json:
    return {
        "date": d.date.isoformat(),
        "tz": tz,
        **instant("sunrise", d.sunrise_utc, tz),
        **instant("sunset", d.sunset_utc, tz),
        **instant("moonrise", d.moonrise_utc, tz),
        **instant("moonset", d.moonset_utc, tz),
        "at_sunrise": panchang_at(d.at_sunrise, tz),
    }


def dasha_period(p: DashaPeriod, tz: str) -> Json:
    out: Json = {"lord": p.lord, "level": p.level}
    if p.lord in YOGINI_LORD:
        out["graha"] = YOGINI_LORD[p.lord].value
    out.update(instant("start", p.start_utc, tz))
    out.update(instant("end", p.end_utc, tz))
    out["children"] = [dasha_period(c, tz) for c in p.children]
    return out


def _finite(x: float) -> float | None:
    return None if math.isinf(x) else x


def kundli(k: Kundli, tz: str, birth_utc: datetime | None, lmt: bool, name: str | None) -> Json:
    lagna_sign = sign_of(k.lagna_lon)
    grahas: Json = {}
    for g, pos in k.grahas.items():
        grahas[g.value] = {
            **position(pos),
            "house": house_of(sign_of(pos.lon), lagna_sign),
            "dignity": k.dignity[g].value,
            "combust": k.combust[g],
            "avastha": k.avastha[g],
            "vargottama": k.vargottama[g],
        }
    meta = {
        key: k.meta[key]
        for key in (
            "engine_version",
            "settings",
            "ayanamsa_deg",
            "jd_ut",
            "time_known",
            "lagna_basis",
            "ephemeris_files",
        )
    }
    meta["ayanamsa_dms"] = dms(k.meta["ayanamsa_deg"])
    meta.update(name=name, tz=tz, lmt=lmt, **instant("birth", birth_utc, tz))
    ashtakavarga = {
        "bav": {g: list(v) for g, v in k.ashtakavarga["bav"].items()},
        "sav": list(k.ashtakavarga["sav"]),
    }
    syllable_latin, syllable_devanagari = k.name_syllable
    return {
        "meta": meta,
        "lagna": lagna(k.lagna_lon),
        "grahas": grahas,
        "bhavas": [
            {
                "house": b.house,
                **rashi(b.rashi),
                "lord": b.lord.value,
                "lord_house": b.lord_house,
                "occupants": [g.value for g in b.occupants],
                "aspected_by": [g.value for g in b.aspected_by],
                "karakas": [g.value for g in b.karakas],
            }
            for b in k.bhavas_detail
        ],
        "panchang": panchang_at(k.panchang, tz),
        "vargas": {
            f"d{n}": {key: rashi(sign) for key, sign in chart.items()}
            for n, chart in sorted(k.vargas.items())
        },
        "vimshottari": [dasha_period(p, tz) for p in k.vimshottari],
        "yogini": [dasha_period(p, tz) for p in k.yogini],
        "doshas": {
            "manglik": {
                "from_lagna": k.manglik.from_lagna,
                "from_moon": k.manglik.from_moon,
                "from_venus": k.manglik.from_venus,
                "level": k.manglik.level,
            },
            "kaal_sarpa": None
            if k.kaal_sarpa is None
            else {
                "kind": k.kaal_sarpa.kind,
                "name": k.kaal_sarpa.name,
                "outside": [g.value for g in k.kaal_sarpa.outside],
            },
            "sade_sati": [
                {
                    "kind": s.kind,
                    **instant("start", s.start_utc, tz),
                    **instant("end", s.end_utc, tz),
                }
                for s in k.sade_sati
            ],
        },
        "shadbala": None
        if k.shadbala is None
        else {
            g.value: {
                "sthana": r.sthana,
                "dig": r.dig,
                "kaala": r.kaala,
                "cheshta": r.cheshta,
                "naisargika": r.naisargika,
                "drik": r.drik,
                "total_virupa": r.total_virupa,
                "total_rupa": r.total_rupa,
                "required_rupa": r.required_rupa,
                "ratio": r.ratio,
                "components": dict(r.components),
            }
            for g, r in k.shadbala.items()
        },
        "ashtakavarga": ashtakavarga,
        "sensitivity": [
            {
                "item": s.item,
                "minutes_before": _finite(s.minutes_before),
                "minutes_after": _finite(s.minutes_after),
                "edge_before": s.edge_before,
                "edge_after": s.edge_after,
            }
            for s in k.sensitivity
        ],
        "name_syllable": {"latin": syllable_latin, "devanagari": syllable_devanagari},
        "warnings": warnings(k.warnings),
    }


def transit(
    at_utc: datetime,
    positions: dict[Graha, GrahaPosition],
    natal: tuple[int, int, str] | None = None,
) -> Json:
    """Positions at ``at_utc``; ``natal`` = (lagna sign, moon sign, lagna basis) adds houses."""
    grahas: Json = {}
    for g, pos in positions.items():
        entry = position(pos)
        if natal is not None:
            sign = sign_of(pos.lon)
            entry["house_from_lagna"] = house_of(sign, natal[0])
            entry["house_from_moon"] = house_of(sign, natal[1])
        grahas[g.value] = entry
    out: Json = {"datetime_utc": iso_utc(at_utc), "grahas": grahas}
    if natal is not None:
        out["natal"] = {"lagna": rashi(natal[0]), "moon": rashi(natal[1]), "lagna_basis": natal[2]}
    return out
