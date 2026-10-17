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


def test_no_hardcoded_prediction_text_in_app_js() -> None:
    """All analysis text comes from the API: no long English sentence literals in app.js."""
    src = (FRONTEND / "app.js").read_text(encoding="utf-8")
    # Non-prediction UI copy that is allowed (labels, errors, form hints, static dosha facts).
    allowed = ("Pick a place", "Please fill", "Cannot reach", "Something went wrong", "Request failed",
               "Analysis is unavailable", "Saturn is not currently", "Planets are distributed",
               "Saturn's 7.5 year")  # fmt: skip
    literals = re.findall(r"'([^'\\\n]{50,})'|\"([^\"\\\n]{50,})\"", src)
    # A sentence: 8+ words, capitalised, ending in a full stop. (House topic lists are not sentences.)
    long_sentences = [
        t for t in (a or b for a, b in literals)
        if len(t.split()) >= 8 and t[0].isupper() and t.rstrip().endswith(".")
    ]  # fmt: skip
    offenders = [t for t in long_sentences if not t.startswith(allowed)]
    assert offenders == []
    # The old canned analysis wording must be gone.
    for phrase in ("being prepared", "you will", "Jupiter in", "tends to"):
        assert phrase not in src


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
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    # ?now= is forwarded as now_utc (test determinism only).
    page.goto(base_url + "/?now=2026-10-17T06:30:00Z")
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

    page.click("#navPredictions")
    expect(page.locator("#predictionsContent [data-area]").first).to_be_visible()
    areas = [
        "personality",
        "career",
        "income",
        "marriage",
        "health",
        "wealth",
        "children",
        "education",
    ]
    for key in areas:
        sec = page.locator(f'#predictionsContent [data-area="{key}"]')
        expect(sec.locator(".score-bar")).to_be_visible()
        assert sec.locator(".life-item").count() >= 1
        assert sec.locator(".ref-badge").count() >= 1
    career = page.locator('#predictionsContent [data-area="career"]')
    expect(career.locator(".chip", has_text="10th lord Saturn").first).to_be_visible()
    assert page.locator('[data-testid="income-sources"] .life-item').count() >= 1
    lucky = page.locator(
        '[data-analysis="Lucky Elements"], .result-card:has-text("Lucky Elements")'
    )
    for kind in ("Colour", "Gemstone", "Day", "Number", "Direction", "Deity", "Metal"):
        expect(lucky.first.locator(".data-label", has_text=kind).first).to_be_visible()
    expect(lucky.first).to_contain_text("traditional association")

    cur = page.locator('[data-testid="current-period"]')
    expect(cur.get_by_test_id("period-path")).to_contain_text("Mars › Rahu")
    assert cur.locator(".period-level").count() == 3
    assert cur.locator(".period-level .reason").count() >= 3
    assert cur.locator(".period-level .advice").count() == 3

    months = page.locator('[data-testid="month-strip"] button.month')
    assert months.count() == 24
    natures = {months.nth(i).get_attribute("data-nature") for i in range(24)}
    assert natures <= {"favourable", "mixed", "challenging"}
    expect(page.get_by_test_id("scoring-note")).to_contain_text("interpretive")
    months.nth(5).click()
    expect(months.nth(5)).to_have_class(re.compile(r"\bsel\b"))
    expect(page.get_by_test_id("month-detail").locator(".reason").first).to_be_visible()
    timeline = page.get_by_test_id("timeline-card")
    assert timeline.locator(".dosha-card.safe").count() == 3
    assert timeline.locator(".dosha-card.danger").count() == 3

    hora_rows = page.locator('[data-testid="hora-table"] tbody tr')
    assert hora_rows.count() == 24
    assert page.locator("tr.hora-now").count() == 1
    expect(page.locator("tr.hora-now")).to_contain_text("Now")
    assert page.locator('[data-testid="hora-table"] .badge.green').count() >= 1
    assert page.locator('[data-testid="hora-table"] .badge.red').count() >= 1
    expect(page.locator('[data-testid="today-card"]')).to_contain_text("Saturday")
    today = page.locator('.result-card:has-text("Colour & Body Language")').first
    expect(today).to_contain_text("Colour today")
    expect(today).to_contain_text("Colour to avoid")
    expect(page.locator('.result-card:has-text("Decision Guidance") .chip').first).to_be_visible()

    # Hindi toggle swaps API text (text_hi) in place.
    page.click("#langBtn")
    expect(career.locator(".life-item-desc").first).to_contain_text("दशमेश")
    page.click("#langBtn")

    expect(page.locator("#honesty")).to_be_visible()
    expect(page.locator("#honesty")).to_have_text(
        "Traditional Jyotish interpretation — guidance, not certainty."
    )

    # Dasha tab shows the same current period.
    page.click("#navDasha")
    expect(page.locator("#periodCurrent")).to_contain_text("Mars › Rahu")

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
    page.click("#navPredictions")
    expect(page.locator(".chandra-note").first).to_be_visible()

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
        page.goto(base_url + "/?now=2026-10-17T06:30:00Z")
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
        page.evaluate("showSection('predictions')")
        expect(page.locator('[data-testid="hora-table"]')).to_be_visible()
        page.get_by_test_id("month-strip").locator("button").nth(3).click()
        for section in ("overview", "houses", "dasha", "doshas", "predictions"):
            page.evaluate(f"showSection('{section}')")
            width = page.evaluate("document.documentElement.scrollWidth")
            assert width <= 390, f"{section}: scrollWidth {width}"
    finally:
        page.set_viewport_size({"width": 1280, "height": 720})
