import itertools
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vedic_engine import ephemeris
from vedic_engine.constants import SEVEN, Graha
from vedic_engine.doshas import kaal_sarpa, manglik, sade_sati
from vedic_engine.models import EngineWarning, Settings
from vedic_engine.timeutil import jd_from_utc, utc_from_jd

S = Settings()


@pytest.fixture(autouse=True)
def _init(ephe_path: Path) -> None:
    ephemeris.init(ephe_path)


def _lon(sign: int) -> float:
    return sign * 30.0 + 10.0


def test_manglik_7th_from_lagna_and_venus_is_medium() -> None:
    # lagna Mesha, Mars Tula (7th from lagna and from Mesha-placed Venus)
    r = manglik(_lon(6), _lon(0), _lon(2), _lon(0))
    assert (r.from_lagna, r.from_moon, r.from_venus, r.level) == (True, False, True, "medium")


def test_manglik_7th_from_lagna_only_is_low() -> None:
    r = manglik(_lon(6), _lon(0), _lon(2), _lon(1))  # Moon Mithuna: Mars 5th; Venus: Mars 6th
    assert (r.from_lagna, r.from_moon, r.from_venus, r.level) == (True, False, False, "low")


def test_manglik_first_house_from_all_is_high() -> None:
    r = manglik(_lon(4), _lon(4), _lon(4), _lon(4))
    assert r.level == "high" and r.from_lagna and r.from_moon and r.from_venus


def test_manglik_third_house_is_none() -> None:
    r = manglik(_lon(2), _lon(0), _lon(0), _lon(0))
    assert r.level == "none" and not (r.from_lagna or r.from_moon or r.from_venus)


def _kp(offsets: dict[Graha, float], rahu: float = 100.0) -> dict[Graha, float]:
    pos = {g: (rahu + offsets[g]) % 360.0 for g in SEVEN}
    pos[Graha.RAHU] = rahu
    return pos


_INSIDE = dict(zip(SEVEN, (10.0, 40.0, 70.0, 100.0, 130.0, 160.0, 175.0), strict=True))


def test_kaal_sarpa_full_inside() -> None:
    r = kaal_sarpa(_kp(_INSIDE), lagna_lon=_lon(3))
    assert r is not None and r.kind == "full" and r.outside == ()
    assert r.name == "anant"  # Rahu at 100 = Karka = lagna sign -> 1st house


def test_kaal_sarpa_full_other_side() -> None:
    other = {g: o + 180.0 for g, o in _INSIDE.items()}
    r = kaal_sarpa(_kp(other), lagna_lon=_lon(0))
    assert r is not None and r.kind == "full"
    assert r.name == "shankhpal"  # Rahu in Karka is the 4th house from a Mesha lagna


def test_kaal_sarpa_partial_and_none() -> None:
    one = {**_INSIDE, Graha.SATURN: 200.0}
    r = kaal_sarpa(_kp(one), lagna_lon=_lon(3))
    assert r is not None and r.kind == "partial" and r.outside == (Graha.SATURN,)
    two = {**one, Graha.MARS: 250.0}
    assert kaal_sarpa(_kp(two), lagna_lon=_lon(3)) is None


def test_kaal_sarpa_planet_on_axis_counts_outside() -> None:
    on_ketu = {**_INSIDE, Graha.SATURN: 180.0}
    r = kaal_sarpa(_kp(on_ketu), lagna_lon=_lon(3))
    assert r is not None and r.kind == "partial" and r.outside == (Graha.SATURN,)
    on_rahu = {**_INSIDE, Graha.SATURN: 0.0}
    r = kaal_sarpa(_kp(on_rahu), lagna_lon=_lon(3))
    assert r is not None and r.kind == "partial" and r.outside == (Graha.SATURN,)
    both = {**on_ketu, Graha.MARS: 0.0}
    assert kaal_sarpa(_kp(both), lagna_lon=_lon(3)) is None


def test_kaal_sarpa_partial_reverse_one_inside_six_beyond() -> None:
    beyond = {g: o + 180.0 for g, o in _INSIDE.items()}
    pos = {**beyond, Graha.MARS: 90.0}  # Mars alone between Rahu and Ketu
    r = kaal_sarpa(_kp(pos), lagna_lon=_lon(3))
    assert r is not None and r.kind == "partial" and r.outside == (Graha.MARS,)


_NAMES = (
    "anant", "kulik", "vasuki", "shankhpal", "padma", "mahapadma",
    "takshak", "karkotak", "shankhachud", "ghatak", "vishdhar", "sheshnag",
)  # fmt: skip


@pytest.mark.parametrize("i", range(12))
def test_kaal_sarpa_name_by_rahu_house(i: int) -> None:
    lagna_sign = 5
    rahu = ((lagna_sign + i) % 12) * 30.0 + 15.0  # Rahu in house i+1
    r = kaal_sarpa(_kp(_INSIDE, rahu=rahu), lagna_lon=_lon(lagna_sign))
    assert r is not None and r.name == _NAMES[i]


def test_sade_sati_phases_ordered() -> None:
    birth = jd_from_utc(datetime(1990, 1, 1, tzinfo=UTC))
    moon = 5 * 30.0 + 7.0  # Kanya
    phases, warnings = sade_sati(moon, birth, S, years=60)
    assert warnings == () and phases
    for a, b in itertools.pairwise(phases):
        assert a.start_utc < a.end_utc <= b.start_utc
    kinds = [p.kind for p in phases]
    assert "sade_sati_rising" in kinds and "sade_sati_peak" in kinds
    collapsed = [k for i, k in enumerate(kinds) if i == 0 or k != kinds[i - 1]]
    first = collapsed.index("sade_sati_rising")
    assert collapsed[first : first + 3] == [
        "sade_sati_rising",
        "sade_sati_peak",
        "sade_sati_setting",
    ]
    assert "dhaiya_4th" in kinds and "dhaiya_8th" in kinds


def test_sade_sati_active_at_birth_starts_at_birth() -> None:
    birth = jd_from_utc(datetime(2023, 6, 1, tzinfo=UTC))  # Saturn in Kumbha
    phases, _ = sade_sati(10 * 30.0 + 5.0, birth, S, years=5)
    assert phases[0].kind == "sade_sati_peak"
    assert phases[0].start_utc == datetime(2023, 6, 1, tzinfo=UTC)
    assert phases[-1].end_utc <= datetime(2028, 6, 1, 6, tzinfo=UTC)


def test_sade_sati_retrograde_reentry_makes_separate_records() -> None:
    birth = jd_from_utc(datetime(2022, 1, 1, tzinfo=UTC))
    phases, _ = sade_sati(10 * 30.0 + 5.0, birth, S, years=4)  # Moon in Kumbha
    kinds = [p.kind for p in phases]
    # Makara (rising) -> Kumbha (peak) -> Makara again (Jul 2022) -> Kumbha -> Meena (setting)
    assert kinds == [
        "sade_sati_rising",
        "sade_sati_peak",
        "sade_sati_rising",
        "sade_sati_peak",
        "sade_sati_setting",
    ]


def test_sade_sati_clamped_to_range() -> None:
    birth = jd_from_utc(datetime(2350, 1, 1, tzinfo=UTC))
    # Moon at Saturn's own longitude at JD_MAX: Saturn is in the peak sign when the range ends.
    moon = ephemeris.body_longitude(ephemeris.JD_MAX, Graha.SATURN, S)
    phases, warnings = sade_sati(moon, birth, S)
    assert any(isinstance(w, EngineWarning) and w.code == "range_clamped" for w in warnings)
    assert phases[-1].kind == "sade_sati_peak"
    assert phases[-1].end_utc == utc_from_jd(ephemeris.JD_MAX)
    assert all(p.end_utc <= utc_from_jd(ephemeris.JD_MAX) for p in phases)


def test_sade_sati_phase_still_active_at_end_is_cut_at_end() -> None:
    birth = jd_from_utc(datetime(2023, 6, 1, tzinfo=UTC))
    phases, _ = sade_sati(10 * 30.0 + 5.0, birth, S, years=1)  # peak throughout
    assert [p.kind for p in phases] == ["sade_sati_peak"]
    assert phases[0].end_utc == utc_from_jd(birth + 365.25)
