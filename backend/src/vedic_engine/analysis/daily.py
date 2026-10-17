"""Today's guidance: hora schedule and colours, body language and decisions for one local date.

``daily(k, date, tz, lat, lon)``:

* ``vaar``: the weekday of the civil ``date`` (``civil_vaar``): the Vedic day that starts at
  that date's sunrise; its lord rules the first hora.
* ``horas``: 24 planetary hours from sunrise to the next sunrise. The 12 day horas each last
  (sunset - sunrise) / 12 and the 12 night horas (next sunrise - sunset) / 12; sunrise and
  sunset are the engine's (``day_panchang``, the sunrise convention in ``Settings``). Lords
  follow the Chaldean order ``CHALDEAN`` from the weekday lord.
* Each hora is ``favourable`` when its lord is a functional benefic or yogakaraka of this chart,
  ``avoid`` when a functional malefic (``functional_roles``); colours from ``hora.json``.
* ``colour_today``: the weekday lord's colour if it is a functional benefic / yogakaraka,
  otherwise the strongest such graha (yogakaraka first, then ``planet_strength``, then
  ``Graha`` order). ``colour_avoid``: the weekday lord's colour if it is a functional malefic,
  otherwise the weakest functional malefic; None when the chart has no functional malefic
  among the seven hora lords.
* ``body_language``: by the lagna's element and the running maha (and antar) lord.
* ``decisions``: by the running antar's ``judge_period`` nature and the houses it activates.

Traditional Jyotish interpretation: guidance, not certainty.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from vedic_engine.analysis.areas import Statement
from vedic_engine.analysis.dasha_judgement import judge_period, moon_waxing
from vedic_engine.analysis.functional import FunctionalRole, Role, functional_roles, load_data
from vedic_engine.analysis.strength import planet_strength
from vedic_engine.analysis.timeline import current_periods, lords_text, settings_of
from vedic_engine.angles import sign_of
from vedic_engine.constants import RASHIS, VAARS, Graha
from vedic_engine.kundli import Kundli
from vedic_engine.models import InputError, Settings
from vedic_engine.panchang import DayPanchang, day_panchang

CHALDEAN: tuple[Graha, ...] = (
    Graha.SATURN, Graha.JUPITER, Graha.MARS, Graha.SUN, Graha.VENUS, Graha.MERCURY, Graha.MOON,
)  # fmt: skip
VAAR_LORD: dict[str, Graha] = {
    "ravi": Graha.SUN,
    "soma": Graha.MOON,
    "mangala": Graha.MARS,
    "budha": Graha.MERCURY,
    "guru": Graha.JUPITER,
    "shukra": Graha.VENUS,
    "shani": Graha.SATURN,
}
ELEMENTS: tuple[str, ...] = ("fire", "earth", "air", "water")  # sign index % 4
DATA_FILES: tuple[str, ...] = ("hora", "transit", "body_language", "decisions")
_GOOD = (Role.YOGAKARAKA, Role.BENEFIC)


@dataclass(frozen=True, slots=True)
class Colour:
    en: str
    hi: str
    source: str


@dataclass(frozen=True, slots=True)
class Hora:
    index: int  # 0-23
    lord: Graha
    start_utc: datetime
    end_utc: datetime
    colour: Colour
    favourable: bool
    avoid: bool
    text_en: str
    text_hi: str
    why: tuple[str, ...]
    ref: str


@dataclass(frozen=True, slots=True)
class ColourPick:
    graha: Graha
    en: str
    hi: str
    source: str
    text_en: str
    text_hi: str
    why: tuple[str, ...]
    ref: str


@dataclass(frozen=True, slots=True)
class Decision:
    kind: str  # "favourable" | "mixed" | "challenging" | "none"
    category: str | None
    text_en: str
    text_hi: str
    why: tuple[str, ...]
    ref: str


@dataclass(frozen=True, slots=True)
class DailyGuidance:
    date: date
    tz: str
    vaar: str
    vaar_lord: Graha
    sunrise_utc: datetime
    sunset_utc: datetime
    next_sunrise_utc: datetime
    horas: tuple[Hora, ...]
    favourable_horas: tuple[int, ...]
    avoid_horas: tuple[int, ...]
    colour_today: ColourPick
    colour_avoid: ColourPick | None
    body_language: tuple[Statement, ...]
    decisions: tuple[Decision, ...]


def vaar_lord(vaar: str) -> Graha:
    return VAAR_LORD[vaar]


def civil_vaar(day: date) -> str:
    """Weekday of the civil date ``day``. Its sunrise (in the given zone) falls on that date,
    so the Vedic day that starts at that sunrise has this weekday. ``panchang._vaar`` (the
    weekday at an instant, by local mean time, as used for birth) is deliberately not used:
    where the zone is far from local mean time (Kiritimati, UTC+14) the two dates differ."""
    return VAARS[day.weekday()]


def role_scope(k: Kundli) -> str:
    """How a functional role is qualified in ``why``: the lagna, or the Moon-based chart."""
    return "for this chart (Moon-based)" if k.meta["lagna_basis"] == "moon" else "for this lagna"


def _day(
    day: date, tz: str, lat: float, lon: float, alt: float, settings: Settings, purpose: str
) -> DayPanchang:
    try:
        return day_panchang(day, tz, lat, lon, alt, settings)
    except InputError as exc:
        if type(exc) is not InputError:  # unknown zone, date out of range: not a polar day
            raise
        raise InputError(
            f"no sunrise or sunset on {day.isoformat()} at latitude {lat}, needed {purpose}"
        ) from exc


def _label(g: Graha) -> tuple[str, str]:
    node = load_data("areas")["labels"]["grahas"][g.value]
    return node["en"], node["hi"]


def _colour(g: Graha) -> Colour:
    c = load_data("hora")["colours"][g.value]
    return Colour(c["en"], c["hi"], c["source"])


def _boundaries(a: datetime, b: datetime) -> list[datetime]:
    step = (b - a) / 12
    return [a + step * i for i in range(12)] + [b]


def _horas(
    day: date,
    lord0: Graha,
    rise: datetime,
    sset: datetime,
    next_rise: datetime,
    roles: Mapping[Graha, FunctionalRole],
    scope: str,
) -> tuple[Hora, ...]:
    data = load_data("hora")
    edges = _boundaries(rise, sset) + _boundaries(sset, next_rise)[1:]
    i0 = CHALDEAN.index(lord0)
    out: list[Hora] = []
    for i in range(24):
        g = CHALDEAN[(i0 + i) % 7]
        role = roles[g]
        good, bad = role.role in _GOOD, role.role == Role.MALEFIC
        tpl = data["hora"]["favourable" if good else "avoid" if bad else "neutral"]
        en, hi = _label(g)
        out.append(
            Hora(
                index=i,
                lord=g,
                start_utc=edges[i],
                end_utc=edges[i + 1],
                colour=_colour(g),
                favourable=good,
                avoid=bad,
                text_en=tpl["en"].format(graha=en),
                text_hi=tpl["hi"].format(graha=hi),
                why=(
                    (
                        f"{'day' if i < 12 else 'night'} hora {i % 12 + 1} of {day.isoformat()}; "
                        f"day starts with the {lord0.value} hora"
                    ),
                    f"{g.value} is {role.role.value} {scope}: {role.why}",
                ),
                ref=f"{data['order_ref']}; role: {role.ref}",
            )
        )
    return tuple(out)


def _pick(
    kind: str, g: Graha, roles: Mapping[Graha, FunctionalRole], basis: str, scope: str
) -> ColourPick:
    data = load_data("hora")
    c = _colour(g)
    en, hi = _label(g)
    tpl = data[kind]
    return ColourPick(
        graha=g,
        en=c.en,
        hi=c.hi,
        source=c.source,
        text_en=tpl["en"].format(colour=c.en, graha=en),
        text_hi=tpl["hi"].format(colour=c.hi, graha=hi),
        why=(basis, f"{g.value} is {roles[g].role.value} {scope}: {roles[g].why}"),
        ref=f"colour: {c.source}; role: {roles[g].ref}",
    )


def _colours(
    k: Kundli, lord0: Graha, roles: Mapping[Graha, FunctionalRole]
) -> tuple[ColourPick, ColourPick | None]:
    scope = role_scope(k)
    good = [g for g in CHALDEAN if roles[g].role in _GOOD]
    bad = [g for g in CHALDEAN if roles[g].role == Role.MALEFIC]
    order = {g: i for i, g in enumerate(Graha)}
    if lord0 in good:
        today, basis = lord0, f"weekday lord {lord0.value} is a functional benefic"
    elif good:
        today = min(
            good,
            key=lambda g: (
                roles[g].role != Role.YOGAKARAKA,
                -planet_strength(k, g).score,
                order[g],
            ),
        )
        basis = (
            f"weekday lord {lord0.value} is not a functional benefic; {today.value} is the "
            f"strongest benefic (strength {planet_strength(k, today).score}/100)"
        )
    else:  # every lagna has at least a benefic lagna/trikona lord; kept for safety
        today, basis = (
            lord0,
            f"no functional benefic among the hora lords; weekday lord {lord0.value}",
        )
    avoid: ColourPick | None = None
    if lord0 in bad:
        avoid = _pick(
            "colour_avoid",
            lord0,
            roles,
            f"weekday lord {lord0.value} is a functional malefic",
            scope,
        )
    elif bad:
        g = min(bad, key=lambda g: (planet_strength(k, g).score, order[g]))
        avoid = _pick(
            "colour_avoid",
            g,
            roles,
            f"{g.value} is the weakest functional malefic (strength {planet_strength(k, g).score}/100)",
            scope,
        )
    return _pick("colour_today", today, roles, basis, scope), avoid


def daily(k: Kundli, day: date, tz: str, lat: float, lon: float, alt: float = 0.0) -> DailyGuidance:
    """Guidance for the local civil ``day`` at a place (see module docstring)."""
    settings = settings_of(k)
    p = _day(day, tz, lat, lon, alt, settings, f"to begin {day.isoformat()}'s horas")
    nxt = _day(
        day + timedelta(days=1), tz, lat, lon, alt, settings, f"to end {day.isoformat()}'s horas"
    )
    vaar = civil_vaar(day)
    lord0 = vaar_lord(vaar)
    lagna = sign_of(k.lagna_lon)
    roles = functional_roles(lagna, moon_waxing(k))
    horas = _horas(day, lord0, p.sunrise_utc, p.sunset_utc, nxt.sunrise_utc, roles, role_scope(k))
    colour_today, colour_avoid = _colours(k, lord0, roles)

    maha, antar, _ = current_periods(k, p.sunrise_utc)
    bl = load_data("body_language")
    element = ELEMENTS[lagna % 4]
    basis = (
        "Moon sign used as lagna (birth time unknown)"
        if k.meta["lagna_basis"] == "moon"
        else "lagna"
    )
    body = [
        Statement(
            text_en=bl["elements"][element]["en"],
            text_hi=bl["elements"][element]["hi"],
            why=(f"{basis} {RASHIS[lagna]}: {element} element",),
            ref=bl["elements"][element]["ref"],
        )
    ]
    for level, period in (("maha", maha), ("antar", antar)):
        if level == "antar" and antar.lord == maha.lord:
            continue
        node = bl["lords"][period.lord]
        body.append(
            Statement(
                text_en=node["en"],
                text_hi=node["hi"],
                why=(
                    (
                        f"current {level} dasha lord {period.lord} "
                        f"({period.start_utc:%Y-%m-%d} to {period.end_utc:%Y-%m-%d})"
                    ),
                ),
                ref=node["ref"],
            )
        )

    dec = load_data("decisions")
    j = judge_period(k, (Graha(maha.lord), Graha(antar.lord)))
    lords_en, _ = lords_text((maha.lord, antar.lord))
    base_why = (
        f"antar {lords_en}: judge_period score {j.score} ({j.nature})",
        f"its lords rule or occupy houses {', '.join(map(str, j.areas))}",
    )
    decisions: list[Decision] = []
    for key, cat in dec["categories"].items():
        hit = sorted(set(cat["houses"]) & set(j.areas))
        if not hit:
            continue
        tpl = dec["kinds"][j.nature]
        decisions.append(
            Decision(
                kind=j.nature,
                category=key,
                text_en=tpl["en"].format(category=cat["label"]["en"]),
                text_hi=tpl["hi"].format(category=cat["label"]["hi"]),
                why=(*base_why, f"{key}: houses {', '.join(map(str, hit))}"),
                ref=dec["ref"],
            )
        )
    if not decisions:
        decisions.append(
            Decision("none", None, dec["none"]["en"], dec["none"]["hi"], base_why, dec["ref"])
        )
    return DailyGuidance(
        date=day,
        tz=tz,
        vaar=vaar,
        vaar_lord=lord0,
        sunrise_utc=p.sunrise_utc,
        sunset_utc=p.sunset_utc,
        next_sunrise_utc=nxt.sunrise_utc,
        horas=horas,
        favourable_horas=tuple(h.index for h in horas if h.favourable),
        avoid_horas=tuple(h.index for h in horas if h.avoid),
        colour_today=colour_today,
        colour_avoid=colour_avoid,
        body_language=tuple(body),
        decisions=tuple(decisions),
    )
