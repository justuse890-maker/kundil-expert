from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def ephe_path() -> Path:
    """Directory holding the shipped Swiss Ephemeris .se1 files."""
    return Path(__file__).resolve().parent.parent / "ephe"
