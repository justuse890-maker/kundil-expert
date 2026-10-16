import pytest

from vedic_engine.varga import VARGAS, varga_chart, varga_sign

# Sign indices: Mesha 0, Vrishabha 1, Mithuna 2, Karka 3, Simha 4, Kanya 5, Tula 6,
# Vrishchika 7, Dhanu 8, Makara 9, Kumbha 10, Meena 11.
# (n, sign, degree in sign, expected)
CASES = [
    # D1
    (1, 0, 5.0, 0),
    (1, 7, 29.9, 7),
    # D2: odd/even, both halves, edge
    (2, 0, 5.0, 4),
    (2, 0, 20.0, 3),
    (2, 1, 5.0, 3),
    (2, 1, 20.0, 4),
    (2, 0, 15.0, 3),
    (2, 1, 15.0, 4),
    # D3: first/last part, odd/even, movable/fixed/dual
    (3, 0, 5.0, 0),
    (3, 0, 25.0, 8),
    (3, 1, 15.0, 5),
    (3, 2, 29.0, 2 + 8),
    # D4
    (4, 0, 1.0, 0),
    (4, 0, 29.0, 9),
    (4, 1, 8.0, 4),
    (4, 2, 23.0, 2 + 9),
    # D7: odd from itself, even from 7th
    (7, 0, 0.0, 0),
    (7, 0, 29.9, 6),
    (7, 1, 0.0, 7),
    (7, 1, 29.9, 1 + 6 + 6),
    # D9: movable, fixed (9th), dual (5th)
    (9, 0, 0.0, 0),
    (9, 0, 29.99, 8),
    (9, 1, 1.0, 9),
    (9, 1, 4.0, 10),
    (9, 2, 1.0, 6),
    (9, 2, 29.9, 2),
    # D10: odd from itself, even from 9th
    (10, 0, 0.5, 0),
    (10, 0, 29.9, 9),
    (10, 1, 1.0, 9),
    (10, 1, 29.9, 6),
    # D12
    (12, 0, 1.0, 0),
    (12, 0, 29.9, 11),
    (12, 2, 5.0, 4),
    # D16: movable Mesha, fixed Simha, dual Dhanu
    (16, 0, 0.5, 0),
    (16, 0, 29.9, 15 % 12),
    (16, 1, 0.5, 4),
    (16, 1, 29.9, 4 + 15),
    (16, 2, 0.5, 8),
    (16, 2, 29.9, 8 + 15),
    # D20: movable Mesha, fixed Dhanu, dual Simha
    (20, 0, 0.5, 0),
    (20, 0, 29.9, 19),
    (20, 1, 0.5, 8),
    (20, 2, 0.5, 4),
    (20, 2, 29.9, 4 + 19),
    # D24: odd Simha, even Karka
    (24, 0, 0.5, 4),
    (24, 0, 29.9, 4 + 23),
    (24, 1, 0.5, 3),
    (24, 1, 29.9, 3 + 23),
    # D27: fire Mesha, earth Karka, air Tula, water Makara
    (27, 0, 0.1, 0),
    (27, 1, 0.1, 3),
    (27, 2, 0.1, 6),
    (27, 3, 0.1, 9),
    (27, 0, 29.99, 26 % 12),
    (27, 3, 29.99, 9 + 26),
    # D30: odd and even, every range, first and last
    (30, 0, 3.0, 0),
    (30, 0, 7.0, 10),
    (30, 0, 12.0, 8),
    (30, 0, 20.0, 2),
    (30, 0, 29.9, 6),
    (30, 1, 3.0, 1),
    (30, 1, 7.0, 5),
    (30, 1, 15.0, 11),
    (30, 1, 22.0, 9),
    (30, 1, 27.0, 7),
    (30, 0, 5.0, 10),
    (30, 1, 25.0, 7),
    # D40: odd from Mesha, even from Tula
    (40, 0, 0.1, 0),
    (40, 0, 29.9, 39),
    (40, 1, 0.1, 6),
    (40, 1, 29.9, 6 + 39),
    # D45: movable Mesha, fixed Simha, dual Dhanu
    (45, 0, 0.1, 0),
    (45, 0, 29.9, 44),
    (45, 1, 0.1, 4),
    (45, 2, 0.1, 8),
    (45, 2, 29.9, 8 + 44),
    # D60
    (60, 0, 0.25, 0),
    (60, 0, 29.75, 11),
    (60, 1, 0.25, 1),
    (60, 1, 29.75, 1 + 59),
]


@pytest.mark.parametrize(("n", "s", "d", "want"), CASES)
def test_varga_table(n: int, s: int, d: float, want: int) -> None:
    assert varga_sign(s * 30.0 + d, n) == want % 12


def test_varga_edges() -> None:
    # exactly 15.0 in D2 belongs to the upper part, including the odd sign
    assert varga_sign(15.0, 2) == 3
    assert varga_sign(30.0 + 15.0, 2) == 4
    for n in VARGAS:
        assert 0 <= varga_sign(359.9999999, n) <= 11


@pytest.mark.parametrize("n", [n for n in VARGAS if n not in (2, 30)])
def test_exact_division_edges_go_to_upper_part(n: int) -> None:
    # k * width must land in part k, including inexact widths 30/7, 30/16, 2/3
    parts = {
        1: 1,
        3: 3,
        4: 4,
        7: 7,
        9: 9,
        10: 10,
        12: 12,
        16: 16,
        20: 20,
        24: 24,
        27: 27,
        40: 40,
        45: 45,
        60: 60,
    }[n]
    width = 30.0 / parts
    for k in range(parts):
        d = k * width
        # part k of Mesha (odd, movable): compare with the value just inside part k
        inside = d + width / 2
        assert varga_sign(d, n) == varga_sign(inside, n), (n, k)


def test_d30_boundaries() -> None:
    assert varga_sign(5.0, 30) == 10 and varga_sign(4.999999, 30) == 0
    assert varga_sign(30.0 + 5.0, 30) == 5 and varga_sign(30.0 + 4.999999, 30) == 1


def test_unsupported_varga() -> None:
    for n in (0, 5, 61, -1):
        with pytest.raises(ValueError):
            varga_sign(10.0, n)


def test_varga_chart_keys() -> None:
    out = varga_chart({"sun": 5.0, "lagna": 50.0}, 9)
    assert out == {"sun": varga_sign(5.0, 9), "lagna": varga_sign(50.0, 9)}
