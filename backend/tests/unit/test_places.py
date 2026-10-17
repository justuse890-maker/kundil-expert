"""Offline place search over data/cities.tsv."""

import importlib.util
import sys
from pathlib import Path

import pytest

from api import places

BACKEND = Path(__file__).resolve().parents[2]


def test_varanasi_first_for_prefix() -> None:
    hits = places.search("varan")
    assert hits[0].name == "Varanasi"
    assert hits[0].tz == "Asia/Kolkata"
    assert hits[0].country == "IN"
    assert hits[0].admin1 == "Uttar Pradesh"
    assert hits == sorted(hits, key=lambda p: -p.population)  # ranked by population


def test_accent_and_case_insensitive() -> None:
    assert any(p.name == "São Paulo" for p in places.search("sao paulo"))
    assert any(p.name == "São Paulo" for p in places.search("SÃO PAU"))
    assert any(p.name == "Zürich" for p in places.search("zurich"))


def test_limit_and_empty_query() -> None:
    assert len(places.search("a", limit=3)) == 3
    assert places.search("   ") == []
    assert places.search("zzzzqqq") == []


def test_prefix_not_substring() -> None:
    assert places.search("anasi") == []


def test_every_place_has_a_known_timezone() -> None:
    from zoneinfo import ZoneInfo

    from vedic_engine import timeutil  # noqa: F401  (pins tz data to the tzdata package)

    assert places._index()._places
    for tz in {p.tz for p in places._index()._places}:
        ZoneInfo(tz)


@pytest.mark.network
def test_build_cities_script_downloads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location(
        "build_cities", BACKEND / "scripts" / "build_cities.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_cities"] = module
    spec.loader.exec_module(module)
    out = tmp_path / "cities.tsv"
    monkeypatch.setattr(module, "OUT", out)
    module.main()
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].split("\t") == list(module.COLUMNS)
    assert len(lines) > 20000
