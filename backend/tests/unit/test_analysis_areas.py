"""Life areas, major income sources and lucky elements (analysis Task 4)."""

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from vedic_engine import ephemeris
from vedic_engine.analysis import (
    AreaReading,
    IncomeSource,
    life_areas,
    lucky_elements,
    planet_strength,
)
from vedic_engine.analysis.areas import AREAS, DATA_FILES, ROLE_PRIORITY, income_sources
from vedic_engine.analysis.functional import load_data
from vedic_engine.bhava import BhavaFact, bhava_facts, vargottama
from vedic_engine.constants import RASHI_LORD, RASHIS, Graha
from vedic_engine.dignity import Dignity, dignity
from vedic_engine.doshas import ManglikResult, manglik
from vedic_engine.kundli import Kundli, build_kundli
from vedic_engine.models import BirthInput
from vedic_engine.varga import varga_chart

DELHI_1947 = BirthInput(datetime(1947, 8, 15, 0, 0), "Asia/Kolkata", 28.6139, 77.2090)

FORBIDDEN_EN = (
    "definitely",
    "guarantee",
    "100%",
    "certainly",
    "surely",
    "undoubtedly",
    "doubtless",
    "without doubt",
    "for sure",
    "always",
    "never",
    "99%",
)
FORBIDDEN_HI = ("निश्चित", "गारंटी", "अवश्य", "ज़रूर", "जरूर", "पक्का", "हमेशा", "कभी नहीं", "100%")


@cache
def _india() -> Kundli:
    return build_kundli(DELHI_1947)


@pytest.fixture(autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


# --- synthetic charts --------------------------------------------------------------------


@dataclass(frozen=True)
class _Pos:
    lon: float


@dataclass(frozen=True)
class _Bala:
    ratio: float


@dataclass(frozen=True)
class _Facts:
    lagna_lon: float
    grahas: Mapping[Graha, _Pos]
    dignity: Mapping[Graha, Dignity]
    combust: Mapping[Graha, bool]
    shadbala: Mapping[Graha, _Bala]
    vargottama: Mapping[Graha, bool]
    vargas: Mapping[int, Mapping[str, int]]
    bhavas_detail: Sequence[BhavaFact]
    manglik: ManglikResult
    meta: Mapping[str, Any] = field(default_factory=dict)


# Every graha in the middle (15 deg) of a sign index; lagna Mesha.
_BASE_SIGNS: dict[Graha, int] = {
    Graha.SUN: 4,
    Graha.MOON: 1,
    Graha.MARS: 2,
    Graha.MERCURY: 5,
    Graha.JUPITER: 8,
    Graha.VENUS: 3,
    Graha.SATURN: 9,
    Graha.RAHU: 0,
    Graha.KETU: 6,
}


def _synthetic(
    signs: Mapping[Graha, int],
    lagna_sign: int = 0,
    meta: Mapping[str, Any] | None = None,
    shadbala: Mapping[Graha, float] | None = None,
) -> _Facts:
    lons = {g: s * 30.0 + 15.0 for g, s in signs.items()}
    lagna_lon = lagna_sign * 30.0 + 15.0
    points = {**{g.value: lon for g, lon in lons.items()}, "lagna": lagna_lon}
    return _Facts(
        lagna_lon=lagna_lon,
        grahas={g: _Pos(lon) for g, lon in lons.items()},
        dignity={g: dignity(g, lon, lons) for g, lon in lons.items()},
        combust={g: False for g in lons},
        shadbala={g: _Bala(r) for g, r in (shadbala or {}).items()},
        vargottama=vargottama(lons),
        vargas={n: varga_chart(points, n) for n in (9, 10)},
        bhavas_detail=bhava_facts(lagna_lon, lons),
        manglik=manglik(lons[Graha.MARS], lagna_lon, lons[Graha.MOON], lons[Graha.VENUS]),
        meta=meta or {},
    )


def _all_readings() -> Iterator[tuple[str, AreaReading]]:
    charts: list[Any] = [_india(), _synthetic(_BASE_SIGNS)]
    for sign in range(12):  # Saturn (10th lord for Mesha) through every house
        charts.append(_synthetic({**_BASE_SIGNS, Graha.SATURN: sign}))
    charts.append(_synthetic(_BASE_SIGNS, lagna_sign=1, meta={"lagna_basis": "moon"}))
    for chart in charts:
        for gender in ("male", "female", None):
            yield from life_areas(chart, gender=gender).items()


def _income_type_of_tenth_lord(facts: _Facts) -> str:
    for src in income_sources(facts):
        if "10th lord" in src.roles:
            return src.type
    raise AssertionError("no source from the 10th lord")


# --- India 1947 ----------------------------------------------------------------------------


def test_areas_keys() -> None:
    areas = life_areas(_india())
    assert (
        tuple(areas)
        == AREAS
        == (
            "personality",
            "career",
            "income",
            "marriage",
            "health",
            "wealth",
            "children",
            "education",
        )
    )
    for reading in areas.values():
        assert 0 <= reading.score <= 100
        assert reading.statements


def test_india_career_cites_tenth_lord_saturn() -> None:
    # Vrishabha lagna: the 10th is Kumbha, lord Saturn, who stands in Karka (the 3rd).
    k = _india()
    assert RASHIS[k.bhavas_detail[9].rashi] == "kumbha"
    career = life_areas(k)["career"]
    whys = [w for s in career.statements for w in s.why]
    assert any("10th lord Saturn in 3rd (Karka)" in w for w in whys), whys
    tenth = career.statements[0]
    assert tenth.ref == "BPHS Ch 24 v. 111 (10th lord in the 3rd)"


def test_india_personality_lagna_and_lord() -> None:
    p = life_areas(_india())["personality"]
    whys = [w for s in p.statements for w in s.why]
    assert "Lagna Vrishabha (earth, fixed)" in whys
    # Venus, lord of Vrishabha, is in Karka (3rd) in the 1947 chart.
    assert any(w.startswith("Lagna lord Venus in 3rd (Karka)") for w in whys)
    assert any(s.ref.startswith("BPHS Ch 24 v. 3 ") for s in p.statements)


def test_lucky_elements_traditional_and_cited() -> None:
    sets = lucky_elements(_india())
    # Lagna lord Venus; Moon in Karka -> Moon-sign lord Moon.
    assert [(s.graha, s.bases) for s in sets] == [
        (Graha.VENUS, ("lagna_lord",)),
        (Graha.MOON, ("moon_sign_lord",)),
    ]
    kinds = {i.kind for i in sets[0].items}
    assert kinds == {"colour", "gemstone", "day", "number", "direction", "deity", "metal"}
    for s in sets:
        for item in s.items:
            assert item.label == "traditional association"
            assert item.label_hi == "पारंपरिक संबंध"
            assert item.source
            assert item.value_en and item.value_hi
    number = next(i for i in sets[0].items if i.kind == "number")
    assert number.source == "popular tradition"
    assert "BPHS" not in number.source
    gem = next(i for i in sets[0].items if i.kind == "gemstone")
    assert gem.source == "Phaladeepika Ch 2 v. 29"


def test_lucky_dedupes_when_lagna_is_moon_sign() -> None:
    facts = _synthetic(_BASE_SIGNS, lagna_sign=1, meta={"lagna_basis": "moon"})
    sets = lucky_elements(facts)
    assert [(s.graha, s.bases) for s in sets] == [(Graha.VENUS, ("lagna_lord", "moon_sign_lord"))]


# --- income -------------------------------------------------------------------------------


def test_income_ranks_are_deterministic() -> None:
    k = _india()
    first = income_sources(k)
    assert first == income_sources(k)
    assert [s.rank for s in first] == list(range(1, len(first) + 1))
    order = list(Graha)
    keys = [(-s.score, ROLE_PRIORITY.index(s.roles[0]), order.index(s.planet)) for s in first]
    assert keys == sorted(keys)
    assert len({s.planet for s in first}) == len(first)  # one entry per planet
    for s in first:
        assert isinstance(s, IncomeSource)
        assert s.why and s.ref


def test_income_tie_broken_by_role_then_graha_order() -> None:
    # Mesha lagna. Every contributor gets exactly the base strength 50: neutral dignity, no
    # shadbala, not combust, not vargottama, D9 Mithuna (neither own, exalted nor debilitated
    # for these planets), and houses 2, 3 and 11 carry no house factor.
    #   Saturn: 10th and 11th lord in Kumbha (11th) -> investments_gains; also occupant of the
    #     11th and the Phaladeepika 5.9 foreign indicator (Mars aspects Makara), both in `why`
    #   Venus: 2nd lord in Mithuna (3rd) -> own_enterprise
    #   Moon: occupant of Vrishabha (2nd) -> trade
    base = _synthetic({**_BASE_SIGNS, Graha.VENUS: 2, Graha.SATURN: 10})
    facts = replace(
        base,
        dignity={g: Dignity.NEUTRAL for g in Graha},
        vargottama={g: False for g in Graha},
        vargas={**base.vargas, 9: {g.value: 2 for g in Graha}},
    )
    srcs = income_sources(facts)
    assert {s.score for s in srcs} == {50}
    assert [(s.type, s.planet) for s in srcs] == [
        ("investments_gains", Graha.SATURN),
        ("own_enterprise", Graha.VENUS),
        ("trade", Graha.MOON),
    ]
    assert srcs[0].roles == ("10th lord", "11th lord", "occupant", "foreign")
    assert any("not by its lord Saturn" in w for w in srcs[0].why)


def test_income_one_entry_per_planet_makara_1985() -> None:
    # Makara lagna: Venus rules the 10th (Tula) and stands in Kumbha (2nd), so it is both the
    # 10th lord and an occupant of the 2nd; its type is the 10th-lord-in-2nd type.
    k = build_kundli(BirthInput(datetime(1985, 1, 20, 7, 0), "Asia/Kolkata", 28.6139, 77.2090))
    srcs = income_sources(k)
    venus = [s for s in srcs if s.planet is Graha.VENUS]
    assert len(venus) == 1
    assert venus[0].type == "family_wealth"
    assert venus[0].roles == ("10th lord", "occupant")
    assert any(w.startswith("10th lord Venus in 2nd (Kumbha)") for w in venus[0].why)
    assert len({s.planet for s in srcs}) == len(srcs)


def test_chandra_kundli_real_chart() -> None:
    birth = BirthInput(
        datetime(1990, 6, 1, 12, 0), "Asia/Kolkata", 28.6139, 77.2090, time_known=False
    )
    k = build_kundli(birth)
    assert k.shadbala is None
    areas = life_areas(k)
    for reading in areas.values():
        assert reading.statements[0].why[0].startswith("birth time unknown")
    whys = [w for r in areas.values() for s in r.statements for w in s.why]
    assert any("shadbala n/a" in w for w in whys)
    marriage = [s.text_en for s in areas["marriage"].statements]
    assert not any("lagna" in t.lower() and "Manglik" in t for t in marriage)
    strength = planet_strength(k, Graha.SATURN)
    note = [f for f in strength.factors if f.name == "shadbala"]
    assert [(f.delta, f.why) for f in note] == [(0, "Shadbala unavailable: birth time unknown")]


@pytest.mark.parametrize(
    ("saturn_sign", "expected"),
    [
        (6, "business_partnership"),  # Tula = 7th from Mesha
        (5, "service"),  # Kanya = 6th
        (10, "investments_gains"),  # Kumbha = 11th
        (11, "foreign"),  # Meena = 12th
        (7, "inheritance"),  # Vrishchika = 8th
    ],
)
def test_tenth_lord_house_sets_income_type(saturn_sign: int, expected: str) -> None:
    facts = _synthetic({**_BASE_SIGNS, Graha.SATURN: saturn_sign})
    assert RASHI_LORD[facts.bhavas_detail[9].rashi] is Graha.SATURN
    assert _income_type_of_tenth_lord(facts) == expected


def test_changing_tenth_lord_house_changes_income_type() -> None:
    types = {
        _income_type_of_tenth_lord(_synthetic({**_BASE_SIGNS, Graha.SATURN: s})) for s in range(12)
    }
    assert len(types) >= 6


# --- gender, chandra kundli, wealth -------------------------------------------------------


def test_marriage_karaka_follows_gender() -> None:
    k = _india()

    def karaka_refs(gender: str | None) -> list[str]:
        return [
            s.ref
            for s in life_areas(k, gender=gender)["marriage"].statements
            if "karaka" in " ".join(s.why)
        ]

    male, female, both = karaka_refs("male"), karaka_refs("female"), karaka_refs(None)
    assert male == ["Phaladeepika Ch 2 v. 6; BPHS Ch 32 vv. 31-34"]
    assert female == ["Phaladeepika Ch 2 v. 5"]
    assert both == male + female


def test_gender_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="gender"):
        life_areas(_india(), gender="other")


def test_chandra_kundli_prefixes_every_reading() -> None:
    facts = _synthetic(_BASE_SIGNS, lagna_sign=1, meta={"lagna_basis": "moon"})
    for name, reading in life_areas(facts).items():
        first = reading.statements[0]
        assert "birth time" in first.text_en.lower(), name
        assert "Moon" in first.text_en
        assert first.why == ("birth time unknown: houses counted from the Moon sign (Vrishabha)",)
    # Divisional-lagna readings need a birth time and are left out.
    career = life_areas(facts)["career"]
    assert not any("D10" in w for s in career.statements for w in s.why)


def test_no_prefix_for_known_time() -> None:
    for reading in life_areas(_india()).values():
        assert "birth time" not in reading.statements[0].text_en.lower()


def test_dhana_yoga_detects_conjunction() -> None:
    # Mesha lagna: Venus lords 2 (Vrishabha), Jupiter lords 9; both in Dhanu -> conjoined.
    facts = _synthetic({**_BASE_SIGNS, Graha.VENUS: 8, Graha.JUPITER: 8})
    wealth = life_areas(facts)["wealth"]
    dhana = [s for s in wealth.statements if s.ref.startswith("BPHS Ch 41")]
    assert any(
        "Jupiter (lord of 9, 12) and Venus (lord of 2, 7): conjoined in Dhanu" in w
        for s in dhana
        for w in s.why
    )


def test_dhana_yoga_absent_is_stated() -> None:
    # Mesha: lords of 1/2/5/9/11 are Mars, Venus, Sun, Jupiter, Saturn. In Mesha, Vrishabha,
    # Mithuna, Karka and Simha no two share a sign and no pair aspects each other mutually
    # (Mars aspects Karka, but Jupiter from Karka aspects Vrishchika, Meena and Makara).
    signs = {
        **_BASE_SIGNS,
        Graha.MARS: 0,
        Graha.VENUS: 1,
        Graha.SUN: 2,
        Graha.JUPITER: 3,
        Graha.SATURN: 4,
    }
    wealth = life_areas(_synthetic(signs))["wealth"]
    dhana = [s for s in wealth.statements if s.ref.startswith("BPHS Ch 41")]
    assert len(dhana) == 1
    assert dhana[0].text_en.startswith("No conjunction or mutual aspect")
    assert "lord of 9 Jupiter in Karka" in dhana[0].why[0]


# --- honesty --------------------------------------------------------------------------------


def test_every_statement_has_why_and_ref() -> None:
    for name, reading in _all_readings():
        for s in reading.statements:
            assert s.ref.strip(), (name, s)
            assert s.why and all(w.strip() for w in s.why), (name, s)
            assert s.text_en.strip() and s.text_hi.strip(), (name, s)
            assert "{" not in s.text_en and "{" not in s.text_hi, (name, s)


def test_summary_keys_resolve() -> None:
    data = load_data("areas")
    for name, reading in _all_readings():
        area, level = reading.summary_key.split(".")
        assert area == name
        assert level in data["summaries"]


def _texts(node: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(node, Mapping):
        yield path, node
        for k, v in node.items():
            yield from _texts(v, f"{path}.{k}")
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            yield from _texts(v, f"{path}[{i}]")


_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def test_all_templates_have_en_and_hi_with_same_placeholders() -> None:
    seen = 0
    for name in DATA_FILES:
        for path, node in _texts(load_data(name), name):
            if "en" in node or "hi" in node:
                assert "en" in node and "hi" in node, path
                en, hi = node["en"], node["hi"]
                assert isinstance(en, str) and en.strip(), path
                assert isinstance(hi, str) and hi.strip(), path
                assert re.search("[ऀ-ॿ]", hi), f"{path}: hi is not Devanagari"
                assert set(_PLACEHOLDER.findall(en)) == set(_PLACEHOLDER.findall(hi)), path
                seen += 1
    assert seen > 200


def test_templates_use_no_certainty_words() -> None:
    for name in DATA_FILES:
        for path, node in _texts(load_data(name), name):
            for lang, words in (("en", FORBIDDEN_EN), ("hi", FORBIDDEN_HI)):
                text = node.get(lang)
                if isinstance(text, str):
                    low = text.lower()
                    for word in words:
                        assert word not in low, f"{path}.{lang}: {word!r}"


def test_generated_text_uses_no_certainty_words() -> None:
    for _name, reading in _all_readings():
        for s in reading.statements:
            for word in FORBIDDEN_EN:
                assert word not in s.text_en.lower()
            for word in FORBIDDEN_HI:
                assert word not in s.text_hi


def test_lucky_entries_complete_and_sourced() -> None:
    planets = load_data("lucky")["planets"]
    assert set(planets) == {g.value for g in Graha}
    for g, entry in planets.items():
        assert set(entry) == {"colour", "gemstone", "day", "number", "direction", "deity", "metal"}
        for kind, item in entry.items():
            assert item["source"], (g, kind)
        assert entry["number"]["source"] == "popular tradition"


# --- lagna-lord conditions, grammar, dedupe ---------------------------------------------------


def _lagna_lord_statement(signs: Mapping[Graha, int]) -> tuple[str, tuple[str, ...]]:
    p = life_areas(_synthetic({**_BASE_SIGNS, **signs}))["personality"]
    s = next(s for s in p.statements if s.why[0].startswith("Lagna lord"))
    return s.text_en, s.why


def _lagna_lord_text(key: str) -> str:
    return str(load_data("personality")["lagna_lord_in_house"][key]["en"])


# Mesha lagna; Mars is the lagna lord. Placements below keep every other graha out of contact
# with Mars unless named: Sun Simha, Moon Vrishabha (waning), Mercury/Venus/Jupiter Mesha.
_QUIET = {Graha.MERCURY: 0, Graha.VENUS: 0, Graha.JUPITER: 0}


def test_lagna_lord_6th_afflicted_only_with_malefic_and_no_benefic() -> None:
    text, why = _lagna_lord_statement({**_QUIET, Graha.MARS: 5, Graha.SATURN: 5})
    assert _lagna_lord_text("6_afflicted") in text
    assert "malefic contact: Saturn; no benefic contact" in why
    # Jupiter in Makara aspects Kanya (its 9th): benefic aspect -> neutral wording.
    text, why = _lagna_lord_statement({**_QUIET, Graha.MARS: 5, Graha.SATURN: 5, Graha.JUPITER: 9})
    assert _lagna_lord_text("6") in text
    assert "benefic contact: Jupiter" in " ".join(why)


def test_lagna_lord_12th_needs_benefic_support() -> None:
    text, _ = _lagna_lord_statement({**_QUIET, Graha.MARS: 11, Graha.SATURN: 9})
    assert _lagna_lord_text("12_unsupported") in text
    text, _ = _lagna_lord_statement({**_QUIET, Graha.MARS: 11, Graha.SATURN: 9, Graha.JUPITER: 11})
    assert _lagna_lord_text("12") in text


def test_lagna_lord_7th_wording_follows_strength() -> None:
    # Mars in Tula (7th, kendra +10), no shadbala: neutral dignity... strength decides the text.
    facts = _synthetic({**_BASE_SIGNS, **_QUIET, Graha.MARS: 6})
    s = next(
        s for s in life_areas(facts)["personality"].statements if s.why[0].startswith("Lagna lord")
    )
    score = int(s.why[1].split("strength ")[1].split("/")[0])
    key = "7_strong" if score >= 60 else "7_weak" if score < 40 else "7"
    assert _lagna_lord_text(key) in s.text_en


def test_health_not_duplicated_when_lagna_lord_is_moon() -> None:
    facts = _synthetic(_BASE_SIGNS, lagna_sign=3)  # Karka: lagna lord is the Moon
    health = life_areas(facts)["health"]
    moon = [s for s in health.statements if s.ref == "Phaladeepika Ch 2 v. 2"]
    assert len(moon) == 1
    assert "Moon is also the lagna lord" in moon[0].why


def test_no_a_before_vowel_element() -> None:
    for _name, reading in _all_readings():
        for s in reading.statements:
            assert " a earth" not in s.text_en and " a air" not in s.text_en, s.text_en


def test_chandra_manglik_text_omits_lagna() -> None:
    for level in ("none", "low", "medium"):
        text = load_data("areas")["marriage"]["manglik_moon"][level]["en"]
        assert "lagna" not in text.lower()
