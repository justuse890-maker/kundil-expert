"""House facts: bhava table, graha drishti, bhava karakas, vargottama (Task 15)."""

import json
from importlib import resources

import pytest
from hypothesis import given
from hypothesis import strategies as st

from chart_fixtures import load_chart
from vedic_engine import bhava
from vedic_engine.angles import sign_of
from vedic_engine.bhava import BhavaFact, bhava_facts, drishti, vargottama
from vedic_engine.constants import RASHI_LORD, RASHIS, SEVEN, Graha
from vedic_engine.lagna import house_of
from vedic_engine.varga import varga_sign

MESHA, VRISHABHA, MITHUNA, KARKA, SIMHA, KANYA, TULA, VRISHCHIKA, DHANU, MAKARA, KUMBHA, MEENA = (
    RASHIS.index(r)
    for r in (
        "mesha", "vrishabha", "mithuna", "karka", "simha", "kanya",
        "tula", "vrishchika", "dhanu", "makara", "kumbha", "meena",
    )
)  # fmt: skip

LON = st.floats(min_value=0.0, max_value=360.0, exclude_max=True, allow_nan=False)


# ---- graha drishti -------------------------------------------------------------------------


def test_mars_in_mesha() -> None:
    assert drishti(Graha.MARS, MESHA) == (KARKA, TULA, VRISHCHIKA)


def test_jupiter_in_mesha() -> None:
    assert drishti(Graha.JUPITER, MESHA) == (SIMHA, TULA, DHANU)


def test_saturn_in_mesha() -> None:
    assert drishti(Graha.SATURN, MESHA) == (MITHUNA, TULA, MAKARA)


def test_sun_in_mesha_aspects_only_tula() -> None:
    assert drishti(Graha.SUN, MESHA) == (TULA,)
    for g in (Graha.MOON, Graha.MERCURY, Graha.VENUS):
        assert drishti(g, MESHA) == (TULA,)


def test_drishti_wraps_around_the_zodiac() -> None:
    # Mars in Vrishchika (7): 4th = Kumbha, 7th = Vrishabha, 8th = Mithuna.
    assert drishti(Graha.MARS, VRISHCHIKA) == (KUMBHA, VRISHABHA, MITHUNA)
    # Jupiter in Meena (11): 5th = Karka, 7th = Kanya, 9th = Vrishchika.
    assert drishti(Graha.JUPITER, MEENA) == (KARKA, KANYA, VRISHCHIKA)
    # Saturn in Makara (9): 3rd = Meena, 7th = Karka, 10th = Tula.
    assert drishti(Graha.SATURN, MAKARA) == (MEENA, KARKA, TULA)


def test_nodes_aspect_nothing_by_default() -> None:
    assert bhava.NODE_ASPECTS_SCHOOL == "none"
    assert drishti(Graha.RAHU, MESHA) == ()
    assert drishti(Graha.KETU, KARKA) == ()


def test_node_5_7_9_school_is_behind_the_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bhava, "NODE_ASPECTS_SCHOOL", "5-7-9")
    assert drishti(Graha.RAHU, MESHA) == (SIMHA, TULA, DHANU)
    assert drishti(Graha.KETU, MEENA) == (KARKA, KANYA, VRISHCHIKA)
    # The seven classical grahas are unaffected by the node school.
    assert drishti(Graha.MARS, MESHA) == (KARKA, TULA, VRISHCHIKA)


def test_unknown_node_school_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bhava, "NODE_ASPECTS_SCHOOL", "bogus")
    with pytest.raises(ValueError, match="NODE_ASPECTS_SCHOOL"):
        drishti(Graha.RAHU, MESHA)


@pytest.mark.parametrize("graha", list(Graha))
def test_drishti_invariants_for_every_sign(graha: Graha) -> None:
    for sign in range(12):
        signs = drishti(graha, sign)
        assert len(set(signs)) == len(signs)
        assert all(0 <= s <= 11 and s != sign for s in signs)
        if graha not in (Graha.RAHU, Graha.KETU):
            assert (sign + 6) % 12 in signs  # every graha aspects the 7th


# ---- India 1947 (golden chart) -------------------------------------------------------------


def _india_1947() -> tuple[float, dict[Graha, float]]:
    """Sidereal longitudes from the golden fixture; the nodes are placed by sign only.

    The fixture has no nodes. Mean Rahu is in Vrishabha (house 1) and Ketu in Vrishchika
    (house 7) for this birth (test_kundli.py checks the engine's own nodes); only the sign
    matters for house facts, so they sit at 15 deg of those signs.
    """
    sidereal = load_chart("new_delhi_1947")["sidereal"]
    lons = {Graha(k): v for k, v in sidereal.items() if k != "lagna"}
    lons[Graha.RAHU] = VRISHABHA * 30.0 + 15.0
    lons[Graha.KETU] = VRISHCHIKA * 30.0 + 15.0
    return sidereal["lagna"], lons


def test_india_1947_placements_match_the_brief() -> None:
    lagna, lons = _india_1947()
    assert sign_of(lagna) == VRISHABHA
    for g in (Graha.SUN, Graha.MOON, Graha.MERCURY, Graha.VENUS, Graha.SATURN):
        assert sign_of(lons[g]) == KARKA
    assert sign_of(lons[Graha.MARS]) == MITHUNA
    assert sign_of(lons[Graha.JUPITER]) == TULA


def test_india_1947_house_facts() -> None:
    lagna, lons = _india_1947()
    facts = bhava_facts(lagna, lons)
    assert len(facts) == 12
    assert [f.house for f in facts] == list(range(1, 13))
    assert [f.rashi for f in facts] == [(VRISHABHA + i) % 12 for i in range(12)]

    h1 = facts[0]
    assert isinstance(h1, BhavaFact)
    assert h1.rashi == VRISHABHA
    assert h1.lord is Graha.VENUS
    assert h1.lord_house == 3
    assert h1.occupants == (Graha.RAHU,)

    assert facts[2].occupants == (Graha.SUN, Graha.MOON, Graha.MERCURY, Graha.VENUS, Graha.SATURN)
    assert facts[1].occupants == (Graha.MARS,)
    assert facts[5].occupants == (Graha.JUPITER,)
    assert facts[6].occupants == (Graha.KETU,)
    assert all(facts[h - 1].occupants == () for h in (4, 5, 8, 9, 10, 11, 12))


def test_india_1947_lords_and_lord_houses() -> None:
    lagna, lons = _india_1947()
    facts = bhava_facts(lagna, lons)
    assert [f.lord for f in facts] == [
        Graha.VENUS, Graha.MERCURY, Graha.MOON, Graha.SUN, Graha.MERCURY, Graha.VENUS,
        Graha.MARS, Graha.JUPITER, Graha.SATURN, Graha.SATURN, Graha.JUPITER, Graha.MARS,
    ]  # fmt: skip
    assert [f.lord_house for f in facts] == [3, 3, 3, 3, 3, 3, 2, 6, 3, 3, 6, 2]
    assert all(f.lord is RASHI_LORD[f.rashi] for f in facts)


def test_india_1947_aspects_by_hand() -> None:
    """Whole-sign aspects worked out by hand from the placements in the brief."""
    lagna, lons = _india_1947()
    by_house = {f.house: f.aspected_by for f in bhava_facts(lagna, lons)}
    # Mars (Mithuna) aspects Kanya, Dhanu, Makara; Jupiter (Tula) Kumbha, Mesha, Mithuna;
    # Saturn (Karka) Kanya, Makara, Mesha; the four other planets in Karka aspect Makara.
    # Houses run Vrishabha (1), Mithuna, Karka, Simha, Kanya (5), Tula, Vrishchika, Dhanu (8),
    # Makara (9), Kumbha, Meena, Mesha (12).
    assert by_house == {
        1: (),
        2: (Graha.JUPITER,),
        3: (),
        4: (),
        5: (Graha.MARS, Graha.SATURN),
        6: (),
        7: (),
        8: (Graha.MARS,),
        9: (Graha.SUN, Graha.MOON, Graha.MARS, Graha.MERCURY, Graha.VENUS, Graha.SATURN),
        10: (Graha.JUPITER,),
        11: (),
        12: (Graha.JUPITER, Graha.SATURN),
    }


def test_india_1947_node_school_changes_aspects_only(monkeypatch: pytest.MonkeyPatch) -> None:
    lagna, lons = _india_1947()
    default = bhava_facts(lagna, lons)
    monkeypatch.setattr(bhava, "NODE_ASPECTS_SCHOOL", "5-7-9")
    nodes = bhava_facts(lagna, lons)
    assert [f.occupants for f in nodes] == [f.occupants for f in default]
    # Rahu (Vrishabha) aspects Kanya, Vrishchika, Makara; Ketu (Vrishchika) Meena, Vrishabha,
    # Karka. Houses: Vrishabha 1, Karka 3, Kanya 5, Vrishchika 7, Makara 9, Meena 11.
    by_house = {f.house: f.aspected_by for f in nodes}
    assert by_house[1] == (Graha.KETU,)
    assert by_house[3] == (Graha.KETU,)
    assert by_house[5] == (Graha.MARS, Graha.SATURN, Graha.RAHU)
    assert by_house[7] == (Graha.RAHU,)
    assert by_house[9] == (
        Graha.SUN, Graha.MOON, Graha.MARS, Graha.MERCURY, Graha.VENUS, Graha.SATURN, Graha.RAHU,
    )  # fmt: skip
    assert by_house[11] == (Graha.KETU,)
    for house in (2, 4, 6, 8, 10, 12):
        assert by_house[house] == {f.house: f.aspected_by for f in default}[house]


def test_karakas_attached_to_each_house() -> None:
    lagna, lons = _india_1947()
    facts = bhava_facts(lagna, lons)
    assert [f.karakas for f in facts] == [
        (Graha.SUN,), (Graha.JUPITER,), (Graha.MARS,), (Graha.MOON,), (Graha.JUPITER,),
        (Graha.MARS,), (Graha.VENUS,), (Graha.SATURN,), (Graha.JUPITER,), (Graha.MERCURY,),
        (Graha.JUPITER,), (Graha.SATURN,),
    ]  # fmt: skip


# ---- structural properties -----------------------------------------------------------------


@given(
    lagna=LON,
    lons=st.fixed_dictionaries({g: LON for g in Graha}),
)
def test_house_facts_are_consistent(lagna: float, lons: dict[Graha, float]) -> None:
    facts = bhava_facts(lagna, lons)
    assert [f.house for f in facts] == list(range(1, 13))
    lagna_sign = sign_of(lagna)
    for f in facts:
        assert f.rashi == (lagna_sign + f.house - 1) % 12
        assert f.lord is RASHI_LORD[f.rashi]
        assert f.lord_house == house_of(sign_of(lons[f.lord]), lagna_sign)
        assert list(f.occupants) == [
            g for g in Graha if house_of(sign_of(lons[g]), lagna_sign) == f.house
        ]
        assert list(f.aspected_by) == [g for g in Graha if f.rashi in drishti(g, sign_of(lons[g]))]
        assert f.karakas
    # every graha occupies exactly one house
    assert sorted(g for f in facts for g in f.occupants) == sorted(Graha)


# ---- vargottama ----------------------------------------------------------------------------


def test_vargottama_known_cases() -> None:
    # First navamsa of a movable sign, 5th of a fixed sign, 9th of a dual sign.
    assert vargottama({Graha.SUN: 0.5})[Graha.SUN] is True  # Mesha 0.5 deg
    assert vargottama({Graha.MOON: 30.0 + 15.0})[Graha.MOON] is True  # Vrishabha 15 deg
    assert vargottama({Graha.MARS: 8 * 30.0 + 28.0})[Graha.MARS] is True  # Dhanu 28 deg
    assert vargottama({Graha.SUN: 5.0})[Graha.SUN] is False  # Mesha 5 deg is in Vrishabha navamsa


def test_vargottama_covers_the_graha_keys_given() -> None:
    lons = {Graha.SUN: 1.0, Graha.RAHU: 200.0}
    assert set(vargottama(lons)) == {Graha.SUN, Graha.RAHU}


@given(lons=st.fixed_dictionaries({g: LON for g in Graha}))
def test_vargottama_is_d1_sign_equals_d9_sign(lons: dict[Graha, float]) -> None:
    result = vargottama(lons)
    assert set(result) == set(Graha)
    for g, lon in lons.items():
        assert result[g] == (varga_sign(lon, 1) == varga_sign(lon, 9))


# ---- karakas table (BPHS Ch. 32 vv. 31-34) -------------------------------------------------

# Brihat Parasara Hora Sastra, tr. R. Santhanam, Vol. 1 (Ranjan, 1992), Ch. 32 verse 34, English
# and Santhanam's table, printed p. 325 (archive.org leaf n329): 1 Sun, 2 Jupiter, 3 Mars,
# 4 Moon, 5 Jupiter, 6 Mars, 7 Venus, 8 Saturn, 9 Jupiter, 10 Mercury, 11 Jupiter, 12 Saturn.
BPHS_KARAKAS = {
    "1": ["sun"], "2": ["jupiter"], "3": ["mars"], "4": ["moon"], "5": ["jupiter"],
    "6": ["mars"], "7": ["venus"], "8": ["saturn"], "9": ["jupiter"], "10": ["mercury"],
    "11": ["jupiter"], "12": ["saturn"],
}  # fmt: skip


def _karakas_json() -> dict[str, object]:
    text = resources.files("vedic_engine").joinpath("data/karakas.json").read_text("utf-8")
    data: dict[str, object] = json.loads(text)
    return data


def test_karakas_table_matches_bphs_literally() -> None:
    assert _karakas_json()["houses"] == BPHS_KARAKAS


def test_every_house_has_a_karaka_and_all_are_graha_keys() -> None:
    houses = _karakas_json()["houses"]
    assert isinstance(houses, dict)
    assert set(houses) == {str(h) for h in range(1, 13)}
    for karakas in houses.values():
        assert len(karakas) >= 1
        assert all(Graha(k) in SEVEN for k in karakas)


def test_karakas_json_cites_its_source_and_records_variants() -> None:
    data = _karakas_json()
    source = str(data["_source"])
    assert "Santhanam" in source and "Ch. 32" in source and "325" in source
    note = str(data["_note"])
    # The Phaladeepika (Ch. XV, sloka 17) variants, incl. the 10th house, are recorded.
    assert "Phaladeepika" in note and "sloka 17" in note
    assert "10th Jupiter, Sun, Mercury, Saturn" in note
