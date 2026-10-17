"""U14a/b/c: friendly ``why`` wording, capitalised names, neutral phrasing of maraka text."""

import json
import re
from collections.abc import Iterator
from importlib import resources
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api import main
from vedic_engine.analysis.friendly import cap_names, friendly, split_why

CHARTS: list[dict[str, Any]] = [
    {"date": "1947-08-15", "time": "00:00", "lat": 28.6139, "lon": 77.209, "tz": "Asia/Kolkata"},
    {"date": "1990-03-05", "time": "14:20", "lat": 19.07, "lon": 72.87, "tz": "Asia/Kolkata"},
    {"date": "1985-11-23", "time": "05:10", "lat": 51.5, "lon": -0.12, "tz": "Europe/London"},
    {"date": "1975-07-01", "lat": 13.08, "lon": 80.27, "tz": "Asia/Kolkata", "time_known": False},
    {"date": "2001-01-09", "time": "22:45", "lat": 40.7, "lon": -74.0, "tz": "America/New_York"},
]
NOW = "2026-10-17T06:30:00Z"
PLANETS = r"sun|moon|mars|mercury|jupiter|venus|saturn|rahu|ketu"
SIGNS = r"mesha|vrishabha|mithuna|karka|simha|kanya|tula|vrishchika|dhanu|makara|kumbha|meena"
LEAKS = [
    r"->", r"decided by", r"\(\d+ - \d+\)", r"judge_period", r"engine phase",
    r"\b[a-z]+_[a-z0-9]+\b", rf"\b({PLANETS}|{SIGNS})\b",
]  # fmt: skip
ALARMING = re.compile(r"\b(death|dead|kill\w*|fatal\w*|die[sd]?)\b", re.IGNORECASE)


@pytest.fixture(scope="module")
def bodies() -> Iterator[list[dict[str, Any]]]:
    out: list[dict[str, Any]] = []
    with TestClient(main.app) as c:
        for ch in CHARTS:
            for mode in ("summary", "full"):
                r = c.post("/api/v1/analysis", json={**ch, "now_utc": NOW, "detail": mode})
                assert r.status_code == 200, r.text
                out.append(r.json())
            r = c.post("/api/v1/analysis", json={**ch, "now_utc": NOW, "gender": "female"})
            out.append(r.json())
            r = c.post("/api/v1/daily", json={**ch, "today": "2026-10-17"})
            assert r.status_code == 200, r.text
            out.append(r.json())
        yield out


def walk(o: Any, key: str | None = None) -> Iterator[tuple[str | None, str]]:
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, k)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v, key)
    elif isinstance(o, str):
        yield key, o


def test_why_has_no_internal_notation(bodies: list[dict[str, Any]]) -> None:
    seen = 0
    for body in bodies:
        for key, text in walk(body):
            if key != "why":
                continue
            seen += 1
            for pat in LEAKS:
                assert not re.search(pat, text), f"{pat!r} in why: {text}"
    assert seen > 1000


def test_detail_keeps_the_raw_facts(bodies: list[dict[str, Any]]) -> None:
    details = [t for b in bodies for k, t in walk(b) if k == "detail"]
    assert any("->" in t for t in details)
    assert any("decided by" in t for t in details)


def test_no_alarming_words_in_any_response_text(bodies: list[dict[str, Any]]) -> None:
    for body in bodies:
        for _, text in walk(body):
            assert not ALARMING.search(text), text


def test_no_alarming_words_in_data_files() -> None:
    root = resources.files("vedic_engine.analysis").joinpath("data")
    for f in root.iterdir():
        if not f.name.endswith(".json"):
            continue

        def values(o: Any) -> Iterator[str]:
            if isinstance(o, dict):
                for k, v in o.items():
                    if not k.startswith("_"):
                        yield from values(v)
            elif isinstance(o, list):
                for v in o:
                    yield from values(v)
            elif isinstance(o, str):
                yield o

        for text in values(json.loads(f.read_text(encoding="utf-8"))):
            assert not ALARMING.search(text), f"{f.name}: {text}"


def test_maraka_text_is_neutral(bodies: list[dict[str, Any]]) -> None:
    texts = {t for b in bodies for k, t in walk(b) if k == "text" and "maraka" in t}
    assert texts
    assert all("traditionally read with care for health" in t for t in texts)


def test_multi_lord_reasons_name_their_lord(bodies: list[dict[str, Any]]) -> None:
    india = bodies[0]
    cur = india["periods"]["current"]
    table = india["periods"]["reasons"]
    praty = [table[i]["why"][0] for i in cur["pratyantar"]["judgement"]["reasons"]]
    antar = [table[i]["why"][0] for i in cur["antar"]["judgement"]["reasons"]]
    pair = re.compile(r"\w+ (is the \d+\w+ sign from|and \w+ are in the same sign)")
    lord = re.compile(r"\w+ \((mahadasha|antardasha|pratyantar) lord\)")
    assert all(lord.match(w) or pair.match(w) for w in praty + antar)
    assert any(lord.match(w) for w in praty)
    assert any(w.startswith("Rahu (antardasha lord)") for w in antar)


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("rahu strength 85/100 -> (85 - 50) / 2", "Rahu is strong (85/100)"),
        ("mars Shadbala ratio 1.44 (>= 1)", "Mars has Shadbala above the classical minimum"),
        ("mars Shadbala ratio 0.9 (< 1)", "Mars has Shadbala below the classical minimum"),
        ("Saturn strength 50/100 (dignity -10, shadbala +15)", "Saturn strength 50/100"),
        ("mars is in house 8 (6/8/12)", "Mars is in house 8, a difficult (6th, 8th or 12th) house"),
        ("weekday lord saturn is a functional benefic", "Weekday lord Saturn is a functional benefic"),
        ("jupiter in kanya from 2028-07-24 to 2028-10-17", "Jupiter in Kanya from 2028-07-24 to 2028-10-17"),
        ("10th lord Saturn in 3rd (Karka)", "10th lord Saturn in 3rd (Karka)"),
    ],
)  # fmt: skip
def test_friendly_cases(raw: str, want: str) -> None:
    assert friendly(raw) == want


def test_lordship_sentence_and_detail() -> None:
    raw = (
        "mars rules house 7, 12 for vrishabha lagna (moolatrikona in house 12); "
        "classified as neutral by bphs_lagna; lordship rule: malefic kendra -> neutral; "
        "decided by: bphs_lagna"
    )
    why, detail = split_why([raw])
    assert why == [
        "Mars rules houses 7 and 12; Parasara's list for Vrishabha lagna classifies it as neutral"
    ]
    assert detail == [raw]


def test_cap_names() -> None:
    assert cap_names("saturn in meena") == "Saturn in Meena"


def test_why_role_word_is_the_final_role_for_every_lagna_and_graha() -> None:
    from vedic_engine.analysis.functional import Role, functional_roles
    from vedic_engine.constants import Graha

    words = {r.value for r in Role if r is not Role.MARAKA}
    for lagna in range(12):
        for waxing in (True, False):
            for g, fr in functional_roles(lagna, waxing).items():
                if g in (Graha.RAHU, Graha.KETU):
                    continue
                for pre in ("", f"{g.value} is {fr.role.value} for this chart (Moon-based): "):
                    out = friendly(pre + fr.why)
                    found = {w for w in words if re.search(rf"\b{w}\b", out)}
                    assert found == {fr.role.value}, (lagna, g, out, fr.role)
                assert "->" not in out


def _dicts(o: Any) -> Iterator[dict[str, Any]]:
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _dicts(v)
    elif isinstance(o, list):
        for v in o:
            yield from _dicts(v)


def test_api_role_reasons_agree_with_the_verdict(bodies: list[dict[str, Any]]) -> None:
    roles = {"benefic", "malefic", "neutral", "yogakaraka"}
    checked = 0
    for body in bodies:
        for d in _dicts(body):
            code = d.get("code")
            final = (
                code.split(":", 1)[1]
                if isinstance(code, str) and code.startswith("role:") and code != "role:maraka"
                else d.get("role")
                if d.get("role") in roles and "houses" in d
                else None
            )
            if final is None or not d.get("why"):
                continue
            text = " ".join(d["why"])
            if "rules house" not in text:
                continue
            checked += 1
            found = {w for w in roles if re.search(rf"\b{w}\b", text)}
            assert found == {final}, (final, text)
    assert checked > 50
