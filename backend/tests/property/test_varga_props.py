import math

from hypothesis import given, settings
from hypothesis import strategies as st

from vedic_engine.angles import sign_of
from vedic_engine.varga import VARGAS, varga_sign

LON = st.floats(min_value=0.0, max_value=360.0, exclude_max=True, allow_nan=False)
# angles.norm folds values within 1e-9 below 360 to 0, so reference formulas are only compared
# away from that wrap-around residue.
LON_REF = st.floats(min_value=0.0, max_value=360.0 - 1e-6, allow_nan=False)


@given(lon=LON)
def test_d1_is_rashi(lon: float) -> None:
    assert varga_sign(lon, 1) == sign_of(lon)


@given(lon=LON_REF)
def test_d9_formula(lon: float) -> None:
    assert varga_sign(lon, 9) == math.floor(lon / (10 / 3)) % 12


@given(lon=LON_REF)
def test_d27_formula(lon: float) -> None:
    assert varga_sign(lon, 27) == math.floor(lon / (30 / 27)) % 12


@settings(max_examples=10_000, deadline=None)
@given(lon=LON)
def test_all_vargas_in_range(lon: float) -> None:
    for n in VARGAS:
        assert 0 <= varga_sign(lon, n) <= 11
