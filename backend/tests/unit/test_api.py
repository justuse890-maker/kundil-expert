"""HTTP API (FastAPI TestClient): v1 endpoints, error mapping, snapshot, frontend mount."""

import itertools
import json
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
    assert meta["birth_local"] == "2000-01-01T12:00:00+05:08:50"
    assert meta["birth_utc"] == "2000-01-01T06:51:10Z"


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


def test_dasha_subtree_depth5(client: TestClient) -> None:
    body = {"kundli": request_of(golden0()), "path": ["jupiter"], "depth": 5}
    r = client.post("/api/v1/dasha", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["scheme"] == "vimshottari"
    period = d["period"]
    assert period["lord"] == "jupiter" and period["level"] == 1
    node = period
    levels = [node["level"]]
    while node["children"]:
        node = node["children"][0]
        levels.append(node["level"])
    assert levels == [1, 2, 3, 4, 5]
    assert len(period["children"]) == 9
    kids = period["children"]
    assert kids[0]["start_utc"] == period["start_utc"]
    assert all(a["end_utc"] == b["start_utc"] for a, b in itertools.pairwise(kids))


def test_dasha_five_level_path_has_no_children(client: TestClient) -> None:
    body = {"kundli": request_of(golden0()), "path": ["jupiter"] * 5, "depth": 3}
    period = client.post("/api/v1/dasha", json=body).json()["period"]
    assert period["level"] == 5 and period["children"] == []


def test_dasha_path_and_yogini(client: TestClient) -> None:
    k = request_of(golden0())
    first = client.post("/api/v1/kundli", json=k).json()["vimshottari"][0]
    antar = first["children"][1]
    path = [first["lord"], antar["lord"]]
    d = client.post("/api/v1/dasha", json={"kundli": k, "path": path, "depth": 1}).json()
    assert d["period"]["level"] == 2
    assert d["period"]["start_utc"] == antar["start_utc"]
    assert d["period"]["end_utc"] == antar["end_utc"]
    yog = client.post("/api/v1/dasha", json={"kundli": k, "path": ["mangala"], "depth": 2}).json()
    assert yog["scheme"] == "yogini"
    assert yog["period"]["graha"] == "moon" and yog["period"]["children"]


@pytest.mark.parametrize("path", [[], ["pluto"], ["jupiter", "mangala"], ["a"] * 6])
def test_dasha_bad_path_422(client: TestClient, path: list[str]) -> None:
    body = {"kundli": request_of(golden0()), "path": path, "depth": 1}
    assert client.post("/api/v1/dasha", json=body).status_code == 422


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


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("path", ["/api/v1/analysis", "/api/v1/daily"])
def test_placeholders_501(client: TestClient, method: str, path: str) -> None:
    r = getattr(client, method)(path)
    assert r.status_code == 501


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
