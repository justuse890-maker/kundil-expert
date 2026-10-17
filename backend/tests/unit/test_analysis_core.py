"""Analysis core: functional roles (BPHS Ch 34), planet strength, dasha period judgement."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from pathlib import Path

import pytest

from vedic_engine import ephemeris
from vedic_engine.analysis import (
    FunctionalRole,
    Role,
    functional_roles,
    judge_period,
    moon_waxing,
    planet_strength,
)
from vedic_engine.analysis.functional import houses_ruled, load_data
from vedic_engine.analysis.strength import d9_dignity
from vedic_engine.constants import RASHIS, Graha
from vedic_engine.dignity import Dignity
from vedic_engine.kundli import Kundli, build_kundli
from vedic_engine.models import BirthInput

DELHI_1947 = BirthInput(datetime(1947, 8, 15, 0, 0), "Asia/Kolkata", 28.6139, 77.2090)


def _sign(name: str) -> int:
    return RASHIS.index(name)


@cache
def _india() -> Kundli:
    return build_kundli(DELHI_1947)


@pytest.fixture(autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


# --- synthetic chart facts -------------------------------------------------------------


@dataclass(frozen=True)
class _Pos:
    lon: float


@dataclass(frozen=True)
class _Bala:
    ratio: float


@dataclass(frozen=True)
class _Facts:
    """Just the fields the analysis functions read, set explicitly per test."""

    lagna_lon: float
    grahas: Mapping[Graha, _Pos]
    dignity: Mapping[Graha, Dignity]
    combust: Mapping[Graha, bool]
    shadbala: Mapping[Graha, _Bala]
    vargottama: Mapping[Graha, bool]
    vargas: Mapping[int, Mapping[str, int]] = field(default_factory=dict)


def _one_planet(
    g: Graha,
    lon: float,
    lagna_lon: float,
    dig: Dignity,
    *,
    combust: bool,
    ratio: float,
    vargottama: bool,
    d9_sign: int,
) -> _Facts:
    return _Facts(
        lagna_lon=lagna_lon,
        grahas={g: _Pos(lon), Graha.SUN: _Pos(0.0), Graha.MOON: _Pos(90.0)},
        dignity={g: dig},
        combust={g: combust},
        shadbala={g: _Bala(ratio)},
        vargottama={g: vargottama},
        vargas={9: {g.value: d9_sign}},
    )


# --- functional roles ------------------------------------------------------------------


def _role(lagna: str, g: Graha) -> FunctionalRole:
    return functional_roles(_sign(lagna))[g]


def test_karka_mars_is_yogakaraka() -> None:
    r = _role("karka", Graha.MARS)
    assert houses_ruled(Graha.MARS, _sign("karka")) == (5, 10)
    assert (r.role, r.roles, r.source) == (Role.YOGAKARAKA, (Role.YOGAKARAKA,), "bphs_lagna")
    assert r.ref == "BPHS Ch 34 vv. 27-28 (Santhanam p. 350)"


def test_vrishabha_saturn_is_yogakaraka() -> None:
    r = _role("vrishabha", Graha.SATURN)
    assert houses_ruled(Graha.SATURN, _sign("vrishabha")) == (9, 10)
    assert (r.role, r.source) == (Role.YOGAKARAKA, "bphs_lagna")  # vv. 23-24


def test_tula_saturn_is_yogakaraka_by_verse_13() -> None:
    # vv. 33-34 call Saturn auspicious; lord of 4 and 5, so v. 13 makes him a yogakaraka.
    r = _role("tula", Graha.SATURN)
    assert (r.role, r.source) == (Role.YOGAKARAKA, "bphs_v13")


def test_vrishchika_sun_is_a_yoga_giver() -> None:
    # vv. 35-36: "The Sun as well as the Moon are Yogakarakas" (Sun rules the 10th).
    r = _role("vrishchika", Graha.SUN)
    assert r.role is Role.YOGAKARAKA
    assert r.rule_role is Role.NEUTRAL  # the generic kendra rule would say neutral


def test_vrishchika_mars_is_neutral_per_verse() -> None:
    # BPHS Ch 34 vv. 35-36 (p. 353): "Mars is neutral" for Scorpio, though lagna lord.
    r = _role("vrishchika", Graha.MARS)
    assert (r.role, r.source) == (Role.NEUTRAL, "bphs_lagna")
    assert r.ref == "BPHS Ch 34 vv. 35-36 (Santhanam p. 353)"


def test_mithuna_jupiter_is_malefic_and_maraka() -> None:
    r = _role("mithuna", Graha.JUPITER)  # vv. 25-26; lord of 7 and 10
    assert r.roles == (Role.MALEFIC, Role.MARAKA)
    assert r.rule == "kendradhipati_dosha"  # still explains the lordship in `why`
    assert "kendradhipati dosha" in r.why


def test_vrishabha_sun_is_benefic() -> None:
    assert _role("vrishabha", Graha.SUN).role is Role.BENEFIC  # vv. 23-24


def test_mesha_mercury_is_malefic() -> None:
    r = _role("mesha", Graha.MERCURY)
    assert houses_ruled(Graha.MERCURY, _sign("mesha")) == (3, 6)
    assert r.roles == (Role.MALEFIC,)


def test_mesha_venus_is_maraka_in_addition_to_its_role() -> None:
    r = _role("mesha", Graha.VENUS)  # vv. 19-22: malefic and a direct killer
    assert houses_ruled(Graha.VENUS, _sign("mesha")) == (2, 7)
    assert r.roles == (Role.MALEFIC, Role.MARAKA)
    assert r.maraka_ref == "BPHS Ch 34 vv. 19-22 (Santhanam p. 347-348)"


def test_mesha_lagna_lord_mars_is_benefic_despite_8th() -> None:
    r = _role("mesha", Graha.MARS)
    assert houses_ruled(Graha.MARS, _sign("mesha")) == (1, 8)
    assert r.roles == (Role.BENEFIC,)
    assert r.note is not None and "8th" in r.note


def test_table_wins_for_lagna_lords() -> None:
    assert _role("tula", Graha.VENUS).role is Role.NEUTRAL  # vv. 33-34
    assert _role("vrishabha", Graha.VENUS).roles == (Role.MALEFIC, Role.MARAKA)  # vv. 23-24


def test_unclassified_planets_fall_back_to_rules() -> None:
    sat = _role("mithuna", Graha.SATURN)  # "no hint on Saturn": lord of 8 and 9
    assert (sat.role, sat.source, sat.rule) == (Role.BENEFIC, "rule", "trikona_lord")
    moon = _role("dhanu", Graha.MOON)  # not classified; luminary's 8th lordship is not evil
    assert (moon.role, moon.source, moon.rule) == (Role.NEUTRAL, "rule", "eighth_lord_luminary")


def test_moon_paksha_changes_only_the_kendra_rule_cited() -> None:
    waxing = functional_roles(_sign("mesha"), moon_is_waxing=True)[Graha.MOON]
    waning = functional_roles(_sign("mesha"), moon_is_waxing=False)[Graha.MOON]
    assert waxing.role is waning.role is Role.NEUTRAL  # lord of 4, not discussed by the verse
    assert (waxing.rule, waning.rule) == ("kendradhipati_dosha", "malefic_kendra")


def test_nodes_are_neutral_with_a_note() -> None:
    roles = functional_roles(_sign("karka"))
    for node in (Graha.RAHU, Graha.KETU):
        assert roles[node].role is Role.NEUTRAL
        assert roles[node].node_note


def test_every_lagna_gives_every_graha_a_cited_role() -> None:
    for lagna in range(12):
        roles = functional_roles(lagna)
        assert set(roles) == set(Graha)
        for r in roles.values():
            assert r.ref and r.why and r.text
            assert r.roles[0] is r.role
            assert (Role.MARAKA in r.roles) == (r.maraka_ref is not None)


def test_where_the_bphs_table_differs_from_the_generic_rules() -> None:
    """Every (lagna, graha, rule role, table role); update deliberately, never to make it pass."""
    diffs = [
        (RASHIS[lagna], g.value, r.rule_role.value, r.role.value)
        for lagna in range(12)
        for g, r in functional_roles(lagna).items()
        if r.role is not r.rule_role
    ]
    assert diffs == [
        ("mesha", "venus", "neutral", "malefic"),
        ("vrishabha", "sun", "neutral", "benefic"),
        ("vrishabha", "venus", "benefic", "malefic"),
        ("mithuna", "jupiter", "neutral", "malefic"),
        ("kanya", "jupiter", "neutral", "malefic"),
        ("tula", "moon", "neutral", "yogakaraka"),
        ("tula", "mars", "neutral", "malefic"),
        ("tula", "mercury", "benefic", "yogakaraka"),
        ("tula", "venus", "benefic", "neutral"),
        ("vrishchika", "sun", "neutral", "yogakaraka"),
        ("vrishchika", "moon", "benefic", "yogakaraka"),
        ("vrishchika", "mars", "benefic", "neutral"),
        ("vrishchika", "venus", "neutral", "malefic"),
        ("dhanu", "sun", "benefic", "yogakaraka"),
        ("dhanu", "mercury", "neutral", "yogakaraka"),
        ("dhanu", "jupiter", "benefic", "neutral"),
        ("makara", "moon", "neutral", "malefic"),
        ("kumbha", "mercury", "benefic", "neutral"),
        ("meena", "mars", "benefic", "yogakaraka"),
        ("meena", "mercury", "neutral", "malefic"),
        ("meena", "jupiter", "benefic", "yogakaraka"),
    ]


def test_load_data_is_read_only() -> None:
    data = load_data("functional_bphs")
    with pytest.raises(TypeError):
        data["lagnas"]["mesha"]["benefic"] = ()  # type: ignore[index]
    assert isinstance(data["lagnas"]["mesha"]["benefic"], tuple)


# --- strength --------------------------------------------------------------------------


def test_exalted_vargottama_kendra_planet_scores_above_80() -> None:
    # Jupiter at 1 Karka (exalted, D9 Karka, vargottama) in a Karka lagna (house 1).
    f = _one_planet(
        Graha.JUPITER, 91.0, 95.0, Dignity.EXALTED,
        combust=False, ratio=1.2, vargottama=True, d9_sign=_sign("karka"),
    )  # fmt: skip
    s = planet_strength(f, Graha.JUPITER)
    assert s.score > 80
    names = {x.name for x in s.factors}
    assert {"dignity", "shadbala", "house", "vargottama", "d9_dignity"} <= names
    assert all(x.ref and x.why for x in s.factors)


def test_debilitated_combust_8th_house_planet_scores_below_20() -> None:
    # Saturn at 10 Mesha (debilitated), Kanya lagna: Mesha is the 8th house.
    f = _one_planet(
        Graha.SATURN, 10.0, 160.0, Dignity.DEBILITATED,
        combust=True, ratio=0.7, vargottama=False, d9_sign=_sign("mithuna"),
    )  # fmt: skip
    s = planet_strength(f, Graha.SATURN)
    assert s.score < 20
    deltas = {x.name: x.delta for x in s.factors}
    assert deltas == {"dignity": -20, "shadbala": -10, "combust": -15, "house": -10}


def test_strength_is_clamped_to_0_100() -> None:
    weak = _one_planet(
        Graha.SATURN, 10.0, 160.0, Dignity.DEBILITATED,
        combust=True, ratio=0.7, vargottama=False, d9_sign=_sign("mesha"),
    )  # fmt: skip
    assert planet_strength(weak, Graha.SATURN).score == 0  # 50-20-10-15-10-10 = -15


def test_d9_dignity_by_sign() -> None:
    assert d9_dignity(Graha.SATURN, _sign("tula")) is Dignity.EXALTED
    assert d9_dignity(Graha.SATURN, _sign("kumbha")) is Dignity.OWN
    assert d9_dignity(Graha.SATURN, _sign("mesha")) is Dignity.DEBILITATED
    assert d9_dignity(Graha.SATURN, _sign("karka")) is None
    assert d9_dignity(Graha.MOON, _sign("vrishabha")) is Dignity.EXALTED
    assert d9_dignity(Graha.RAHU, _sign("vrishabha")) is Dignity.EXALTED  # NODE_DIGNITY_SCHOOL


def test_india_1947_strength_of_saturn() -> None:
    s = planet_strength(_india(), Graha.SATURN)
    # great enemy in Karka -10, Shadbala ratio 1.09 +15, combust -15, D9 Makara (own) +10
    assert {x.name: x.delta for x in s.factors} == {
        "dignity": -10, "shadbala": 15, "combust": -15, "d9_dignity": 10,
    }  # fmt: skip
    assert s.score == 50


def test_strength_of_every_graha_is_in_range_with_refs() -> None:
    k = _india()
    for g in Graha:
        s = planet_strength(k, g)
        assert 0 <= s.score <= 100
        assert all(x.ref and x.delta != 0 for x in s.factors)


# --- dasha judgement -------------------------------------------------------------------


def test_moon_waxing_from_elongation() -> None:
    assert moon_waxing(_india()) is False  # Moon 24 deg behind the Sun: krishna paksha


def test_india_1947_saturn_maha() -> None:
    k = _india()
    assert k.vimshottari[0].lord == Graha.SATURN.value
    j = judge_period(k, (Graha.SATURN,))
    codes = [r.code for r in j.reasons]
    assert "role:yogakaraka" in codes
    assert "strength:combust" in codes
    assert "occupies:3" in codes
    assert j.areas == (3, 9, 10)
    # yogakaraka +40, strength 50 -> (50 - 50) / 2 = 0
    assert j.score == 40
    assert j.nature == "favourable"
    assert all(r.ref for r in j.reasons)


def test_india_1947_saturn_mercury_antar() -> None:
    k = _india()
    j = judge_period(k, (Graha.SATURN, Graha.MERCURY))
    # Saturn alone 40. Mercury for Vrishabha: 'somewhat auspicious' (BPHS Ch 34 vv. 23-24) +25;
    # lord of the 2nd, so maraka by lordship (BPHS Ch 44) -10;
    # strength: great enemy -10, Shadbala 1.07 +15 -> 55 -> +2.5; total 17.5.
    # Mean (40 + 17.5) / 2 = 28.75; both in Karka (same sign = kendra) +10 -> 38.75 -> 39.
    assert functional_roles(_sign("vrishabha"))[Graha.MERCURY].roles == (Role.BENEFIC, Role.MARAKA)
    assert planet_strength(k, Graha.MERCURY).score == 55
    assert "mutual:kendra_trikona" in [r.code for r in j.reasons]
    assert j.score == 39
    assert j.areas == (2, 3, 5, 9, 10)
    assert all(r.ref for r in j.reasons)


def test_mutual_6_8_and_2_12_are_penalised() -> None:
    k = _india()
    # Mars in Mithuna, Sun in Karka: the Sun is 2nd from Mars (Mars 12th from the Sun) -> 2/12.
    j = judge_period(k, (Graha.MARS, Graha.SUN))
    assert "mutual:dvirdvadasha_shashtashtaka" in [r.code for r in j.reasons]
    mutual = [r for r in j.reasons if r.code.startswith("mutual:")]
    assert [r.delta for r in mutual] == [-15]


def test_nature_thresholds() -> None:
    k = _india()
    for lords in [(g,) for g in Graha] + [(Graha.SATURN, g) for g in Graha]:
        j = judge_period(k, lords)
        assert -100 <= j.score <= 100
        expected = "favourable" if j.score > 20 else "challenging" if j.score < -20 else "mixed"
        assert j.nature == expected
        assert all(r.ref and r.why and r.text for r in j.reasons)


def test_judge_period_requires_a_lord() -> None:
    with pytest.raises(ValueError):
        judge_period(_india(), ())
