"""Load the golden birth charts built by scripts/build_golden_charts.py."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from vedic_engine.models import BirthInput

CHART_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "golden" / "charts"
CHART_PATHS = sorted(CHART_DIR.glob("*.json"))


def load_chart(path_or_id: Path | str) -> dict[str, Any]:
    path = path_or_id if isinstance(path_or_id, Path) else CHART_DIR / f"{path_or_id}.json"
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def birth_of(chart: dict[str, Any]) -> BirthInput:
    b = chart["birth"]
    return BirthInput(
        local=datetime.fromisoformat(b["local"]),
        tz=b["tz"],
        lat=b["lat"],
        lon=b["lon"],
        alt=b["alt"],
        fold=b["fold"],
    )
