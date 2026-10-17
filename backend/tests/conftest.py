from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def ephe_path() -> Path:
    """Directory holding the shipped Swiss Ephemeris .se1 files."""
    return Path(__file__).resolve().parent.parent / "ephe"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-snapshot",
        action="store_true",
        default=False,
        help="rewrite tests/snapshots/*.json from the current output (deliberate API change)",
    )
