from hypothesis import given
from hypothesis import strategies as st

from vedic_engine.ashtakavarga import bav, sav
from vedic_engine.constants import SEVEN

KEYS = [g.value for g in SEVEN] + ["lagna"]
signs_st = st.fixed_dictionaries({k: st.integers(0, 11) for k in KEYS})
TOTALS = {
    "sun": 48,
    "moon": 49,
    "mars": 39,
    "mercury": 54,
    "jupiter": 56,
    "venus": 52,
    "saturn": 39,
}


@given(signs_st)
def test_sav_337(signs: dict[str, int]) -> None:
    result = sav(bav(signs))
    assert len(result) == 12
    assert sum(result) == 337


@given(signs_st)
def test_bav_totals_invariant(signs: dict[str, int]) -> None:
    result = bav(signs)
    assert {g.value: sum(v) for g, v in result.items()} == TOTALS
    assert all(len(v) == 12 and all(0 <= b <= 8 for b in v) for v in result.values())
