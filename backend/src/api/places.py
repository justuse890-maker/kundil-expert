"""Offline place search over ``data/cities.tsv`` (GeoNames cities15000, CC-BY 4.0).

Case- and diacritic-insensitive prefix match on the name or ASCII name, ranked by population.
"""

import bisect
import csv
import os
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path

DEFAULT_CITIES = Path(__file__).resolve().parents[2] / "data" / "cities.tsv"


@dataclass(frozen=True, slots=True)
class Place:
    name: str
    admin1: str
    country: str
    lat: float
    lon: float
    tz: str
    population: int


def fold(text: str) -> str:
    """Lowercase, strip diacritics and collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.split())


class PlaceIndex:
    def __init__(self, path: Path) -> None:
        self._places: list[Place] = []
        keys: dict[str, set[int]] = {}
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
                idx = len(self._places)
                self._places.append(
                    Place(
                        name=row["name"],
                        admin1=row["admin1"],
                        country=row["country"],
                        lat=float(row["lat"]),
                        lon=float(row["lon"]),
                        tz=row["tz"],
                        population=int(row["population"]),
                    )
                )
                for label in (row["name"], row["asciiname"]):
                    keys.setdefault(fold(label), set()).add(idx)
        self._keys = sorted(keys)
        self._ids = [sorted(keys[k]) for k in self._keys]

    def search(self, q: str, limit: int = 10) -> list[Place]:
        prefix = fold(q)
        if not prefix or limit <= 0:
            return []
        hits: set[int] = set()
        i = bisect.bisect_left(self._keys, prefix)
        while i < len(self._keys) and self._keys[i].startswith(prefix):
            hits.update(self._ids[i])
            i += 1
        # Population first; the file order (already by population, then name) breaks ties.
        ranked = sorted(hits, key=lambda n: (-self._places[n].population, n))
        return [self._places[n] for n in ranked[:limit]]


@cache
def _index() -> PlaceIndex:
    return PlaceIndex(Path(os.environ.get("VEDIC_CITIES_TSV", DEFAULT_CITIES)))


def search(q: str, limit: int = 10) -> list[Place]:
    """Up to ``limit`` places whose name or ASCII name starts with ``q``, most populous first."""
    return _index().search(q, limit)
