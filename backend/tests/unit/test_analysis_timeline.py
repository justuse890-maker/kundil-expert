"""24-month timeline and today's guidance (analysis Task 5)."""

import re
from datetime import UTC, date, datetime, timedelta
from functools import cache
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from vedic_engine import ephemeris
from vedic_engine.analysis import (
    DailyGuidance,
    current_periods,
    daily,
    functional_roles,
    judge_period,
    timeline,
)
from vedic_engine.analysis.daily import CHALDEAN, DATA_FILES, vaar_lord
from vedic_engine.analysis.dasha_judgement import moon_waxing
from vedic_engine.analysis.functional import Role, load_data
from vedic_engine.analysis.timeline import Timeline, add_months
from vedic_engine.angles import sign_of
from vedic_engine.constants import Graha
from vedic_engine.kundli import Kundli, build_kundli
from vedic_engine.models import BirthInput

DELHI = (28.6139, 77.2090)
NOW = datetime(2026, 10, 17, 6, 30, tzinfo=UTC)
DAY = date(2026, 10, 17)
TZ = "Asia/Kolkata"
TOL = timedelta(microseconds=1)  # float day arithmetic in the dasha tree


@cache
def _india(time_known: bool = True) -> Kundli:
    return build_kundli(BirthInput(datetime(1947, 8, 15, 0, 0), TZ, *DELHI, time_known=time_known))


@cache
def _tl() -> Timeline:
    return timeline(_india(), NOW)


@cache
def _daily(day: date = DAY, time_known: bool = True) -> DailyGuidance:
    return daily(_india(time_known), day, TZ, *DELHI)


@pytest.fixture(autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


# --- hora schedule ----------------------------------------------------------------------


def test_chaldean_order() -> None:
    assert [g.value for g in CHALDEAN] == [
        "saturn", "jupiter", "mars", "sun", "venus", "mercury", "moon",
    ]  # fmt: skip


def test_sunday_horas_start_with_the_sun() -> None:
    sunday = date(2026, 10, 18)
    assert sunday.weekday() == 6
    g = _daily(sunday)
    assert g.vaar == "ravi" and g.vaar_lord == Graha.SUN
    assert [h.lord.value for h in g.horas[:8]] == [
        "sun", "venus", "mercury", "moon", "saturn", "jupiter", "mars", "sun",
    ]  # fmt: skip


def test_first_hora_is_the_weekday_lord_every_day() -> None:
    for i in range(7):
        g = _daily(DAY + timedelta(days=i))
        assert g.horas[0].lord == g.vaar_lord == vaar_lord(g.vaar)


def test_24_horas_cover_sunrise_to_next_sunrise_without_gaps() -> None:
    g = _daily()
    assert len(g.horas) == 24
    assert g.horas[0].start_utc == g.sunrise_utc
    assert g.horas[11].end_utc == g.sunset_utc == g.horas[12].start_utc
    assert g.horas[-1].end_utc == g.next_sunrise_utc
    for a, b in pairwise(g.horas):
        assert a.end_utc == b.start_utc
    day_len = (g.sunset_utc - g.sunrise_utc) / 12
    night_len = (g.next_sunrise_utc - g.sunset_utc) / 12
    for h in g.horas[:12]:
        assert abs((h.end_utc - h.start_utc) - day_len) < timedelta(milliseconds=1)
    for h in g.horas[12:]:
        assert abs((h.end_utc - h.start_utc) - night_len) < timedelta(milliseconds=1)


def test_sunrise_matches_the_engine_panchang() -> None:
    from vedic_engine.models import Settings
    from vedic_engine.panchang import day_panchang

    g = _daily()
    p = day_panchang(DAY, TZ, *DELHI, 0.0, Settings())
    nxt = day_panchang(DAY + timedelta(days=1), TZ, *DELHI, 0.0, Settings())
    assert g.sunrise_utc == p.sunrise_utc and g.sunset_utc == p.sunset_utc
    assert g.next_sunrise_utc == nxt.sunrise_utc
    assert g.vaar == p.at_sunrise.vaar == "shani"  # 2026-10-17 is a Saturday


def test_horas_flagged_by_functional_role() -> None:
    k = _india()
    roles = functional_roles(sign_of(k.lagna_lon), moon_waxing(k))
    for h in _daily().horas:
        role = roles[h.lord].role
        assert h.favourable == (role in (Role.BENEFIC, Role.YOGAKARAKA))
        assert h.avoid == (role == Role.MALEFIC)
        assert h.why and h.ref and h.colour.en and h.colour.hi and h.colour.source
    g = _daily()
    assert g.favourable_horas == tuple(i for i, h in enumerate(g.horas) if h.favourable)
    assert g.avoid_horas == tuple(i for i, h in enumerate(g.horas) if h.avoid)


def test_hora_colours_and_sources() -> None:
    colours = load_data("hora")["colours"]
    assert colours["sun"]["en"].startswith("red")
    assert colours["saturn"]["en"].startswith("black")
    assert "BPHS Ch 3 vv. 16-17" in colours["mercury"]["source"]
    for g in CHALDEAN:
        c = colours[g.value]
        assert c["en"] and re.search(r"[ऀ-ॿ]", c["hi"]) and c["source"]
        assert "traditional association" in c["source"]  # the extra shades are not classical


def test_colour_today_and_avoid_follow_roles() -> None:
    k = _india()
    roles = functional_roles(sign_of(k.lagna_lon), moon_waxing(k))
    g = _daily()
    assert roles[g.colour_today.graha].role in (Role.BENEFIC, Role.YOGAKARAKA)
    assert g.colour_avoid is not None
    assert roles[g.colour_avoid.graha].role == Role.MALEFIC
    # Saturday: Saturn is the Vrishabha yogakaraka, so the day's own colour is favourable
    assert g.colour_today.graha == Graha.SATURN
    for c in (g.colour_today, g.colour_avoid):
        assert c.why and c.ref and c.en and c.hi


def test_body_language_and_decisions_are_cited() -> None:
    g = _daily()
    assert len(g.body_language) >= 2
    assert any("earth" in s.why[0] for s in g.body_language)  # Vrishabha lagna
    assert any("mars" in " ".join(s.why) for s in g.body_language)  # Mars maha
    assert g.decisions
    for s in (*g.body_language, *g.decisions):
        assert s.text_en and s.text_hi and s.why and s.ref
        assert re.search(r"[ऀ-ॿ]", s.text_hi)


def test_time_unknown_daily_still_gives_horas() -> None:
    g = _daily(DAY, False)
    assert len(g.horas) == 24 and g.horas[0].lord == Graha.SATURN
    assert g.sunrise_utc == _daily().sunrise_utc


# --- current periods and timeline ---------------------------------------------------------


def test_india_current_maha_mars_antar_rahu() -> None:
    maha, antar, pratyantar = current_periods(_india(), NOW)
    assert (maha.lord, antar.lord) == ("mars", "rahu")
    engine = next(p for p in _india().vimshottari if p.start_utc <= NOW < p.end_utc)
    assert engine.lord == "mars"
    assert next(c for c in engine.children if c.start_utc <= NOW < c.end_utc).lord == "rahu"
    assert pratyantar.start_utc <= NOW < pratyantar.end_utc


def test_timeline_covers_the_window_contiguously() -> None:
    tl = _tl()
    end = add_months(NOW, 24)
    for level in ("antar", "pratyantar"):
        items = [i for i in tl.items if i.level == level]
        assert items[0].start_utc <= NOW < items[0].end_utc
        assert items[-1].start_utc < end <= items[-1].end_utc
        for a, b in pairwise(items):
            assert abs(a.end_utc - b.start_utc) <= TOL
            assert a.start_utc < b.start_utc
    assert [i.level for i in tl.items] == sorted((i.level for i in tl.items),
                                                 key=("antar", "pratyantar").index)  # fmt: skip


def test_timeline_items_are_judged_and_cited() -> None:
    k = _india()
    for item in _tl().items:
        assert item.why and item.ref and item.advice_key
        assert item.advice_key in {f"advice.{n}" for n in ("favourable", "mixed", "challenging")}
        lords = tuple(Graha(x) for x in item.lords)
        assert item.judgement == judge_period(k, lords)
        assert len(lords) == (2 if item.level == "antar" else 3)
        assert set(item.areas) <= set(load_data("decisions")["area_houses"])


def test_months_and_windows() -> None:
    tl = _tl()
    assert len(tl.months) == 24
    assert tl.months[0].start_utc == NOW
    for a, b in pairwise(tl.months):
        assert a.end_utc == b.start_utc
    assert tl.months[-1].end_utc == add_months(NOW, 24)
    assert len(tl.best_windows) == 3 and len(tl.challenging_windows) == 3
    best = sorted(tl.months, key=lambda m: (-m.score, m.start_utc))[:3]
    worst = sorted(tl.months, key=lambda m: (m.score, m.start_utc))[:3]
    assert tl.best_windows == tuple(best) and tl.challenging_windows == tuple(worst)
    for m in tl.months:
        assert m.reasons and all(r.why and r.ref for r in m.reasons)


def test_best_windows_are_deterministic() -> None:
    again = timeline(_india(), NOW)
    assert again.best_windows == _tl().best_windows
    assert again.challenging_windows == _tl().challenging_windows


def test_transit_overlays_follow_gochara() -> None:
    k = _india()
    moon_sign = sign_of(k.grahas[Graha.MOON].lon)
    seen = set()
    for t in _tl().transits:
        assert t.ref.startswith("Phaladeepika Ch 26")
        assert t.house == (t.sign - moon_sign) % 12 + 1
        if t.graha == Graha.JUPITER:
            assert (t.delta > 0) == (t.house in (2, 5, 7, 9, 11))
        else:
            assert (t.delta > 0) == (t.house in (3, 6, 11))
            if t.house in (12, 1, 2, 4, 8):
                assert t.code.startswith(("sade_sati", "dhaiya"))
        seen.add(t.graha)
    assert seen == {Graha.JUPITER, Graha.SATURN}
    for a, b in pairwise([t for t in _tl().transits if t.graha == Graha.SATURN]):
        assert a.end_utc == b.start_utc


def test_add_months_clamps_the_day() -> None:
    assert add_months(datetime(2027, 1, 31, tzinfo=UTC), 1) == datetime(2027, 2, 28, tzinfo=UTC)
    assert add_months(NOW, 24) == datetime(2028, 10, 17, 6, 30, tzinfo=UTC)


# --- honesty ------------------------------------------------------------------------------

_CERTAIN = re.compile(
    r"definitely|guarantee|100%|99%|certainly|surely|undoubtedly|without doubt|for sure|"
    r"\balways\b|\bnever\b|निश्चित|गारंटी|अवश्य|ज़रूर|जरूर|पक्का|हमेशा|कभी नहीं",
    re.IGNORECASE,
)


def _strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for k, v in node.items() if not k.startswith("_") for s in _strings(v)]
    if isinstance(node, (list, tuple)):
        return [s for v in node for s in _strings(v)]
    return []


@pytest.mark.parametrize("name", DATA_FILES)
def test_data_files_have_no_certainty_words_and_hindi_pairs(name: str) -> None:
    data = load_data(name)
    for s in _strings(data):
        assert not _CERTAIN.search(s), s

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "en" in node or "hi" in node:
                assert node.get("en") and node.get("hi"), node
                assert re.search(r"[ऀ-ॿ]", node["hi"]), node
                assert set(re.findall(r"{\w+}", node["en"])) == set(
                    re.findall(r"{\w+}", node["hi"])
                ), node
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)

    walk(dict(data))


def test_generated_text_has_no_certainty_words() -> None:
    g = _daily()
    texts = [s.text_en for s in (*g.body_language, *g.decisions)]
    texts += [s.text_hi for s in (*g.body_language, *g.decisions)]
    texts += [r.text_en for m in _tl().months for r in m.reasons]
    texts += [r.text_hi for m in _tl().months for r in m.reasons]
    for t in texts:
        assert not _CERTAIN.search(t), t
        assert "{" not in t, t
