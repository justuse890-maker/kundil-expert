"""Browser tests of the UI against a live uvicorn (marker ``e2e``, excluded from the default run;
the cheap grep test below runs by default).

Run with: ``uv run playwright install chromium`` once, then ``uv run pytest -m e2e``.
"""

import re
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, expect, sync_playwright

REPO = Path(__file__).resolve().parents[3]
FRONTEND = REPO / "frontend"

# Functions that used to compute astronomy or interpretation in the browser.
REMOVED_FUNCTIONS = [
    "getAyanamsa", "toJD", "sunLongitude", "moonLongitude", "planetLongitude", "rahuLongitude",
    "calcAscendant", "computePositions", "calcPanchang", "calcVimshottariDasha", "calcManglik",
    "calcKaalSarpa", "calcSadeSati", "calcAshtakavarga", "getDignity", "isCombust", "navamsaSign",
    "isVargottama", "houseOf", "bhavaRashis", "generateLifeAnalysis", "getPersonalityAnalysis",
    "getCareerAnalysis", "getMarriageAnalysis", "getHealthAnalysis", "getWealthAnalysis",
    "getCurrentPeriodAnalysis", "getLuckyElements", "getColorGuidance", "getUpcomingAnalysis",
    "getDecisionGuidance", "getHouseReading",
]  # fmt: skip


def test_removed_client_functions_are_gone() -> None:
    """No removed function name survives anywhere under frontend/ (grep test)."""
    files = [p for p in FRONTEND.rglob("*") if p.is_file()]
    assert files, "frontend/ is empty"
    pattern = re.compile(r"\b(" + "|".join(REMOVED_FUNCTIONS) + r")\b")
    hits = [
        f"{p.relative_to(REPO)}: {m.group(0)}"
        for p in files
        for m in pattern.finditer(p.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert hits == []


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=REPO / "backend",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"{url}/api/v1/health", timeout=1):
                    break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("uvicorn did not start")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="module")
def page(base_url: str) -> Iterator[Page]:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        pg = browser.new_page()

        # Keep the test hermetic: the page links Google Fonts, which we never fetch.
        def stub_fonts(route: Route) -> None:
            route.fulfill(status=200, content_type="text/css", body="")

        pg.route(re.compile(r"https://fonts\.(googleapis|gstatic)\.com/.*"), stub_fonts)
        yield pg
        browser.close()


@pytest.mark.e2e
def test_india_1947_end_to_end(page: Page, base_url: str) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    # /analysis and /daily answer 501 for now; Chromium logs every non-2xx fetch as a console
    # error ("Failed to load resource"), which is the expected placeholder path, not a JS error.
    page.on(
        "console",
        lambda msg: (
            errors.append(msg.text)
            if msg.type == "error" and "status of 501" not in msg.text
            else None
        ),
    )

    page.goto(base_url + "/")
    page.fill("#name", "India 1947")
    page.fill("#dob", "1947-08-15")
    page.fill("#tob", "00:00")

    page.fill("#birthPlace", "New Delhi")
    page.locator("#placeList li").first.wait_for()
    page.locator("#placeList li", has_text="New Delhi").first.click()
    expect(page.locator("#tzName")).to_have_value("Asia/Kolkata")
    expect(page.locator("#lat")).not_to_have_value("")

    page.click("#submitBtn")

    expect(page.get_by_test_id("lagna")).to_have_text("Vrishabha")
    expect(page.get_by_test_id("nakshatra")).to_have_text("Pushya")
    expect(page.get_by_test_id("sensitivity-banner")).to_be_visible()
    assert page.locator("#overviewContent .house-table").inner_text().count("Pushya") >= 1

    page.click("#navDasha")
    expect(page.get_by_test_id("maha-row").first).to_contain_text("Saturn")

    page.click("#navDoshas")
    expect(page.locator("#doshasContent")).to_contain_text("Manglik Dosha")

    # Analysis endpoints return 501: every section shows the placeholder, never fake text.
    page.click("#navPredictions")
    sections = page.locator("#predictionsContent [data-analysis]")
    expect(sections.first).to_be_visible()
    count = sections.count()
    assert count >= 9
    for i in range(count):
        expect(sections.nth(i)).to_have_text("Detailed analysis is being prepared")
    expect(page.locator("#honesty")).to_have_text(
        "Traditional Jyotish interpretation — guidance, not certainty."
    )

    assert errors == []


@pytest.mark.e2e
def test_time_unknown_and_error_state(page: Page, base_url: str) -> None:
    posted: list[str] = []
    page.on("request", lambda r: posted.append(r.post_data or "") if "/kundli" in r.url else None)
    page.goto(base_url + "/")
    page.fill("#name", "Unknown Time")
    page.fill("#dob", "1990-01-01")
    page.check("#timeUnknown")
    expect(page.locator("#tob")).to_be_disabled()
    # Manual coordinates, no place picked: the advanced UTC offset is sent instead of a tz name.
    page.fill("#birthPlace", "Somewhere")
    page.fill("#lat", "28.6139")
    page.fill("#lon", "77.2090")
    # No place picked and no explicit offset: refused with a hint, never a silent IST default.
    page.click("#submitBtn")
    expect(page.locator("#placeHint")).to_be_visible()
    assert posted == []
    page.click("summary")
    page.check("#useOffset")
    page.click("#submitBtn")
    expect(page.get_by_test_id("sensitivity-banner")).to_contain_text("birth time unknown")
    assert '"time_known":false' in posted[0] and '"utc_offset":"+05:30"' in posted[0]
    assert '"time"' not in posted[0]

    page.goto(base_url + "/")
    page.fill("#name", "Bad Latitude")
    page.fill("#dob", "1990-01-01")
    page.fill("#tob", "10:00")
    page.fill("#birthPlace", "Nowhere")
    page.fill("#lat", "28.6139")
    page.fill("#lon", "77.2090")
    page.click("summary")
    page.check("#useOffset")
    page.select_option("#tz", "5.5")
    # Out-of-range latitude: the API answers 422 and the form shows it.
    page.fill("#lat", "95")
    page.click("#submitBtn")
    expect(page.locator("#formError")).to_contain_text("lat")


@pytest.mark.e2e
def test_no_horizontal_overflow_on_mobile(page: Page, base_url: str) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    try:
        page.goto(base_url + "/")
        page.fill("#name", "India 1947")
        page.fill("#dob", "1947-08-15")
        page.fill("#tob", "00:00")
        page.fill("#birthPlace", "New Delhi")
        page.locator("#placeList li", has_text="New Delhi").first.click()
        # Editing the text after picking clears the zone and shows the hint.
        page.fill("#birthPlace", "New Delhi ")
        expect(page.locator("#placeHint")).to_be_visible()
        page.fill("#birthPlace", "New Delhi")
        page.locator("#placeList li", has_text="New Delhi").first.click()
        expect(page.locator("#placeHint")).to_be_hidden()
        page.click("#submitBtn")
        expect(page.get_by_test_id("lagna")).to_have_text("Vrishabha")
        for section in ("overview", "houses", "dasha", "doshas", "predictions"):
            page.evaluate(f"showSection('{section}')")
            width = page.evaluate("document.documentElement.scrollWidth")
            assert width <= 390, f"{section}: scrollWidth {width}"
    finally:
        page.set_viewport_size({"width": 1280, "height": 720})
