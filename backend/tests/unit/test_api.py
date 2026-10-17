"""HTTP API (FastAPI TestClient): v1 endpoints, error mapping, snapshot, frontend mount."""

import itertools
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api import main, serialize
from chart_fixtures import CHART_PATHS, load_chart
from vedic_engine.models import EngineError

SNAPSHOT = Path(__file__).resolve().parents[1] / "snapshots" / "openapi.json"
DELHI = {"lat": 28.6139, "lon": 77.2090}


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(main.app) as c:  # runs the lifespan: ephemeris.init + place index
        yield c


def request_of(chart: dict[str, Any]) -> dict[str, Any]:
    b = chart["birth"]
    date, time = b["local"].split("T")
    body: dict[str, Any] = {
        "date": date,
        "time": time,
        "tz": b["tz"],
        "lat": b["lat"],
        "lon": b["lon"],
        "alt": b["alt"],
    }
    if b["fold"] is not None:
        body["fold"] = b["fold"]
    return body


def golden0() -> dict[str, Any]:
    return load_chart(CHART_PATHS[0])


DELHI_2000 = {"date": "2000-01-01", "time": "12:00", "tz": "Asia/Kolkata", **DELHI}


def test_kundli_ok(client: TestClient) -> None:
    chart = golden0()
    r = client.post("/api/v1/kundli", json=request_of(chart))
    assert r.status_code == 200, r.text
    body = r.json()
    exp = chart["expected"]
    assert body["lagna"]["rashi_key"] == exp["lagna_rashi"]
    assert body["lagna"]["rashi"] == 9  # dhanu, 1-based
    moon = body["grahas"]["moon"]
    assert moon["nakshatra_key"] == exp["moon_nakshatra"]
    assert moon["pada"] == exp["moon_pada"]
    assert body["panchang"]["tithi"]["index"] == exp["tithi"]
    assert body["panchang"]["tithi"]["key"] == exp["tithi_key"]
    assert body["vimshottari"][0]["lord"] == exp["first_maha_lord"]
    assert body["vargas"]["d9"]["lagna"]["rashi_key"] == exp["d9_lagna"]
    assert set(body["grahas"]) == {
        "sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu",
    }  # fmt: skip
    assert len(body["bhavas"]) == 12 and body["bhavas"][0]["house"] == 1
    assert body["meta"]["lagna_basis"] == "ascendant"
    assert "vargottama" in body["grahas"]["sun"]
    assert body["shadbala"]["sun"]["total_rupa"] > 0
    assert set(body["vargas"]) == {f"d{n}" for n in (1, 2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27,
                                                      30, 40, 45, 60)}  # fmt: skip


def test_instants_come_as_utc_and_local_pairs(client: TestClient) -> None:
    body = client.post("/api/v1/kundli", json=request_of(golden0())).json()
    # Auckland 2010-02-14 03:15 NZDT (+13:00) = 2010-02-13 14:15 UTC
    assert body["meta"]["birth_utc"] == "2010-02-13T14:15:00Z"
    assert body["meta"]["birth_local"] == "2010-02-14T03:15:00+13:00"
    maha = body["vimshottari"][0]
    assert maha["start_utc"].endswith("Z") and maha["end_local"].endswith("+13:00")
    ends = body["panchang"]["tithi"]
    assert ends["ends_utc"].endswith("Z") and "ends_local" in ends


def test_degrees_are_unrounded_floats_with_dms(client: TestClient) -> None:
    body = client.post("/api/v1/kundli", json=request_of(golden0())).json()
    sun = body["grahas"]["sun"]
    assert isinstance(sun["lon"], float) and len(repr(sun["lon"])) > 10
    assert sun["deg_in_sign"] == pytest.approx(sun["lon"] % 30.0)
    assert "°" in sun["dms"] and "′" in sun["dms"]


def test_dms_truncates_never_rolls_to_thirty() -> None:
    assert serialize.dms(29.999999999999) == "29°59′59.99″"
    assert serialize.dms(0.0) == "0°00′00.00″"
    assert serialize.dms(12.5) == "12°30′00.00″"
    assert serialize.dms(1 + 1 / 60 + 1 / 3600) == "1°01′01.00″"


def test_api_ambiguous_time_422(client: TestClient) -> None:
    body = {"date": "2021-11-07", "time": "01:30", "tz": "America/New_York",
            "lat": 40.7128, "lon": -74.006}  # fmt: skip
    r = client.post("/api/v1/kundli", json=body)
    assert r.status_code == 422
    assert "fold" in json.dumps(r.json()["detail"])
    assert client.post("/api/v1/kundli", json={**body, "fold": 1}).status_code == 200


def test_nonexistent_time_422(client: TestClient) -> None:
    body = {"date": "2021-03-14", "time": "02:30", "tz": "America/New_York",
            "lat": 40.7128, "lon": -74.006}  # fmt: skip
    r = client.post("/api/v1/kundli", json=body)
    assert r.status_code == 422
    assert "does not exist" in json.dumps(r.json()["detail"])


@pytest.mark.parametrize("date", ["1700-01-01", "2500-06-01"])
def test_out_of_range_422(client: TestClient, date: str) -> None:
    r = client.post("/api/v1/kundli", json={**DELHI_2000, "date": date})
    assert r.status_code == 422
    assert "date" in json.dumps(r.json()["detail"])


def test_bad_tz_422(client: TestClient) -> None:
    r = client.post("/api/v1/kundli", json={**DELHI_2000, "tz": "Mars/Olympus_Mons"})
    assert r.status_code == 422
    assert "tz" in json.dumps(r.json()["detail"])


@pytest.mark.parametrize(
    "field,value", [("lat", 90.5), ("lat", -91), ("lon", 180.1), ("lon", -181)]
)
def test_lat_out_of_range_422(client: TestClient, field: str, value: float) -> None:
    r = client.post("/api/v1/kundli", json={**DELHI_2000, field: value})
    assert r.status_code == 422
    assert field in json.dumps(r.json()["detail"])


def _zone_less() -> dict[str, Any]:
    return {k: v for k, v in DELHI_2000.items() if k != "tz"}


@pytest.mark.parametrize(
    "zone",
    [
        {},
        {"tz": "Asia/Kolkata", "utc_offset": "+05:30"},
        {"tz": "Asia/Kolkata", "lmt": True},
        {"utc_offset": "+05:30", "lmt": True},
        {"utc_offset": "5:30"},
        {"utc_offset": "+05:30:00:00"},
    ],
)
def test_exactly_one_zone_422(client: TestClient, zone: dict[str, Any]) -> None:
    assert client.post("/api/v1/kundli", json={**_zone_less(), **zone}).status_code == 422


def test_lmt_false_is_not_a_zone(client: TestClient) -> None:
    r = client.post("/api/v1/kundli", json={**DELHI_2000, "lmt": False})
    assert r.status_code == 200


def test_utc_offset_equals_the_same_iana_zone(client: TestClient) -> None:
    a = client.post("/api/v1/kundli", json=DELHI_2000).json()
    b = client.post("/api/v1/kundli", json={**_zone_less(), "utc_offset": "+05:30"}).json()
    assert a["meta"]["birth_utc"] == b["meta"]["birth_utc"] == "2000-01-01T06:30:00Z"
    assert b["meta"]["birth_local"] == "2000-01-01T12:00:00+05:30"
    assert b["meta"]["tz"] == "UTC+05:30"
    assert a["lagna"]["lon"] == b["lagna"]["lon"]


def test_engine_rejects_out_of_range_offset_as_422(client: TestClient) -> None:
    r = client.post("/api/v1/kundli", json={**_zone_less(), "utc_offset": "+15:00"})
    assert r.status_code == 422


def test_lmt(client: TestClient) -> None:
    r = client.post("/api/v1/kundli", json={**_zone_less(), "lmt": True})
    assert r.status_code == 200, r.text
    meta = r.json()["meta"]
    assert meta["lmt"] is True
    # 77.2090 deg / 15 = 5 h 8 min 50.16 s
    assert meta["birth_local"] == "2000-01-01T12:00:00+05:09"
    assert meta["birth_utc"] == "2000-01-01T06:51:10Z"
    assert meta["utc_offset_seconds"] == pytest.approx(5 * 3600 + 8 * 60 + 50.16, abs=0.01)


def test_extra_fields_rejected(client: TestClient) -> None:
    assert client.post("/api/v1/kundli", json={**DELHI_2000, "colour": "red"}).status_code == 422


def test_kundli_time_unknown(client: TestClient) -> None:
    body = {k: v for k, v in DELHI_2000.items() if k != "time"}
    r = client.post("/api/v1/kundli", json={**body, "time_known": False})
    assert r.status_code == 200, r.text
    k = r.json()
    assert k["meta"]["time_known"] is False and k["meta"]["lagna_basis"] == "moon"
    assert k["meta"]["birth_utc"] is None and k["meta"]["birth_local"] is None
    assert k["lagna"]["rashi_key"] == k["grahas"]["moon"]["rashi_key"]
    assert k["shadbala"] is None
    assert k["sensitivity"] == []
    assert k["doshas"]["manglik"]["from_lagna"] is None
    assert "time_unknown" in {w["code"] for w in k["warnings"]}


def test_time_required_when_known(client: TestClient) -> None:
    body = {k: v for k, v in DELHI_2000.items() if k != "time"}
    r = client.post("/api/v1/kundli", json=body)
    assert r.status_code == 422
    assert "time" in json.dumps(r.json()["detail"])


def test_kundli_ayanamsa_kp(client: TestClient) -> None:
    lahiri = client.post("/api/v1/kundli", json=DELHI_2000).json()
    kp = client.post("/api/v1/kundli", json={**DELHI_2000, "settings": {"ayanamsa": "KP"}}).json()
    assert kp["meta"]["settings"]["ayanamsa"] == "KP"
    assert lahiri["meta"]["settings"]["ayanamsa"] == "LAHIRI"
    delta = lahiri["meta"]["ayanamsa_deg"] - kp["meta"]["ayanamsa_deg"]
    assert 0.0 < delta < 0.1  # KP is a few arcmin below Lahiri
    assert lahiri["grahas"]["sun"]["lon"] - kp["grahas"]["sun"]["lon"] == pytest.approx(-delta)
    r = client.post("/api/v1/kundli", json={**DELHI_2000, "settings": {"ayanamsa": "TROPICAL"}})
    assert r.status_code == 422


def test_sensitivity_infinity_is_null_with_edge_flags(client: TestClient) -> None:
    r = client.post("/api/v1/kundli", json=request_of(golden0()))
    assert "Infinity" not in r.text and "NaN" not in r.text
    items = r.json()["sensitivity"]
    assert [i["item"] for i in items] == [
        "lagna", "moon_nakshatra_pada", "tithi", "d9_lagna", "d10_lagna",
    ]  # fmt: skip
    nulls = [i for i in items if i["minutes_before"] is None or i["minutes_after"] is None]
    assert nulls, "some item should have no change within the 120-minute window"
    assert all(i["edge_before"] is False and i["edge_after"] is False for i in items)
    assert any(isinstance(i["minutes_after"], float) for i in items)


def test_sensitivity_edge_flag_at_range_start(client: TestClient) -> None:
    body = {"date": "1800-01-01", "time": "06:30", "utc_offset": "+00:00", **DELHI}
    r = client.post("/api/v1/kundli", json=body)
    assert r.status_code == 200, r.text
    items = r.json()["sensitivity"]
    flagged = [i for i in items if i["edge_before"]]
    assert flagged and all(i["minutes_before"] is None for i in flagged)


def test_vargas_subset_and_depth(client: TestClient) -> None:
    r = client.post(
        "/api/v1/kundli", json={**DELHI_2000, "vargas": [9, 1, 9], "dasha_depth": 1}
    ).json()
    assert list(r["vargas"]) == ["d1", "d9"]
    assert r["vimshottari"][0]["children"] == []
    assert client.post("/api/v1/kundli", json={**DELHI_2000, "vargas": [5]}).status_code == 422
    assert client.post("/api/v1/kundli", json={**DELHI_2000, "dasha_depth": 6}).status_code == 422


def test_panchang_ok(client: TestClient) -> None:
    body = {"date": "2024-03-25", "tz": "Asia/Kolkata", "lat": 25.3176, "lon": 82.9739}
    r = client.post("/api/v1/panchang", json=body)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["sunrise_local"].startswith("2024-03-25T05:5") and p["sunrise_local"].endswith(
        "+05:30"
    )
    assert p["sunset_utc"].endswith("Z")
    assert p["at_sunrise"]["tithi"]["key"] == "purnima"  # Holi, 2024-03-25
    assert p["at_sunrise"]["vaar"] == "soma"
    assert 1 <= p["at_sunrise"]["nakshatra"]["index"] <= 27
    assert client.post("/api/v1/panchang", json={**body, "tz": "No/Where"}).status_code == 422


INDIA_1947 = {"date": "1947-08-15", "time": "00:00", "tz": "Asia/Kolkata", **DELHI}


def _dasha(client: TestClient, **body: Any) -> Any:
    return client.post("/api/v1/dasha", json={"kundli": INDIA_1947, **body})


def _levels(period: dict[str, Any]) -> list[int]:
    out = [period["level"]]
    while period["children"]:
        period = period["children"][0]
        out.append(period["level"])
    return out


def test_dasha_subtree_depth5(client: TestClient) -> None:
    r = _dasha(client, scheme="vimshottari", maha_index=1, depth=5)
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["scheme"], d["maha_index"], d["path"]) == ("vimshottari", 1, [])
    period = d["period"]
    assert period["lord"] == "mercury" and _levels(period) == [1, 2, 3, 4, 5]
    kids = period["children"]
    assert len(kids) == 9 and kids[0]["start_utc"] == period["start_utc"]
    assert kids[-1]["end_utc"] == period["end_utc"]
    assert all(a["end_utc"] == b["start_utc"] for a, b in itertools.pairwise(kids))


def test_dasha_second_saturn_maha_is_addressable(client: TestClient) -> None:
    mahas = client.post("/api/v1/kundli", json=INDIA_1947).json()["vimshottari"]
    saturn = [i for i, m in enumerate(mahas) if m["lord"] == "saturn"]
    assert saturn == [0, 9]  # birth maha (partly elapsed) and the one 120 years on
    first = _dasha(client, scheme="vimshottari", maha_index=0, depth=2).json()["period"]
    second = _dasha(client, scheme="vimshottari", maha_index=9, depth=2).json()["period"]
    assert second["lord"] == "saturn"
    assert second["start_utc"] == mahas[9]["start_utc"] != first["start_utc"]
    assert second["end_utc"] == mahas[9]["end_utc"]
    assert second["children"][0]["lord"] == "saturn"
    assert second["children"][0]["start_utc"] == mahas[9]["start_utc"]
    assert second["children"][-1]["end_utc"] == mahas[9]["end_utc"]
    # an antar of the second Saturn maha, by path
    antar = second["children"][2]
    d = _dasha(client, scheme="vimshottari", maha_index=9, path=[antar["lord"]], depth=1).json()
    assert d["period"]["level"] == 2
    assert (d["period"]["start_utc"], d["period"]["end_utc"]) == (
        antar["start_utc"],
        antar["end_utc"],
    )


def test_dasha_later_dhanya_yogini_maha(client: TestClient) -> None:
    mahas = client.post("/api/v1/kundli", json=INDIA_1947).json()["yogini"]
    dhanya = [i for i, m in enumerate(mahas) if m["lord"] == "dhanya"]
    assert dhanya[:4] == [0, 8, 16, 24]
    r = _dasha(client, scheme="yogini", maha_index=16, depth=2)
    assert r.status_code == 200, r.text
    period = r.json()["period"]
    assert period["lord"] == "dhanya" and period["graha"] == "jupiter"
    assert period["start_utc"] == mahas[16]["start_utc"] != mahas[8]["start_utc"]
    assert len(period["children"]) == 8 and period["children"][0]["children"]
    deep = _dasha(client, scheme="yogini", maha_index=16, path=["siddha"], depth=1).json()
    assert deep["period"]["lord"] == "siddha" and deep["period"]["level"] == 2


def test_dasha_five_level_path_has_no_children(client: TestClient) -> None:
    r = _dasha(client, scheme="vimshottari", maha_index=1, path=["mercury"] * 4, depth=3)
    period = r.json()["period"]
    assert period["level"] == 5 and period["children"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"scheme": "vimshottari", "maha_index": 10},  # only 0-9 exist
        {"scheme": "yogini", "maha_index": 28},
        {"scheme": "vimshottari", "maha_index": -1},
        {"scheme": "vimshottari", "maha_index": 0, "path": ["pluto"]},
        {"scheme": "vimshottari", "maha_index": 0, "path": ["mangala"]},  # wrong scheme
        {"scheme": "yogini", "maha_index": 0, "path": ["jupiter"]},
        {"scheme": "vimshottari", "maha_index": 0, "path": ["ketu"] * 5},
        {"scheme": "other", "maha_index": 0},
        {"maha_index": 0},
        {"scheme": "vimshottari"},
        {"scheme": "vimshottari", "maha_index": 0, "lord": "saturn"},
    ],
)
def test_dasha_bad_request_422(client: TestClient, body: dict[str, Any]) -> None:
    assert _dasha(client, **body).status_code == 422


def test_dasha_error_locations(client: TestClient) -> None:
    loc = _dasha(client, scheme="vimshottari", maha_index=10).json()["detail"][0]["loc"]
    assert loc == ["body", "maha_index"]
    bad = {**INDIA_1947, "tz": "No/Where"}
    r = client.post("/api/v1/dasha", json={"kundli": bad, "scheme": "yogini", "maha_index": 0})
    assert r.json()["detail"][0]["loc"] == ["body", "kundli", "tz"]


def test_transit_ok(client: TestClient) -> None:
    body = {"datetime_utc": "2024-03-25T00:00:00Z"}
    r = client.post("/api/v1/transit", json=body)
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["datetime_utc"] == "2024-03-25T00:00:00Z"
    assert t["grahas"]["saturn"]["rashi_key"] == "kumbha"
    assert "natal" not in t
    with_natal = client.post("/api/v1/transit", json={**body, "natal": DELHI_2000}).json()
    sat = with_natal["grahas"]["saturn"]
    assert 1 <= sat["house_from_lagna"] <= 12 and 1 <= sat["house_from_moon"] <= 12
    assert with_natal["natal"]["lagna_basis"] == "ascendant"
    assert t["grahas"]["saturn"]["lon"] == sat["lon"]


def test_transit_needs_aware_datetime(client: TestClient) -> None:
    assert (
        client.post("/api/v1/transit", json={"datetime_utc": "2024-03-25T00:00:00"}).status_code
        == 422
    )
    r = client.post("/api/v1/transit", json={"datetime_utc": "1500-01-01T00:00:00Z"})
    assert r.status_code == 422


def test_places_varanasi(client: TestClient) -> None:
    r = client.get("/api/v1/places", params={"q": "varan"})
    assert r.status_code == 200
    first = r.json()[0]
    assert first["name"] == "Varanasi" and first["tz"] == "Asia/Kolkata"
    assert set(first) == {"name", "admin1", "country", "lat", "lon", "tz", "population"}


def test_places_accent_insensitive(client: TestClient) -> None:
    names = [p["name"] for p in client.get("/api/v1/places", params={"q": "sao paulo"}).json()]
    assert "São Paulo" in names


def test_places_validation(client: TestClient) -> None:
    assert client.get("/api/v1/places").status_code == 422
    assert client.get("/api/v1/places", params={"q": "a", "limit": 0}).status_code == 422
    assert len(client.get("/api/v1/places", params={"q": "a", "limit": 2}).json()) == 2


def test_health_reports_ephe(client: TestClient) -> None:
    for path in ("/health", "/api/v1/health"):
        r = client.get(path)
        assert r.status_code == 200
        h = r.json()
        assert h["status"] == "ok" and h["ephemeris"]["ok"] is True
        assert "path" not in h["ephemeris"]  # no server paths in responses
        assert h["ephemeris"]["files"] == ["sepl_18.se1", "semo_18.se1", "seas_18.se1"]
        assert h["ephemeris"]["missing"] == []
    v = client.get("/version").json()
    assert v["engine_version"] and v["api_version"] == "1"


def test_health_unavailable_when_files_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VEDIC_EPHE_PATH", str(tmp_path))
    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["ephemeris"]["missing"] == ["sepl_18.se1", "semo_18.se1", "seas_18.se1"]


def test_startup_refuses_without_ephemeris(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VEDIC_EPHE_PATH", str(tmp_path))
    with pytest.raises(EngineError, match="ephemeris files missing"), TestClient(main.app):
        pass


def test_engine_error_is_500_with_id_and_no_traceback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_a: Any, **_k: Any) -> None:
        raise EngineError("secret internal detail")

    monkeypatch.setattr(main, "build_kundli", boom)
    r = client.post("/api/v1/kundli", json=DELHI_2000)
    assert r.status_code == 500
    body = r.json()
    assert set(body) == {"detail", "error_id"} and len(body["error_id"]) == 12
    assert "secret" not in r.text and "Traceback" not in r.text


def test_unexpected_error_is_500_with_id(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("secret")

    monkeypatch.setattr(main, "build_kundli", boom)
    with TestClient(main.app, raise_server_exceptions=False) as c:
        r = c.post("/api/v1/kundli", json=DELHI_2000)
    assert r.status_code == 500 and "error_id" in r.json() and "secret" not in r.text


@pytest.mark.parametrize("path", ["/api/v1/analysis", "/api/v1/daily"])
def test_analysis_endpoints_are_post_only(client: TestClient, path: str) -> None:
    r = client.get(path)
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")


def test_root_serves_frontend(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Vedic Kundli" in r.text


def test_api_routes_take_precedence_over_the_frontend(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.headers["content-type"].startswith("application/json")
    assert client.get("/index.html").status_code == 200
    assert client.get("/no-such-file.js").status_code == 404


def test_frontend_dir_is_resolved_from_the_repo_not_the_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main.frontend_dir() == Path(main.__file__).resolve().parents[3] / "frontend"
    assert (main.frontend_dir() / "index.html").is_file()


def test_response_deterministic(client: TestClient) -> None:
    body = request_of(golden0())
    a = client.post("/api/v1/kundli", json=body)
    b = client.post("/api/v1/kundli", json=body)
    assert a.content == b.content


def test_openapi_snapshot(client: TestClient, request: pytest.FixtureRequest) -> None:
    current = json.dumps(client.get("/openapi.json").json(), indent=2, sort_keys=True) + "\n"
    if request.config.getoption("--update-snapshot"):
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(current)
    assert SNAPSHOT.read_text() == current, "API schema changed; rerun with --update-snapshot"


JS_DATE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:[0-9]{2}$"
)


def _all_local_strings(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for k, v in node.items():
            if k.endswith("_local") and isinstance(v, str):
                yield v
            else:
                yield from _all_local_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _all_local_strings(v)


@pytest.mark.parametrize(
    "zone,label",
    [
        ({"lmt": True}, "+05:09"),  # true offset +05:08:50.16
        ({"tz": "Asia/Kolkata"}, "+05:30"),
        ({"utc_offset": "+05:53:20"}, "+05:53"),
        ({"utc_offset": "-04:30"}, "-04:30"),
    ],
)
def test_local_strings_are_js_date_parseable(
    client: TestClient, zone: dict[str, Any], label: str
) -> None:
    body = {**{k: v for k, v in DELHI_2000.items() if k != "tz"}, **zone}
    k = client.post("/api/v1/kundli", json=body).json()
    locals_ = list(_all_local_strings(k))
    assert len(locals_) > 100
    assert all(JS_DATE.match(v) for v in locals_), [v for v in locals_ if not JS_DATE.match(v)][:3]
    assert k["meta"]["birth_local"].endswith(label)
    assert k["meta"]["utc_offset_seconds"] is not None


def test_utc_offset_seconds_follows_dst(client: TestClient) -> None:
    body = {
        "date": "2021-07-01",
        "time": "12:00",
        "tz": "America/New_York",
        "lat": 40.7,
        "lon": -74,
    }
    meta = client.post("/api/v1/kundli", json=body).json()["meta"]
    assert meta["utc_offset_seconds"] == -4 * 3600 and meta["birth_local"].endswith("-04:00")


def test_utc_offset_range_error_names_the_field(client: TestClient) -> None:
    r = client.post("/api/v1/kundli", json={**_zone_less(), "utc_offset": "+15:00"})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "utc_offset"]


def test_transit_error_locations(client: TestClient) -> None:
    r = client.post("/api/v1/transit", json={"datetime_utc": "1500-01-01T00:00:00Z"})
    assert r.json()["detail"][0]["loc"] == ["body", "datetime_utc"]
    natal = {**DELHI_2000, "tz": "No/Where"}
    r = client.post(
        "/api/v1/transit", json={"datetime_utc": "2024-01-01T00:00:00Z", "natal": natal}
    )
    assert r.json()["detail"][0]["loc"] == ["body", "natal", "tz"]


def test_transit_is_utc_only(client: TestClient) -> None:
    t = client.post("/api/v1/transit", json={"datetime_utc": "2024-03-25T05:30:00+05:30"}).json()
    assert t["datetime_utc"] == "2024-03-25T00:00:00Z"
    assert list(_all_local_strings(t)) == []


@pytest.mark.parametrize("method", ["get", "post", "put", "patch", "delete"])
@pytest.mark.parametrize("path", ["/api/nope", "/api/v1/nope", "/api/v2/kundli", "/api/"])
def test_unknown_api_path_is_json_404(client: TestClient, method: str, path: str) -> None:
    r = getattr(client, method)(path)
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
    assert "detail" in r.json()


# ---- response-shape snapshots (drift guard): key/type shape of the India 1947 chart


def shape(node: Any) -> Any:
    """Recursive key/type shape: dict -> {key: shape}, list -> [merged element shape]."""
    if isinstance(node, dict):
        return {k: shape(v) for k, v in sorted(node.items())}
    if isinstance(node, list):
        merged: Any = None
        for item in node:
            merged = _merge(merged, shape(item))
        return [merged]
    if node is None:
        return "null"
    return type(node).__name__


def _merge(a: Any, b: Any) -> Any:
    if a is None or a == b:
        return b
    if b is None:
        return a
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: _merge(a.get(k), b.get(k)) if k in a and k in b else a.get(k, b.get(k))
                for k in sorted(a.keys() | b.keys())}  # fmt: skip
    if isinstance(a, list) and isinstance(b, list):
        return [_merge(a[0], b[0])]
    if isinstance(a, str) and isinstance(b, str):
        return "|".join(sorted(set(a.split("|")) | set(b.split("|"))))
    return {"_union": sorted([json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True)])}


def _check_shape(name: str, body: Any, request: pytest.FixtureRequest) -> None:
    path = SNAPSHOT.parent / name
    current = json.dumps(shape(body), indent=2) + "\n"
    if request.config.getoption("--update-snapshot"):
        path.write_text(current)
    assert path.read_text() == current, f"{name} drifted; rerun with --update-snapshot if intended"


def test_kundli_shape_snapshot(client: TestClient, request: pytest.FixtureRequest) -> None:
    r = client.post("/api/v1/kundli", json=INDIA_1947)
    assert r.status_code == 200
    _check_shape("kundli_shape.json", r.json(), request)


def test_kundli_time_unknown_shape_snapshot(
    client: TestClient, request: pytest.FixtureRequest
) -> None:
    body = {k: v for k, v in INDIA_1947.items() if k != "time"}
    r = client.post("/api/v1/kundli", json={**body, "time_known": False})
    assert r.status_code == 200
    _check_shape("kundli_time_unknown_shape.json", r.json(), request)


# ---- /analysis and /daily (Task 5)

NOW_UTC = "2026-10-17T06:30:00Z"
_CERTAIN = re.compile(r"definitely|guarantee|100%|99%|certainly|surely|undoubtedly", re.IGNORECASE)


def _walk_statements(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        if "text_en" in node:
            yield node
        for v in node.values():
            yield from _walk_statements(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_statements(v)


@pytest.fixture(scope="module")
def analysis_body(client: TestClient) -> Any:
    r = client.post("/api/v1/analysis", json={**INDIA_1947, "now_utc": NOW_UTC})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def daily_body(client: TestClient) -> Any:
    r = client.post("/api/v1/daily", json={**INDIA_1947, "today": "2026-10-17"})
    assert r.status_code == 200, r.text
    return r.json()


def test_analysis_india(analysis_body: Any) -> None:
    b = analysis_body
    cur = b["periods"]["current"]
    assert (cur["maha"]["lord"], cur["antar"]["lord"]) == ("mars", "rahu")
    assert cur["pratyantar"]["judgement"]["nature"] in ("favourable", "mixed", "challenging")
    assert set(b["areas"]) == {"personality", "career", "income", "marriage", "health",
                               "wealth", "children", "education"}  # fmt: skip
    assert b["functional_roles"]["saturn"]["role"] == "yogakaraka"
    assert b["lucky"][0]["items"][0]["label_hi"]
    assert b["disclaimer_en"] == "Traditional Jyotish interpretation — guidance, not certainty."
    assert b["disclaimer_hi"]
    p = b["periods"]
    assert len(p["months"]) == 24 and len(p["best_windows"]) == 3
    assert len(p["challenging_windows"]) == 3
    assert p["now_utc"] == NOW_UTC and p["now_local"] == "2026-10-17T12:00:00+05:30"
    for item in p["timeline"]:
        assert item["why"] and item["ref"] and item["start_local"].endswith("+05:30")
    for s in _walk_statements(b):
        assert s["why"] and s["ref"], s
        assert not _CERTAIN.search(s["text_en"]), s


def test_analysis_is_deterministic(client: TestClient, analysis_body: Any) -> None:
    again = client.post("/api/v1/analysis", json={**INDIA_1947, "now_utc": NOW_UTC}).json()
    assert again == analysis_body


def test_analysis_gender(client: TestClient) -> None:
    body = {**INDIA_1947, "now_utc": NOW_UTC, "gender": "female"}
    r = client.post("/api/v1/analysis", json=body)
    assert r.status_code == 200 and r.json()["meta"]["gender"] == "female"
    r = client.post("/api/v1/analysis", json={**body, "gender": "other"})
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "gender"]


def test_analysis_now_out_of_dasha_span_is_422(client: TestClient) -> None:
    r = client.post("/api/v1/analysis", json={**INDIA_1947, "now_utc": "1900-01-01T00:00:00Z"})
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "now_utc"]


def test_daily_india(daily_body: Any) -> None:
    b = daily_body
    assert b["vaar"] == "shani" and b["vaar_lord"] == "saturn" and b["tz"] == "Asia/Kolkata"
    horas = b["horas"]
    assert len(horas) == 24 and horas[0]["lord"] == "saturn"
    assert (
        horas[0]["start_utc"] == b["sunrise_utc"] and horas[-1]["end_utc"] == b["next_sunrise_utc"]
    )
    assert horas[0]["start_local"].startswith("2026-10-17T06:2")
    for h in horas:
        assert set(h) >= {"lord", "start_utc", "start_local", "end_utc", "end_local",
                          "colour_en", "colour_hi", "favourable", "avoid", "why", "ref"}  # fmt: skip
    assert b["colour_today"]["graha"] == "saturn"
    assert b["body_language"] and b["decisions"]
    for s in _walk_statements(b):
        assert s["why"] and s["ref"], s


def test_daily_current_location(client: TestClient) -> None:
    body = {**INDIA_1947, "today": "2026-10-17", "current_lat": 25.2048,
            "current_lon": 55.2708, "current_tz": "Asia/Dubai"}  # fmt: skip
    r = client.post("/api/v1/daily", json=body)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["tz"] == "Asia/Dubai" and b["place"] == {"lat": 25.2048, "lon": 55.2708}
    assert b["horas"][0]["start_local"].endswith("+04:00")
    r = client.post("/api/v1/daily", json={**body, "current_tz": "Mars/Olympus"})
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "current_tz"]
    r = client.post("/api/v1/daily", json={**INDIA_1947, "today": "2026-10-17", "current_lat": 1.0})
    assert r.status_code == 422


def test_daily_time_unknown_still_gives_horas(client: TestClient, daily_body: Any) -> None:
    birth = {k: v for k, v in INDIA_1947.items() if k != "time"}
    r = client.post("/api/v1/daily", json={**birth, "time_known": False, "today": "2026-10-17"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert len(b["horas"]) == 24
    assert [h["lord"] for h in b["horas"]] == [h["lord"] for h in daily_body["horas"]]
    assert b["sunrise_utc"] == daily_body["sunrise_utc"]
    assert "Moon sign" in b["body_language"][0]["why"][0]


def test_analysis_shape_snapshot(analysis_body: Any, request: pytest.FixtureRequest) -> None:
    _check_shape("analysis_shape.json", analysis_body, request)


def test_daily_shape_snapshot(daily_body: Any, request: pytest.FixtureRequest) -> None:
    _check_shape("daily_shape.json", daily_body, request)


def test_analysis_time_unknown_shape_snapshot(
    client: TestClient, request: pytest.FixtureRequest
) -> None:
    birth = {k: v for k, v in INDIA_1947.items() if k != "time"}
    r = client.post("/api/v1/analysis", json={**birth, "time_known": False, "now_utc": NOW_UTC})
    assert r.status_code == 200, r.text
    _check_shape("analysis_time_unknown_shape.json", r.json(), request)


# ---- Task 5 fix round 1


def test_analysis_default_is_lean_and_full_mode_has_every_reason(
    client: TestClient, analysis_body: Any
) -> None:
    r = client.post("/api/v1/analysis", json={**INDIA_1947, "now_utc": NOW_UTC})
    # 100 KB is a budget (ruling U13), not a hard property of the data
    assert len(r.content) < 100_000, len(r.content)
    lean = analysis_body["periods"]
    for item in lean["timeline"]:
        j = item["judgement"]
        assert len(j["reasons"]) == min(3, j["reasons_total"])
        assert all(rid in lean["reasons"] for rid in j["reasons"])
    for m in lean["months"]:  # pointers into the timeline and transits
        ids = {i["id"] for i in lean["timeline"]} | {t["id"] for t in lean["transits"]}
        assert all(x["source"] in ids for x in m["reasons"])
    full = client.post(
        "/api/v1/analysis", json={**INDIA_1947, "now_utc": NOW_UTC, "detail": "full"}
    )
    assert full.status_code == 200 and len(full.content) > len(r.content)
    fp = full.json()["periods"]
    for small, item in zip(lean["timeline"], fp["timeline"], strict=True):
        j = item["judgement"]
        assert len(j["reasons"]) == j["reasons_total"] > 3
        deltas = sorted((abs(fp["reasons"][x]["delta"]) for x in j["reasons"]), reverse=True)
        kept = sorted((abs(lean["reasons"][x]["delta"]) for x in small["judgement"]["reasons"]),
                      reverse=True)  # fmt: skip
        assert kept == deltas[:3]
    for m in fp["months"]:
        assert all(x["why"] and x["ref"] for x in m["reasons"])
    bad = client.post("/api/v1/analysis", json={**INDIA_1947, "detail": "all"})
    assert bad.status_code == 422 and bad.json()["detail"][0]["loc"] == ["body", "detail"]


def test_analysis_labels_interpretive_weights(client: TestClient, analysis_body: Any) -> None:
    p = analysis_body["periods"]
    assert "interpretive" in p["scoring_note"]["en"] and p["scoring_note"]["hi"]
    assert "weights: interpretive" in p["scoring_note"]["ref"]
    assert all(t["ref"].endswith("weights: interpretive") for t in p["transits"])
    full = client.post(
        "/api/v1/analysis", json={**INDIA_1947, "now_utc": NOW_UTC, "detail": "full"}
    ).json()["periods"]
    for m in (*full["months"], *full["best_windows"], *full["challenging_windows"]):
        assert all(r["ref"].endswith("weights: interpretive") for r in m["reasons"])


@pytest.mark.parametrize(
    "extra",
    [
        {"current_tz": "Asia/Dubai"},
        {"current_lat": 25.2, "current_lon": 55.27},
        {"current_lon": 55.27, "current_tz": "Asia/Dubai"},
    ],
)
def test_daily_current_place_is_all_or_nothing(client: TestClient, extra: dict[str, Any]) -> None:
    r = client.post("/api/v1/daily", json={**INDIA_1947, "today": "2026-10-17", **extra})
    assert r.status_code == 422, r.text


def test_daily_polar_day_is_422_naming_the_date(client: TestClient) -> None:
    body = {**INDIA_1947, "today": "2026-05-15", "current_lat": 69.6492,
            "current_lon": 18.9553, "current_tz": "Europe/Oslo"}  # fmt: skip
    r = client.post("/api/v1/daily", json=body)
    assert r.status_code == 422
    d = r.json()["detail"][0]
    assert d["loc"] == ["body", "today"]
    assert "2026-05-16" in d["msg"] and "end 2026-05-15's horas" in d["msg"]


def test_daily_lmt_birth(client: TestClient) -> None:
    body = {k: v for k, v in INDIA_1947.items() if k != "tz"}
    r = client.post("/api/v1/daily", json={**body, "lmt": True, "today": "2026-10-17"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["tz"].startswith("UTC+05:08")  # LMT at 77.209 E
    assert b["horas"][0]["start_local"].endswith("+05:09") and b["vaar"] == "shani"


@pytest.mark.parametrize(
    ("today", "first", "last"),
    [("2026-03-29", "+01:00", "+01:00"), ("2026-10-24", "+01:00", "+00:00")],
)
def test_daily_london_dst_horas(client: TestClient, today: str, first: str, last: str) -> None:
    body = {**INDIA_1947, "today": today, "current_lat": 51.5074, "current_lon": -0.1278,
            "current_tz": "Europe/London"}  # fmt: skip
    r = client.post("/api/v1/daily", json=body)
    assert r.status_code == 200, r.text
    horas = r.json()["horas"]
    assert len(horas) == 24
    assert horas[0]["start_local"].startswith(today) and horas[0]["start_local"].endswith(first)
    assert horas[-1]["end_local"].endswith(last)
    for a, b in itertools.pairwise(horas):
        assert a["end_utc"] == b["start_utc"]


@pytest.mark.parametrize("detail", ["summary", "full"])
@pytest.mark.parametrize("time_known", [True, False])
def test_analysis_ids_resolve(client: TestClient, detail: str, time_known: bool) -> None:
    birth = (
        dict(INDIA_1947)
        if time_known
        else {**{k: v for k, v in INDIA_1947.items() if k != "time"}, "time_known": False}
    )
    r = client.post("/api/v1/analysis", json={**birth, "now_utc": NOW_UTC, "detail": detail})
    assert r.status_code == 200, r.text
    p = r.json()["periods"]
    reason_ids = set(p["reasons"])
    judgements = [c["judgement"] for c in p["current"].values()]
    judgements += [i["judgement"] for i in p["timeline"]]
    assert len(judgements) == 3 + len(p["timeline"])
    for j in judgements:
        assert j["reasons"] and set(j["reasons"]) <= reason_ids
    sources = {i["id"] for i in p["timeline"]} | {t["id"] for t in p["transits"]}
    assert len(sources) == len(p["timeline"]) + len(p["transits"])  # ids are unique
    for m in (*p["months"], *p["best_windows"], *p["challenging_windows"]):
        assert m["reasons"] and {x["source"] for x in m["reasons"]} <= sources
    assert {i["advice_key"] for i in p["timeline"]} <= set(p["advice"])


def test_config_test_hooks_follow_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(main.app) as c:
        monkeypatch.delenv("KUNDLI_TEST_HOOKS", raising=False)
        assert c.get("/api/v1/config").json() == {"test_hooks": False}
        monkeypatch.setenv("KUNDLI_TEST_HOOKS", "1")
        assert c.get("/api/v1/config").json() == {"test_hooks": True}


def test_422_caps_echoed_input_and_vargas_are_bounded() -> None:
    body = {"date": "1990-01-01", "time": "10:00", "lat": 1, "lon": 1}
    with TestClient(main.app) as c:
        r = c.post("/api/v1/kundli", json={**body, "utc_offset": "x" * 500})
        assert r.status_code == 422
        assert len(r.text) < 800 and "x" * 100 not in r.text
        r = c.post("/api/v1/kundli", json={**body, "tz": "Mars/" + "y" * 500})
        assert r.status_code == 422
        assert "y" * 100 not in r.text
        r = c.post("/api/v1/kundli", json={**body, "tz": "Asia/Kolkata", "vargas": [1] * 17})
        assert r.status_code == 422
        assert r.json()["detail"][0]["loc"] == ["body", "vargas"]
