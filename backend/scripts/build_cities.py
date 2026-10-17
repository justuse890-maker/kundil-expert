"""Build data/cities.tsv from GeoNames cities15000 (dev-time only, needs network).

Run manually from backend/:  uv run python scripts/build_cities.py
The TSV it writes is committed; the service and the tests never hit the network.

GeoNames data is licensed CC-BY 4.0 (https://www.geonames.org/); see NOTICE.md.
Source: https://download.geonames.org/export/dump/cities15000.zip (columns documented in
https://download.geonames.org/export/dump/readme.txt). The admin1 names come from
admin1CodesASCII.txt of the same dump. Kept columns: name, asciiname, admin1, country (ISO
code), lat, lon, population, timezone. Rows without a timezone are dropped.
"""

from __future__ import annotations

import csv
import io
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://download.geonames.org/export/dump/"
OUT = Path(__file__).resolve().parent.parent / "data" / "cities.tsv"
COLUMNS = ("name", "asciiname", "admin1", "country", "lat", "lon", "population", "tz")


def fetch(name: str) -> bytes:
    with urllib.request.urlopen(BASE + name, timeout=120) as response:
        data: bytes = response.read()
    return data


def admin1_names() -> dict[str, str]:
    text = fetch("admin1CodesASCII.txt").decode("utf-8")
    out: dict[str, str] = {}
    for line in text.splitlines():
        code, _name, ascii_name, _id = line.split("\t")
        out[code] = ascii_name
    return out


def main() -> None:
    admin1 = admin1_names()
    archive = zipfile.ZipFile(io.BytesIO(fetch("cities15000.zip")))
    rows = []
    with archive.open("cities15000.txt") as raw:
        for line in io.TextIOWrapper(raw, encoding="utf-8"):
            f = line.rstrip("\n").split("\t")
            if len(f) < 19 or not f[17]:
                continue
            country, code = f[8], f[10]
            rows.append(
                (
                    f[1],
                    f[2],
                    admin1.get(f"{country}.{code}", ""),
                    country,
                    f[4],
                    f[5],
                    int(f[14] or 0),
                    f[17],
                )
            )
    rows.sort(key=lambda r: (-r[6], r[0], r[3], r[4], r[5]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(
            fh, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_NONE, escapechar="\\"
        )
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    print(f"wrote {len(rows)} cities to {OUT}")


if __name__ == "__main__":
    main()
