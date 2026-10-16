import json
from importlib import resources

from vedic_engine import constants as c
from vedic_engine.constants import Graha


def test_vimshottari_years_sum_120() -> None:
    assert sum(c.VIMSHOTTARI_YEARS.values()) == 120
    assert set(c.VIMSHOTTARI_ORDER) == set(c.VIMSHOTTARI_YEARS)
    assert len(c.VIMSHOTTARI_ORDER) == 9


def test_nakshatra_lords_cycle() -> None:
    def lord(key: str) -> Graha:
        return c.VIMSHOTTARI_ORDER[c.NAKSHATRAS.index(key) % 9]

    assert lord("ashwini") == Graha.KETU
    assert lord("punarvasu") == Graha.JUPITER
    assert lord("revati") == Graha.MERCURY


def test_counts() -> None:
    assert len(c.RASHIS) == 12 and len(c.RASHI_LORD) == 12
    assert len(c.NAKSHATRAS) == 27 and len(c.YOGAS) == 27
    assert len(c.TITHIS) == 30 and len(c.KARANAS_MOVABLE) == 7
    assert len(c.KARANAS_FIXED) == 4 and len(c.VAARS) == 7
    assert c.SEVEN == tuple(Graha)[:7]
    assert c.VAARS[0] == "soma" and c.VAARS[6] == "ravi"


def test_i18n_covers_all_keys() -> None:
    data = json.loads(
        resources.files("vedic_engine").joinpath("data/i18n.json").read_text(encoding="utf-8")
    )
    keys = (
        *c.RASHIS, *c.NAKSHATRAS, *(g.value for g in Graha), *c.TITHIS,
        *c.YOGAS, *c.KARANAS_MOVABLE, *c.KARANAS_FIXED,
    )  # fmt: skip
    for k in keys:
        assert data[k]["en"].strip(), k
        assert data[k]["hi"].strip(), k
