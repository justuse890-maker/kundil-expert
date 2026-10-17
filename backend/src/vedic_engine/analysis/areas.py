"""Life areas, major income sources and lucky elements, read from the chart.

``life_areas(k, gender)`` gives one ``AreaReading`` per area in ``AREAS``. Every ``Statement`` is
filled from a template in ``data/{areas,personality,career,income}.json`` (English and Hindi),
carries ``why`` (the chart facts it rests on, e.g. "10th lord Saturn in 3rd (Karka), combust")
and ``ref`` (the classical source; see each file's ``_source`` for what was checked).

Area ``score`` (0-100) follows Phaladeepika Ch 15 v. 25 (a bhava gives good results when its
lord and its karaka are strong): the mean ``planet_strength`` of the area's key planets,

* personality: lagna lord, Moon; career: 10th lord, its karaka(s);
* income: 2nd, 10th and 11th lords; marriage: 7th lord, the spouse karaka(s) for ``gender``;
* health: lagna lord, Moon; wealth: 2nd, 5th, 9th and 11th lords;
* children: 5th lord, Jupiter; education: 4th and 5th lords, Mercury.

Each planet counts once. ``summary_key`` is ``"<area>.<level>"``: strong (score >= 60), weak
(< 40), otherwise moderate; the text is ``areas.json`` ``summaries[level]``.

``income_sources`` ranks the major income sources: contributions from the 10th, 11th and 2nd
lords (type from the house each occupies), the planets in the 2nd and 11th (type from the
planet), and earning away from the native place (Phaladeepika Ch 5 v. 9). Contributions of the
same type merge; a source's score is its strongest contributor's ``planet_strength``. Rank:
score descending, then the strongest contributor's ``Graha`` order, then the type key.

Chandra kundli (``meta["lagna_basis"] == "moon"``): the lagna is the Moon, so houses are counted
from the Moon; every reading starts with a note saying so, and readings from divisional lagnas
(D9 7th lord, D10 lagna lord) are left out because they need the birth time.

Traditional Jyotish interpretation: guidance, not certainty.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from statistics import fmean
from typing import Any, Literal, Protocol, cast

from vedic_engine.analysis.dasha_judgement import moon_waxing
from vedic_engine.analysis.functional import houses_ruled, load_data
from vedic_engine.analysis.strength import ChartFacts, Strength, d9_dignity, planet_strength
from vedic_engine.angles import nak_of, sign_of
from vedic_engine.bhava import BhavaFact, drishti
from vedic_engine.constants import NAKSHATRAS, RASHI_LORD, RASHIS, VIMSHOTTARI_ORDER, Graha
from vedic_engine.dignity import Dignity
from vedic_engine.doshas import ManglikResult
from vedic_engine.lagna import house_of

AREAS: tuple[str, ...] = (
    "personality",
    "career",
    "income",
    "marriage",
    "health",
    "wealth",
    "children",
    "education",
)
DATA_FILES: tuple[str, ...] = ("areas", "personality", "career", "income", "lucky")
LUCKY_KINDS: tuple[str, ...] = (
    "colour",
    "gemstone",
    "day",
    "number",
    "direction",
    "deity",
    "metal",
)
STRONG_FROM = 60
WEAK_BELOW = 40
DUSTHANAS: tuple[int, ...] = (6, 8, 12)
DHANA_HOUSES: tuple[int, ...] = (1, 2, 5, 9, 11)
# Phaladeepika Ch 2 v. 27 (the waning Moon is added at call time; Mercury's association is not
# evaluated, as in functional.py).
_NATURAL_MALEFICS = frozenset({Graha.SUN, Graha.MARS, Graha.SATURN, Graha.RAHU, Graha.KETU})
_GRAHA_ORDER = {g: i for i, g in enumerate(Graha)}

Gender = Literal["male", "female"]
Text = tuple[str, str]  # (en, hi)


class AreaFacts(ChartFacts, Protocol):
    """``ChartFacts`` plus the bhava table, Manglik result and meta that ``Kundli`` carries."""

    @property
    def bhavas_detail(self) -> Sequence[BhavaFact]: ...
    @property
    def manglik(self) -> ManglikResult: ...
    @property
    def meta(self) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class Statement:
    text_en: str
    text_hi: str
    why: tuple[str, ...]
    ref: str


@dataclass(frozen=True, slots=True)
class AreaReading:
    score: int
    summary_key: str
    statements: tuple[Statement, ...]


@dataclass(frozen=True, slots=True)
class IncomeSource:
    """One ranked income source; ``planets`` strongest first, ``roles`` e.g. ("10th lord",)."""

    rank: int
    type: str
    label_en: str
    label_hi: str
    score: int
    planets: tuple[Graha, ...]
    roles: tuple[str, ...]
    why: tuple[str, ...]
    ref: str


@dataclass(frozen=True, slots=True)
class LuckyItem:
    kind: str
    value_en: str
    value_hi: str
    source: str
    label: str = "traditional association"


@dataclass(frozen=True, slots=True)
class LuckySet:
    """Associations of one graha; ``bases`` says why it was chosen (lagna lord, Moon-sign lord)."""

    graha: Graha
    bases: tuple[str, ...]
    items: tuple[LuckyItem, ...]


# --- text helpers --------------------------------------------------------------------------


def _labels() -> Mapping[str, Any]:
    labels: Mapping[str, Any] = load_data("areas")["labels"]
    return labels


def _text(node: Mapping[str, Any]) -> Text:
    return node["en"], node["hi"]


def _g(g: Graha) -> Text:
    return _text(_labels()["grahas"][g.value])


def _sign(sign: int) -> Text:
    return _text(_labels()["rashis"][RASHIS[sign]])


def _ord(n: int) -> Text:
    return _text(_labels()["ordinals"][str(n)])


def _band_key(score: float) -> str:
    if score >= STRONG_FROM:
        return "strong"
    if score < WEAK_BELOW:
        return "weak"
    return "moderate"


def _band(score: int) -> Text:
    return _text(_labels()["bands"][_band_key(score)])


def _house_areas(h: int) -> Text:
    node = load_data("houses")["houses"][str(h)]
    return ", ".join(node["en"]), ", ".join(node["hi"])


def _say(tpl: Mapping[str, Any], why: Sequence[str], ref: str, **kw: Text | str | int) -> Statement:
    en = {k: v[0] if isinstance(v, tuple) else v for k, v in kw.items()}
    hi = {k: v[1] if isinstance(v, tuple) else v for k, v in kw.items()}
    return Statement(
        text_en=tpl["en"].format(**en),
        text_hi=tpl["hi"].format(**hi),
        why=tuple(why),
        ref=ref,
    )


# --- chart fact helpers ----------------------------------------------------------------------

_DIGNITY_WORDS: dict[Dignity, str] = {
    Dignity.EXALTED: "exalted",
    Dignity.MOOLATRIKONA: "moolatrikona",
    Dignity.OWN: "own sign",
    Dignity.GREAT_FRIEND: "great friend's sign",
    Dignity.FRIEND: "friend's sign",
    Dignity.ENEMY: "enemy's sign",
    Dignity.GREAT_ENEMY: "great enemy's sign",
    Dignity.DEBILITATED: "debilitated",
}


def _name(g: Graha) -> str:
    return g.value.capitalize()


def _rashi(sign: int) -> str:
    return RASHIS[sign].capitalize()


def _suffix(n: int) -> str:
    return str(_ord(n)[0])


class _Chart:
    """Per-call cache of the facts the readings need."""

    def __init__(self, k: AreaFacts) -> None:
        self.k = k
        self.lagna = sign_of(k.lagna_lon)
        self.moon_basis = k.meta.get("lagna_basis") == "moon"
        self._strength: dict[Graha, Strength] = {}

    def sign(self, g: Graha) -> int:
        return sign_of(self.k.grahas[g].lon)

    def house(self, g: Graha) -> int:
        return house_of(self.sign(g), self.lagna)

    def bhava(self, h: int) -> BhavaFact:
        return self.k.bhavas_detail[h - 1]

    def lord(self, h: int) -> Graha:
        return self.bhava(h).lord

    def strength(self, g: Graha) -> Strength:
        if g not in self._strength:
            self._strength[g] = planet_strength(self.k, g)
        return self._strength[g]

    def score(self, g: Graha) -> int:
        return self.strength(g).score

    def placement(self, g: Graha) -> str:
        """e.g. "Saturn in 3rd (Karka), great enemy's sign, combust"."""
        parts = [f"{_name(g)} in {_suffix(self.house(g))} ({_rashi(self.sign(g))})"]
        word = _DIGNITY_WORDS.get(self.k.dignity[g])
        if word:
            parts.append(word)
        if self.k.combust.get(g, False):
            parts.append("combust")
        return ", ".join(parts)

    def lord_fact(self, h: int) -> str:
        return f"{_suffix(h)} lord {self.placement(self.lord(h))}"

    def strength_fact(self, g: Graha) -> str:
        s = self.strength(g)
        factors = ", ".join(f"{f.name} {f.delta:+d}" for f in s.factors) or "no factors"
        return f"{_name(g)} strength {s.score}/100 ({factors})"

    def occupants(self, h: int) -> tuple[Graha, ...]:
        return tuple(self.bhava(h).occupants)


def _lord_in_house(c: _Chart, h: int) -> Statement:
    lord = c.lord(h)
    n = c.house(lord)
    return _say(
        load_data("areas")["lord_in_house"],
        [c.lord_fact(h), c.strength_fact(lord)],
        _ch24_ref(h, n),
        h=_ord(h),
        planet=_g(lord),
        n=_ord(n),
        areas_h=_house_areas(h),
        areas_n=_house_areas(n),
        score=c.score(lord),
        band=_band(c.score(lord)),
    )


def _ch24_ref(h: int, n: int) -> str:
    """BPHS Ch 24: the lord of house h in house n is verse 12 * (h - 1) + n."""
    return f"BPHS Ch 24 v. {12 * (h - 1) + n} ({_suffix(h)} lord in the {_suffix(n)})"


def _planet_in_house(c: _Chart, tpl: Mapping[str, Any], g: Graha, ref: str) -> Statement:
    return _say(
        tpl,
        [c.placement(g), c.strength_fact(g)],
        ref,
        planet=_g(g),
        n=_ord(c.house(g)),
        score=c.score(g),
        band=_band(c.score(g)),
    )


# --- areas -------------------------------------------------------------------------------------


def _personality(c: _Chart) -> list[Statement]:
    d = load_data("personality")
    tpl = d["templates"]
    out: list[Statement] = []

    element = d["elements"][d["sign_element"][c.lagna]]
    modality = d["modalities"][d["sign_modality"][c.lagna]]
    sign_traits = d["signs"][RASHIS[c.lagna]]
    out.append(
        _say(
            tpl["lagna"],
            [f"Lagna {_rashi(c.lagna)} ({element['en']}, {modality['en']})"],
            f"{sign_traits['ref']}; {d['refs']['lagna_class']}",
            sign=_sign(c.lagna),
            element=_text(element),
            modality=_text(modality),
            traits=_text(sign_traits),
        )
    )

    lord = c.lord(1)
    n = c.house(lord)
    out.append(
        _say(
            tpl["lagna_lord"],
            [f"Lagna lord {c.placement(lord)}", c.strength_fact(lord)],
            _ch24_ref(1, n),
            planet=_g(lord),
            n=_ord(n),
            sign=_sign(c.sign(lord)),
            score=c.score(lord),
            band=_band(c.score(lord)),
            text=_text(d["lagna_lord_in_house"][str(n)]),
        )
    )

    moon_sign = c.sign(Graha.MOON)
    nak, pada = nak_of(c.k.grahas[Graha.MOON].lon)
    nak_lord = VIMSHOTTARI_ORDER[nak % 9]
    nature = d["graha_nature"][nak_lord.value]
    moon_traits = d["signs"][RASHIS[moon_sign]]
    nak_name = _text(_labels()["nakshatras"][NAKSHATRAS[nak]])
    out.append(
        _say(
            tpl["moon"],
            [
                f"Moon in {_rashi(moon_sign)}, {nak_name[0]} nakshatra pada {pada}",
                f"nakshatra lord {_name(nak_lord)}",
            ],
            f"{d['refs']['moon']}; {moon_traits['ref']}; {nature['ref']}",
            sign=_sign(moon_sign),
            nakshatra=nak_name,
            nak_lord=_g(nak_lord),
            traits=_text(moon_traits),
            nature=_text(nature),
        )
    )

    sun_sign = c.sign(Graha.SUN)
    s_el = d["elements"][d["sign_element"][sun_sign]]
    s_mod = d["modalities"][d["sign_modality"][sun_sign]]
    out.append(
        _say(
            tpl["sun"],
            [f"Sun in {_suffix(c.house(Graha.SUN))} ({_rashi(sun_sign)}), {s_el['en']} sign"],
            d["refs"]["sun"],
            sign=_sign(sun_sign),
            n=_ord(c.house(Graha.SUN)),
            element=_text(s_el),
            modality=_text(s_mod),
            element_trait=_text(s_el["trait"]),
            modality_trait=_text(s_mod["trait"]),
        )
    )
    return out


def _career(c: _Chart) -> list[Statement]:
    d = load_data("career")
    tpl = d["templates"]
    lord = c.lord(10)
    n = c.house(lord)
    out = [
        _say(
            tpl["tenth_lord"],
            [c.lord_fact(10), c.strength_fact(lord)],
            _ch24_ref(10, n),
            planet=_g(lord),
            n=_ord(n),
            sign=_sign(c.sign(lord)),
            score=c.score(lord),
            band=_band(c.score(lord)),
            text=_text(d["tenth_lord_in_house"][str(n)]),
        )
    ]

    fields = d["fields"][lord.value]
    out.append(
        _say(
            tpl["fields_tenth_lord"],
            [f"10th lord is {_name(lord)}"],
            fields["ref"],
            planet=_g(lord),
            classical=_text(fields["classical"]),
            modern=_text(fields["modern"]),
        )
    )

    d9_sign = c.k.vargas.get(9, {}).get(lord.value)
    if d9_sign is not None:
        d9_lord = RASHI_LORD[d9_sign]
        f9 = d["fields"][d9_lord.value]
        out.append(
            _say(
                tpl["fields_navamsa"],
                [f"10th lord {_name(lord)} in D9 {_rashi(d9_sign)} (lord {_name(d9_lord)})"],
                f"{d['refs']['navamsa']}; {f9['ref']}",
                planet=_g(d9_lord),
                sign=_sign(d9_sign),
                classical=_text(f9["classical"]),
                modern=_text(f9["modern"]),
            )
        )

    for g in c.occupants(10):
        fields = d["fields"][g.value]
        why = [f"{c.placement(g)}", c.strength_fact(g)]
        if g.value in d["persons"]:
            out.append(
                _say(
                    tpl["occupant"],
                    why,
                    f"{d['refs']['occupant']}; {fields['ref']}",
                    planet=_g(g),
                    person=_text(d["persons"][g.value]),
                    modern=_text(fields["modern"]),
                )
            )
        else:
            out.append(
                _say(
                    tpl["occupant_node"],
                    why,
                    d["refs"]["occupant_node"],
                    planet=_g(g),
                    modern=_text(fields["modern"]),
                )
            )

    d10 = c.k.vargas.get(10, {})
    if not c.moon_basis and "lagna" in d10:
        d10_lagna = d10["lagna"]
        d10_lord = RASHI_LORD[d10_lagna]
        d10_house = house_of(d10[d10_lord.value], d10_lagna)
        out.append(
            _say(
                tpl["d10"],
                [
                    (
                        f"D10 lagna {_rashi(d10_lagna)}, lord {_name(d10_lord)} in D10 house "
                        f"{d10_house} ({_rashi(d10[d10_lord.value])})"
                    ),
                    c.strength_fact(d10_lord),
                ],
                d["refs"]["d10"],
                sign=_sign(d10_lagna),
                planet=_g(d10_lord),
                n=_ord(d10_house),
                score=c.score(d10_lord),
                band=_band(c.score(d10_lord)),
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class _Contribution:
    type: str
    planet: Graha
    role: str  # "10th lord", "11th lord", "2nd lord", "occupant", "foreign"
    score: int
    why: tuple[str, ...]
    ref: str
    phrase: Text


def _contributions(c: _Chart) -> list[_Contribution]:
    d = load_data("income")
    tpl = d["templates"]
    out: list[_Contribution] = []
    for h, role in ((10, "10th lord"), (11, "11th lord"), (2, "2nd lord")):
        lord = c.lord(h)
        n = c.house(lord)
        en, hi = d["roles"][role]["en"], d["roles"][role]["hi"]
        phrase_en = tpl["lord_phrase"]["en"].format(role=en, planet=_g(lord)[0], n=_ord(n)[0])
        phrase_hi = tpl["lord_phrase"]["hi"].format(role=hi, planet=_g(lord)[1], n=_ord(n)[1])
        out.append(
            _Contribution(
                type=d["house_type"][str(n)],
                planet=lord,
                role=role,
                score=c.score(lord),
                why=(c.lord_fact(h), c.strength_fact(lord)),
                ref=f"{_ch24_ref(h, n)}; {d['refs']['house_type']}",
                phrase=(phrase_en, phrase_hi),
            )
        )
    for h in (2, 11):
        for g in c.occupants(h):
            pt = d["planet_type"][g.value]
            out.append(
                _Contribution(
                    type=pt["type"],
                    planet=g,
                    role="occupant",
                    score=c.score(g),
                    why=(c.placement(g), c.strength_fact(g)),
                    ref=pt["ref"],
                    phrase=(
                        tpl["occupant_phrase"]["en"].format(planet=_g(g)[0], n=_ord(h)[0]),
                        tpl["occupant_phrase"]["hi"].format(planet=_g(g)[1], n=_ord(h)[1]),
                    ),
                )
            )
    foreign = _earns_abroad(c)
    if foreign:
        lord = c.lord(10)
        out.append(
            _Contribution(
                type="foreign",
                planet=lord,
                role="foreign",
                score=c.score(lord),
                why=(foreign, c.strength_fact(lord)),
                ref=d["refs"]["foreign"],
                phrase=_text(tpl["foreign_phrase"]),
            )
        )
    return out


def _earns_abroad(c: _Chart) -> str | None:
    """Phaladeepika Ch 5 v. 9, applied to the 10th house sign; the fact, or None.

    Away from the native place when the 10th sign is occupied or aspected by planets other than
    its lord, its lord neither occupies nor aspects it, and the 10th lord's navamsa is not a
    fixed sign (a fixed-sign navamsa keeps the earning at home).
    """
    tenth = c.bhava(10)
    touching = set(tenth.occupants) | set(tenth.aspected_by)
    if tenth.lord in touching:
        return None
    others = sorted(touching, key=_GRAHA_ORDER.__getitem__)
    if not others:
        return None
    d9 = c.k.vargas.get(9, {}).get(tenth.lord.value)
    if d9 is None or d9 % 3 == 1:  # fixed signs: Vrishabha, Simha, Vrishchika, Kumbha
        return None
    names = ", ".join(_name(g) for g in others)
    return (
        f"10th sign {_rashi(tenth.rashi)} occupied or aspected by {names}, not by its lord "
        f"{_name(tenth.lord)}; 10th lord in D9 {_rashi(d9)} (not fixed)"
    )


def income_sources(k: AreaFacts) -> tuple[IncomeSource, ...]:
    """Major income sources, ranked (see module docstring)."""
    return tuple(src for src, _ in _ranked_sources(_Chart(k)))


def _ranked_sources(c: _Chart) -> list[tuple[IncomeSource, tuple[Text, ...]]]:
    """Ranked sources, each with its contributors' phrases for the statement text."""
    types = load_data("income")["types"]
    by_type: dict[str, list[_Contribution]] = {}
    for contrib in _contributions(c):
        by_type.setdefault(contrib.type, []).append(contrib)

    merged: list[tuple[tuple[int, int, str], str, list[_Contribution]]] = []
    for t, contribs in by_type.items():
        contribs.sort(key=lambda x: (-x.score, _GRAHA_ORDER[x.planet], x.role))
        top = contribs[0]
        merged.append(((-top.score, _GRAHA_ORDER[top.planet], t), t, contribs))
    merged.sort(key=lambda m: m[0])

    out: list[tuple[IncomeSource, tuple[Text, ...]]] = []
    for rank, (_key, t, contribs) in enumerate(merged, start=1):
        planets = tuple(dict.fromkeys(x.planet for x in contribs))
        roles = tuple(dict.fromkeys(x.role for x in contribs))
        why = tuple(dict.fromkeys(w for x in contribs for w in x.why))
        ref = "; ".join(dict.fromkeys(part for x in contribs for part in x.ref.split("; ")))
        src = IncomeSource(
            rank=rank,
            type=t,
            label_en=types[t]["en"],
            label_hi=types[t]["hi"],
            score=contribs[0].score,
            planets=planets,
            roles=roles,
            why=why,
            ref=ref,
        )
        out.append((src, tuple(x.phrase for x in contribs)))
    return out


def _income(c: _Chart) -> list[Statement]:
    tpl = load_data("income")["templates"]["source"]
    out: list[Statement] = []
    for src, phrases in _ranked_sources(c):
        out.append(
            _say(
                tpl,
                src.why,
                src.ref,
                rank=src.rank,
                type=(src.label_en, src.label_hi),
                details=("; ".join(p[0] for p in phrases), "; ".join(p[1] for p in phrases)),
                score=src.score,
            )
        )
    return out


def _karakas_for(gender: Gender | None) -> tuple[tuple[Graha, str], ...]:
    male = (Graha.VENUS, "male")
    female = (Graha.JUPITER, "female")
    if gender == "male":
        return (male,)
    if gender == "female":
        return (female,)
    return (male, female)


def _marriage(c: _Chart, gender: Gender | None) -> list[Statement]:
    d = load_data("areas")["marriage"]
    lord = c.lord(7)
    n = c.house(lord)
    out = [
        _say(
            d["seventh_lord"],
            [c.lord_fact(7), c.strength_fact(lord)],
            _ch24_ref(7, n),
            planet=_g(lord),
            n=_ord(n),
            sign=_sign(c.sign(lord)),
            score=c.score(lord),
            band=_band(c.score(lord)),
            text=_text(d["seventh_lord_in_house"][str(n)]),
        )
    ]
    for g, who in _karakas_for(gender):
        out.append(
            _say(
                d["karaka"],
                [f"spouse karaka ({who} chart): {c.placement(g)}", c.strength_fact(g)],
                d["refs"][f"karaka_{who}"],
                planet=_g(g),
                for_chart=_text(_labels()["for_chart"][who]),
                n=_ord(c.house(g)),
                score=c.score(g),
                band=_band(c.score(g)),
            )
        )

    d9 = c.k.vargas.get(9, {})
    if not c.moon_basis and "lagna" in d9:
        d9_lagna = d9["lagna"]
        d9_lord = RASHI_LORD[(d9_lagna + 6) % 12]
        d9_sign = d9[d9_lord.value]
        dig = d9_dignity(d9_lord, d9_sign)
        dig_key = (
            {
                Dignity.EXALTED: "exalted",
                Dignity.OWN: "own",
                Dignity.DEBILITATED: "debilitated",
            }.get(dig, "ordinary")
            if dig
            else "ordinary"
        )
        d9_house = house_of(d9_sign, d9_lagna)
        out.append(
            _say(
                d["d9_seventh_lord"],
                [
                    (
                        f"D9 lagna {_rashi(d9_lagna)}; D9 7th lord {_name(d9_lord)} in "
                        f"{_rashi(d9_sign)}, D9 house {d9_house} ({dig_key})"
                    )
                ],
                d["refs"]["d9"],
                planet=_g(d9_lord),
                sign=_sign(d9_sign),
                n=_ord(d9_house),
                dignity=_text(_labels()["d9_dignity"][dig_key]),
            )
        )

    m = c.k.manglik
    hits = [
        name
        for name, hit in (("lagna", m.from_lagna), ("Moon", m.from_moon), ("Venus", m.from_venus))
        if hit
    ]
    mars = c.placement(Graha.MARS)
    out.append(
        Statement(
            text_en=d["manglik"][m.level]["en"],
            text_hi=d["manglik"][m.level]["hi"],
            why=(f"Manglik level {m.level}" + (f" (from {', '.join(hits)})" if hits else ""), mars),
            ref=d["manglik"]["ref"],
        )
    )
    return out


def _health(c: _Chart) -> list[Statement]:
    d = load_data("areas")["health"]
    out = [
        _planet_in_house(c, d["lagna_lord"], c.lord(1), d["refs"]["lagna_lord"]),
        _planet_in_house(c, d["moon"], Graha.MOON, d["refs"]["moon"]),
        _lord_in_house(c, 6),
        _lord_in_house(c, 8),
    ]
    waxing = moon_waxing(c.k)
    found = False
    for h in DUSTHANAS:
        for g in c.occupants(h):
            found = True
            malefic = g in _NATURAL_MALEFICS or (g is Graha.MOON and not waxing)
            key = "dusthana_malefic" if malefic else "dusthana_benefic"
            nature = "natural malefic" if malefic else "natural benefic"
            out.append(
                _say(
                    d[key],
                    [f"{c.placement(g)} ({nature})"],
                    d["refs"]["dusthana"],
                    planet=_g(g),
                    n=_ord(h),
                )
            )
    if not found:
        out.append(
            Statement(
                text_en=d["dusthana_empty"]["en"],
                text_hi=d["dusthana_empty"]["hi"],
                why=("6th, 8th and 12th houses unoccupied",),
                ref=d["refs"]["dusthana"],
            )
        )
    return out


def _mutual_aspect(c: _Chart, a: Graha, b: Graha) -> bool:
    sa, sb = c.sign(a), c.sign(b)
    return sb in drishti(a, sa) and sa in drishti(b, sb)


def _wealth(c: _Chart) -> list[Statement]:
    d = load_data("areas")["wealth"]
    out = [_lord_in_house(c, h) for h in (2, 11, 9, 5)]

    lords: dict[Graha, list[int]] = {}
    for h in DHANA_HOUSES:
        lords.setdefault(c.lord(h), []).append(h)
    ordered = sorted(lords, key=_GRAHA_ORDER.__getitem__)
    owned = {g: ", ".join(map(str, houses_ruled(g, c.lagna))) for g in ordered}
    pairs: list[Statement] = []
    for a, b in combinations(ordered, 2):
        if c.sign(a) == c.sign(b):
            rel, fact = "conjoined", f"conjoined in {_rashi(c.sign(a))}"
        elif _mutual_aspect(c, a, b):
            rel = "mutual_aspect"
            fact = f"in mutual aspect ({_rashi(c.sign(a))} and {_rashi(c.sign(b))})"
        else:
            continue
        pairs.append(
            _say(
                d["dhana_pair"],
                [f"{_name(a)} (lord of {owned[a]}) and {_name(b)} (lord of {owned[b]}): {fact}"],
                d["ref"],
                a=(f"{_g(a)[0]} ({owned[a]})", f"{_g(a)[1]} ({owned[a]})"),
                b=(f"{_g(b)[0]} ({owned[b]})", f"{_g(b)[1]} ({owned[b]})"),
                relation=_text(_labels()["relations"][rel]),
            )
        )
    if pairs:
        out.extend(pairs)
    else:
        facts = "; ".join(
            f"lord of {', '.join(map(str, lords[g]))} {_name(g)} in {_rashi(c.sign(g))}"
            for g in ordered
        )
        out.append(
            Statement(
                text_en=d["dhana_none"]["en"],
                text_hi=d["dhana_none"]["hi"],
                why=(facts,),
                ref=d["ref"],
            )
        )
    return out


def _children(c: _Chart) -> list[Statement]:
    d = load_data("areas")["children"]
    return [_lord_in_house(c, 5), _planet_in_house(c, d["jupiter"], Graha.JUPITER, d["ref"])]


def _education(c: _Chart) -> list[Statement]:
    d = load_data("areas")["education"]
    return [
        _lord_in_house(c, 4),
        _lord_in_house(c, 5),
        _planet_in_house(c, d["mercury"], Graha.MERCURY, d["ref"]),
    ]


def _key_planets(c: _Chart, area: str, gender: Gender | None) -> tuple[Graha, ...]:
    if area == "personality" or area == "health":
        planets = [c.lord(1), Graha.MOON]
    elif area == "career":
        planets = [c.lord(10), *c.bhava(10).karakas]
    elif area == "income":
        planets = [c.lord(2), c.lord(10), c.lord(11)]
    elif area == "marriage":
        planets = [c.lord(7), *(g for g, _ in _karakas_for(gender))]
    elif area == "wealth":
        planets = [c.lord(h) for h in (2, 5, 9, 11)]
    elif area == "children":
        planets = [c.lord(5), Graha.JUPITER]
    else:  # education
        planets = [c.lord(4), c.lord(5), Graha.MERCURY]
    return tuple(dict.fromkeys(planets))


def life_areas(k: AreaFacts, gender: str | None = None) -> dict[str, AreaReading]:
    """Readings for every area in ``AREAS`` (see module docstring).

    ``gender`` ("male", "female" or None) is used only for the marriage karaka: Venus for a male
    chart, Jupiter for a female chart, both when None.
    """
    if gender not in ("male", "female", None):
        raise ValueError(f"gender must be 'male', 'female' or None, got {gender!r}")
    g = cast(Gender | None, gender)
    c = _Chart(k)
    statements: dict[str, list[Statement]] = {
        "personality": _personality(c),
        "career": _career(c),
        "income": _income(c),
        "marriage": _marriage(c, g),
        "health": _health(c),
        "wealth": _wealth(c),
        "children": _children(c),
        "education": _education(c),
    }
    prefix: list[Statement] = []
    if c.moon_basis:
        note = load_data("areas")["moon_basis_note"]
        prefix.append(
            Statement(
                text_en=note["en"],
                text_hi=note["hi"],
                why=(
                    (
                        "birth time unknown: houses counted from the Moon sign "
                        f"({_rashi(c.sign(Graha.MOON))})"
                    ),
                ),
                ref=note["ref"],
            )
        )
    out: dict[str, AreaReading] = {}
    for area in AREAS:
        score = round(fmean(c.score(p) for p in _key_planets(c, area, g)))
        out[area] = AreaReading(
            score=score,
            summary_key=f"{area}.{_band_key(score)}",
            statements=tuple(prefix + statements[area]),
        )
    return out


def lucky_elements(k: AreaFacts) -> tuple[LuckySet, ...]:
    """Traditional associations of the lagna lord and the Moon-sign lord (``data/lucky.json``).

    One set per graha, lagna lord first; when both are the same graha, one set with both bases.
    """
    data = load_data("lucky")
    lagna_lord = RASHI_LORD[sign_of(k.lagna_lon)]
    moon_lord = RASHI_LORD[sign_of(k.grahas[Graha.MOON].lon)]
    bases: dict[Graha, list[str]] = {}
    bases.setdefault(lagna_lord, []).append("lagna_lord")
    bases.setdefault(moon_lord, []).append("moon_sign_lord")
    label = data["label"]["en"]
    sets: list[LuckySet] = []
    for g, why in bases.items():
        entry = data["planets"][g.value]
        items = tuple(
            LuckyItem(
                kind=kind,
                value_en=entry[kind]["en"],
                value_hi=entry[kind]["hi"],
                source=entry[kind]["source"],
                label=label,
            )
            for kind in LUCKY_KINDS
        )
        sets.append(LuckySet(graha=g, bases=tuple(why), items=items))
    return tuple(sets)
