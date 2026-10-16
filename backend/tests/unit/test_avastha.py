import pytest

from vedic_engine.avastha import baladi


@pytest.mark.parametrize(
    ("lon", "expected"),
    [
        (13.0, "yuva"),  # Mesha (odd) 13
        (43.0, "yuva"),  # Vrishabha (even) 13
        (32.0, "mrita"),  # Vrishabha 2
        (29.0, "mrita"),  # Mesha 29
        (1.0, "bala"),
        (6.0, "kumara"),
        (18.0, "vriddha"),
        (24.0, "mrita"),
        (59.9, "bala"),  # Vrishabha 29.9
        (36.0, "vriddha"),  # Vrishabha 6
        (359.9, "bala"),  # Meena (even) 29.9
    ],
)
def test_baladi(lon: float, expected: str) -> None:
    assert baladi(lon) == expected
