from pathlib import Path

import swisseph as swe

import vedic_engine

EPHE_FILES = ("sepl_18.se1", "semo_18.se1", "seas_18.se1")


def test_version() -> None:
    assert vedic_engine.__version__ == "0.1.0"


def test_ephe_files_present(ephe_path: Path) -> None:
    for name in EPHE_FILES:
        f = ephe_path / name
        assert f.is_file(), f"missing {f}"
        assert f.stat().st_size > 100_000, f"{f} too small"


def test_swisseph_importable() -> None:
    assert swe.version.startswith("2.10")
