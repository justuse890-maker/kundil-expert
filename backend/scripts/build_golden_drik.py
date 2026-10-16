"""Transcribe Drik Panchang day pages for New Delhi into golden fixtures (dev-time, needs network).

Run manually from backend/:  uv run python scripts/build_golden_drik.py
The JSON written under fixtures/golden/drik/ is committed; tests never hit the network.

Only what the page displays is transcribed: sunrise, sunset, moonrise, moonset and every
tithi / nakshatra / yoga / karana row with its "upto" time (the last row of each element has no
end time on the page: it continues past the next sunrise). Drik prints end times after midnight
as e.g. "06:51 AM, Jan 11"; the date suffix is resolved against the page date. Each element's
index is read from the page's own element-info attribute and cross-checked against the
displayed name, so a key is never guessed from a name alone.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.request
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vedic_engine.constants import (
    KARANAS_FIXED,
    KARANAS_MOVABLE,
    NAKSHATRAS,
    TITHIS,
    YOGAS,
)

OUT_DIR = ROOT / "fixtures" / "golden" / "drik"
GEONAME_ID = 1261481  # New Delhi, as used by drikpanchang.com
URL = "https://www.drikpanchang.com/panchang/day-panchang.html?geoname-id={gid}&date={d:%d/%m/%Y}"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko)"

# (date, why it is in the set)
DATES: tuple[tuple[date, str], ...] = (
    (date(2024, 1, 10), "winter; four karanas in one day (Vishti, Shakuni, Chatushpada)"),
    (date(2024, 3, 12), "kshaya tithi: Shukla Tritiya starts after sunrise, ends before the next"),
    (date(2024, 6, 21), "June solstice, earliest-sunrise season"),
    (date(2024, 9, 15), "monsoon"),
    (date(2024, 12, 1), "late autumn"),
    (date(2025, 2, 14), "late winter"),
    (date(2025, 4, 30), "spring"),
    (date(2025, 7, 15), "monsoon"),
    (date(2025, 10, 21), "autumn"),
    (date(2025, 12, 25), "winter"),
    # 2024 and 2025 contain no Adhik masa (2023 Shravana and 2026 Jyeshtha do), so the
    # Adhik-masa date is an eleventh date outside those years.
    (date(2023, 8, 1), "Adhik (Adhika) Shravana masa, 2023"),
)

_MONTHS = {
    m: i
    for i, m in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1
    )
}
_TIME = re.compile(r"(\d{1,2}):(\d{2}) (AM|PM)(?:, ([A-Z][a-z]{2}) (\d{1,2}))?$")
_LOC = re.compile(
    r"Latitude: (\d+)° (\d+)′ (\d+)″ ([NS]) \| Longitude: (\d+)° (\d+)′ (\d+)″ ([EW]) \| "
    r"Elevation: (-?\d+) m \| Olson Timezone: ([\w/]+)"
)

# Drik spellings that differ from the engine keys.
_ALIASES = {
    "kinstughna": "kimstughna", "nagava": "naga", "dhanishtha": "dhanishta",
    "shatabhisha": "shatabhisha", "mrigashirsha": "mrigashira", "ashvini": "ashwini",
    "pratipada": "pratipada", "dvitiya": "dwitiya", "garaja": "gara", "ayushmana": "ayushman", "variyana": "variyan",
}  # fmt: skip


class _Cells(HTMLParser):
    """Collect table rows -> cells (class, text, element-info) inside two card wrappers."""

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.rows: list[list[dict[str, str]]] = []
        self.cell: dict[str, str] | None = None
        self.cell_depth = -1
        self.popup_depth = -1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "div":
            return
        self.depth += 1
        a = dict(attrs)
        cls = a.get("class") or ""
        if "dpTableRow" in cls.split():
            self.rows.append([])
        elif "dpTableCell" in cls.split() and self.rows:
            kind = "key" if "dpTableKey" in cls else "value"
            self.cell = {"kind": kind, "text": "", "info": ""}
            self.cell_depth = self.depth
            self.rows[-1].append(self.cell)
        elif "dpElementInfoPopupWrapper" in cls.split():
            if self.cell is not None and not self.cell["info"]:
                self.cell["info"] = a.get("data-element-info") or ""
            self.popup_depth = self.depth

    def handle_endtag(self, tag: str) -> None:
        if tag != "div":
            return
        if self.depth == self.popup_depth:
            self.popup_depth = -1
        if self.depth == self.cell_depth:
            self.cell = None
            self.cell_depth = -1
        self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.cell is not None and self.popup_depth == -1:
            self.cell["text"] += data


def _section(page: str, start: str, end: str) -> str:
    i = page.index(start)
    return page[i : page.index(end, i)]


def _rows(fragment: str) -> list[list[dict[str, str]]]:
    p = _Cells()
    p.feed(fragment)
    for row in p.rows:
        for c in row:
            c["text"] = " ".join(c["text"].split())
    return p.rows


def _local(text: str, day: date) -> str:
    m = _TIME.match(text)
    if m is None:
        raise ValueError(f"unparsed time {text!r}")
    hh, mm, ampm, mon, dd = m.groups()
    h = int(hh) % 12 + (12 if ampm == "PM" else 0)
    d = day
    if mon is not None:
        d = date(day.year, _MONTHS[mon], int(dd))
        if d < day - timedelta(days=2):  # "Jan 1" printed on a Dec 31 page
            d = date(day.year + 1, _MONTHS[mon], int(dd))
    return datetime(d.year, d.month, d.day, h, int(mm)).isoformat(timespec="minutes")


def _text(page: str) -> str:
    """Visible text with tags collapsed to " | " separators."""
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.DOTALL)
    t = html.unescape(re.sub(r"<[^>]+>", "|", t))
    return re.sub(r"\s*\|[\s|]*", " | ", t)


def _norm_name(name: str) -> str:
    n = name.lower().replace(" ", "_")
    return _ALIASES.get(n, n)


def _key(element: str, index: int) -> str:
    if element == "tithi":
        return TITHIS[index - 1]
    if element == "nakshatra":
        return NAKSHATRAS[index - 1]
    if element == "yoga":
        return YOGAS[index - 1]
    # Drik numbers the 60 half-tithis 1..60 from Shukla Pratipada's first half (Kimstughna).
    k = index - 1
    if k == 0:
        return KARANAS_FIXED[0]
    if k >= 57:
        return KARANAS_FIXED[k - 56]
    return KARANAS_MOVABLE[(k - 1) % 7]


def _check_name(element: str, name: str, key: str) -> None:
    n = _norm_name(name)
    if element == "tithi":
        if not (key == n or key.endswith("_" + n)):
            raise ValueError(f"tithi name {name!r} does not match index key {key!r}")
    elif n != key:
        raise ValueError(f"{element} name {name!r} does not match index key {key!r}")


def parse(page: str, day: date) -> dict[str, object]:
    loc = _LOC.search(_text(page))
    if loc is None:
        raise ValueError("location block not found")
    g = loc.groups()
    lat = (int(g[0]) + int(g[1]) / 60 + int(g[2]) / 3600) * (1 if g[3] == "N" else -1)
    lon = (int(g[4]) + int(g[5]) / 60 + int(g[6]) / 3600) * (1 if g[7] == "E" else -1)

    sun: dict[str, str | None] = {}
    for row in _rows(_section(page, "Sunrise and Moonrise</h3>", "dpCorePanchangCardWrapper")):
        for i in range(0, len(row) - 1, 2):
            k, v = row[i]["text"], row[i + 1]["text"]
            sun[k.lower()] = None if v.startswith("No ") else _local(v, day)

    elements: dict[str, list[dict[str, object]]] = {}
    columns: dict[int, str] = {}
    for row in _rows(_section(page, 'dpTableCardTitle">Panchang</h3>', "dpLunarDateCardWrapper")):
        for col, i in enumerate(range(0, len(row) - 1, 2)):
            label, value = row[i]["text"].lower(), row[i + 1]
            if label:
                columns[col] = label
            element = columns.get(col)
            if element not in ("tithi", "nakshatra", "yoga", "karana"):
                continue
            text = value["text"]
            if not text:  # padding cell when the other column has more rows
                continue
            name, _, upto = text.partition(" upto ")
            index = int(value["info"].split("=", 1)[1].split(";", 1)[0])
            key = _key(element, index)
            _check_name(element, name, key)
            elements.setdefault(element, []).append(
                {
                    "drik_name": name,
                    "drik_index": index,
                    "key": key,
                    "upto_display": upto or None,
                    # "Full Night": the element outlasts the next sunrise; no end time shown.
                    "ends_local": _local(upto, day) if upto and upto != "Full Night" else None,
                }
            )
    text = _text(page)
    purnimanta = re.search(r"Chandramasa \| ([^|]+?) \| - \| Purnimanta", text)
    amanta = re.search(r"\| ([^|]+?) \| - \| Amanta", text)
    if purnimanta is None or amanta is None:
        raise ValueError("lunar month not found")
    return {
        "chandramasa": {"purnimanta": purnimanta.group(1), "amanta": amanta.group(1)},
        "location": {
            "name": "New Delhi, India",
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "elevation_m": int(g[8]),
            "tz": g[9],
        },
        "sunrise_local": sun["sunrise"],
        "sunset_local": sun["sunset"],
        "moonrise_local": sun.get("moonrise"),
        "moonset_local": sun.get("moonset"),
        "elements": elements,
    }


def main(argv: list[str]) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(UTC).date().isoformat()
    for day, why in DATES:
        url = URL.format(gid=GEONAME_ID, d=day)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            page = resp.read().decode("utf-8")
        fixture = {
            "source": "Drik Panchang (drikpanchang.com), day panchang page",
            "url": url,
            "retrieved": retrieved,
            "date": day.isoformat(),
            "why": why,
            **parse(page, day),
        }
        path = OUT_DIR / f"delhi_{day.isoformat()}.json"
        path.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n")
        print(path.name)
        time.sleep(2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
