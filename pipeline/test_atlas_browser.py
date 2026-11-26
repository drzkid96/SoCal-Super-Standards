"""Exercise the published municipal map, its permalinks and its agency links in Chrome."""
import json
import os
from collections import Counter, defaultdict
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import parse_qs, urlsplit

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait


DIST = Path(__file__).resolve().parents[1] / "dist"
BASE = "/SoCal-Super-Standards/"
CITY_COUNTS = {"025": 7, "037": 88, "059": 34, "065": 28, "071": 24, "073": 18, "111": 10}
PASADENA = "0656000"
ANAHEIM = "0602000"
HOLTVILLE = "0634246"


@contextmanager
def serve_build():
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    with TemporaryDirectory() as root:
        (Path(root) / BASE.strip("/")).symlink_to(DIST, target_is_directory=True)
        handler = partial(QuietHandler, directory=root)
        with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield f"http://127.0.0.1:{server.server_port}{BASE}"
            finally:
                server.shutdown()
                thread.join()


def control(browser, name):
    return Select(browser.find_element(By.ID, "atlas-" + name))


def choices(browser, name):
    return set(browser.execute_script(
        "return Array.from(document.getElementById(arguments[0])?.options ?? [], o => o.value).filter(Boolean)",
        "atlas-" + name,
    ))


def selected_query(browser, field):
    return parse_qs(urlsplit(browser.current_url).query).get(field, [None])[0]


def municipal_result(browser, city, expected_path):
    def selected(driver):
        if selected_query(driver, "city") != city or control(driver, "city").first_selected_option.get_attribute("value") != city:
            return False
        links = driver.find_elements(By.CSS_SELECTOR, "#atlas-context a")
        return links and urlsplit(links[0].get_attribute("href")).path == BASE + expected_path

    WebDriverWait(browser, 10).until(selected, f"Expected {city} and first reference {expected_path}")


def check_indexed_municipalities(browser, county):
    profiles = json.loads((DIST / "api/v2/profiles.json").read_text())
    authorities = defaultdict(set)
    for agency in profiles.values():
        if agency["county"] == county and agency["place"]:
            authorities[agency["place"]].add(agency["home"])
    for city, expected in authorities.items():
        control(browser, "city").select_by_value(city)

        def shows_issuers(driver):
            paths = driver.execute_script(
                "return Array.from(document.querySelectorAll('#atlas-context a'), a => a.pathname)"
            )
            return selected_query(driver, "city") == city and paths and paths[0] in expected and expected.issubset(paths)

        WebDriverWait(browser, 10).until(shows_issuers, f"City {city} must lead with its own issuers: {expected}")


def click_city_shape(browser, city):
    # A shape's bounding-box centre can fall outside a multipart city or inside a hole.
    # Hit-test the rendered SVG, then send an actual pointer click through Chrome.
    browser.execute_script(
        "document.getElementById('atlas-map').scrollIntoView({block:'center', behavior:'instant'})"
    )
    point = WebDriverWait(browser, 10).until(lambda driver: driver.execute_script("""
        const shape = document.querySelector('#atlas-map path[data-city="' + arguments[0] + '"]');
        if (!shape || document.querySelector('.leaflet-zoom-anim')) return null;
        const box = shape.getBoundingClientRect();
        const map = document.getElementById('atlas-map').getBoundingClientRect();
        const left = Math.max(box.left, map.left, 0), right = Math.min(box.right, map.right, innerWidth);
        const top = Math.max(box.top, map.top, 0), bottom = Math.min(box.bottom, map.bottom, innerHeight);
        for (let row = 0; row < 15; row++) {
          for (let col = 0; col < 15; col++) {
            const x = left + (right - left) * (col + 0.5) / 15;
            const y = top + (bottom - top) * (row + 0.5) / 15;
            if (document.elementFromPoint(x, y) === shape) return {x, y};
          }
        }
        return null;
    """, city), f"Could not click a visible municipal boundary for {city}")
    for event in ("mousePressed", "mouseReleased"):
        browser.execute_cdp_cmd("Input.dispatchMouseEvent", {
            "type": event, "button": "left", "clickCount": 1, **point,
        })


def run(browser, base):
    wait = WebDriverWait(browser, 10)
    places = json.loads((DIST / "api/v2/places.json").read_text())
    cities = [p for p in places if p["kind"] == "city"]
    assert Counter(p["county"] for p in cities) == CITY_COUNTS

    # Represent a network where remote imagery and optional street databases are unavailable.
    browser.execute_cdp_cmd("Network.enable", {})
    browser.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": True})
    unavailable = ["*tile.openstreetmap.org/*", "*basemap.nationalmap.gov/*", "*/api/v2/db/*"]
    browser.execute_cdp_cmd("Network.setBlockedURLs", {"urls": unavailable})
    browser.set_window_size(1600, 950)
    browser.get(base)
    map_entry = next(a for a in browser.find_elements(By.CSS_SELECTOR, "main a[href]")
                     if a.get_attribute("href") == base + "map/" and a.is_displayed())
    assert "project map" not in map_entry.text.lower()
    map_entry.click()
    all_cities = {p["id"] for p in cities}
    wait.until(lambda d: choices(d, "city") == all_cities, "209 cities on the regional landing page")
    assert choices(browser, "county") == set(CITY_COUNTS)
    assert "municipal" in browser.find_element(By.TAG_NAME, "h1").text.lower()
    assert control(browser, "basemap").first_selected_option.get_attribute("value") == "local"
    wait.until(lambda d: set(d.execute_script(
        "return Array.from(document.querySelectorAll('#atlas-map path[data-city]'), p => p.dataset.city)"
    )) == all_cities, "All 209 cities have clickable boundaries on the regional map")
    assert not browser.find_elements(By.CSS_SELECTOR, "#atlas-map img.leaflet-tile")
    assert not browser.find_element(By.ID, "atlas-highways").is_selected()
    assert not browser.find_element(By.ID, "atlas-stops").is_selected()

    for county in CITY_COUNTS:
        control(browser, "county").select_by_value(county)
        expected = {p["id"] for p in cities if p["county"] == county}
        wait.until(lambda d: choices(d, "city") == expected, f"Municipal selection list for {county}")
        check_indexed_municipalities(browser, county)
    control(browser, "county").select_by_value("059")
    click_city_shape(browser, ANAHEIM)
    municipal_result(browser, ANAHEIM, "regions/anaheim/")
    browser.refresh()
    municipal_result(browser, ANAHEIM, "regions/anaheim/")

    control(browser, "county").select_by_value("037")
    control(browser, "city").select_by_value(PASADENA)
    municipal_result(browser, PASADENA, "regions/pasadena/")
    control(browser, "city").select_by_value("0608954")
    municipal_result(browser, "0608954", "regions/burbank/")
    browser.back()
    municipal_result(browser, PASADENA, "regions/pasadena/")
    browser.forward()
    municipal_result(browser, "0608954", "regions/burbank/")

    # Emulate a real 390 CSS-pixel device, including mobile viewport handling.
    browser.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True,
    })
    browser.get(base + "map/?city=" + PASADENA)
    municipal_result(browser, PASADENA, "regions/pasadena/")
    assert browser.execute_script("return innerWidth === 390 && document.documentElement.scrollWidth <= 391")
    first_link_y = browser.find_element(By.CSS_SELECTOR, "#atlas-context a").rect["y"]
    assert first_link_y < 844, f"First municipal reference starts at {first_link_y}px on mobile"
    for name in ("county", "city"):
        box = browser.find_element(By.ID, "atlas-" + name).rect
        assert box["width"] > 60 and box["x"] >= 0 and box["x"] + box["width"] <= 391, (name, box)
    browser.find_element(By.CSS_SELECTOR, "#atlas-context a").click()
    wait.until(lambda d: urlsplit(d.current_url).path == BASE + "regions/pasadena/")
    assert "Pasadena" in browser.find_element(By.TAG_NAME, "h1").text
    browser.back()
    municipal_result(browser, PASADENA, "regions/pasadena/")

    browser.get(base + "map/?city=" + HOLTVILLE)
    report = wait.until(lambda d: d.find_element(By.ID, "atlas-context").text or False)
    assert control(browser, "city").first_selected_option.get_attribute("value") == HOLTVILLE
    assert "Holtville" in browser.find_element(By.ID, "atlas-summary").text
    assert any(word in report.lower() for word in ("not indexed", "no indexed", "no city", "not yet", "no municipal")), report
    county_link = browser.find_element(By.CSS_SELECTOR, '#atlas-context a[href*="/regions/imperial-county"]')
    assert county_link.is_displayed()

    # A failed geometry request must leave the text index and its standards links usable.
    browser.execute_cdp_cmd("Network.setBlockedURLs", {
        "urls": unavailable + ["*/api/v2/boundaries/*", "*/api/v2/municipalities.geojson"],
    })
    browser.get(base + "map/?city=" + ANAHEIM)
    municipal_result(browser, ANAHEIM, "regions/anaheim/")
    browser.execute_cdp_cmd("Network.setBlockedURLs", {"urls": unavailable + ["*/vendor/atlas/leaflet.js"]})
    browser.get(base + "map/?city=" + PASADENA)
    municipal_result(browser, PASADENA, "regions/pasadena/")
    assert not browser.find_elements(By.CSS_SELECTOR, "#atlas-map .leaflet-pane")

    # The optional intersection inspector still resolves a real local street pair and its transit context.
    browser.execute_cdp_cmd("Network.setBlockedURLs", {"urls": unavailable[:2]})
    browser.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
    browser.get(base + "map/")
    wait.until(lambda d: choices(d, "city") == all_cities)
    browser.find_element(By.CSS_SELECTOR, "#atlas-inspector > summary").click()
    field = browser.find_element(By.ID, "atlas-query")
    field.send_keys("Holly St", Keys.ENTER)
    wait.until(lambda d: d.find_element(By.ID, "atlas-results").text.strip(), "Street search from all counties must respond")
    field.clear()
    field.send_keys("Ventura", Keys.ENTER)
    wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "#atlas-results li button") or selected_query(d, "city"))
    if not selected_query(browser, "city"):
        browser.find_element(By.CSS_SELECTOR, "#atlas-results li button").click()
    wait.until(lambda d: selected_query(d, "city") == "0665042", "Ventura resolves to its municipality")

    browser.get(base + "map/?city=" + PASADENA + "&topic=crosswalks")
    municipal_result(browser, PASADENA, "regions/pasadena/")
    assert control(browser, "topic").first_selected_option.get_attribute("value") == "crosswalks"
    wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, '#atlas-context a[href*="s-709/"]'))
    browser.find_element(By.CSS_SELECTOR, "#atlas-inspector > summary").click()
    browser.find_element(By.ID, "atlas-query").send_keys("Holly St & Arroyo Pkwy, Pasadena", Keys.ENTER)
    result = wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "#atlas-results li button") or False)[0]
    assert "Holly" in result.text and "Arroyo" in result.text and "Pasadena" in result.text
    result.click()
    wait.until(lambda d: "Stops and operators" in d.find_element(By.ID, "atlas-context").text)
    assert "Pasadena" in browser.find_element(By.ID, "atlas-summary").text
    assert "ownership" in browser.find_element(By.ID, "atlas-context").text.lower()
    records = browser.find_elements(By.XPATH, '//section[h3[.="Local street records"]]//div[contains(@class,"atlas-record")]')
    for road, classification in (("N ARROYO PKWY", "Primary Street"), ("E HOLLY ST", "Secondary Street")):
        assert any(road in record.text.upper() and classification in record.text and "Street inventory" in record.text
                   for record in records), (road, [record.text for record in records])
    assert abs(float(selected_query(browser, "lat")) - 34.14764) < 0.001
    assert abs(float(selected_query(browser, "lon")) + 118.14765) < 0.001
    browser.get(base + "map/?agency=pasadena&city=" + PASADENA)
    municipal_result(browser, PASADENA, "regions/pasadena/")
    assert choices(browser, "city") == {PASADENA}
    assert choices(browser, "county") == {"037"}
    assert not browser.find_elements(By.CSS_SELECTOR, '#atlas-context a[href*="/regions/ladot/"]')

    # The homepage form and directory are static HTML; the agency directory serves script-free clients.
    browser.execute_cdp_cmd("Emulation.setScriptExecutionDisabled", {"value": True})
    browser.get(base)
    picker = browser.find_element(By.CSS_SELECTOR, 'form select[name="city"]')
    assert len(picker.find_elements(By.TAG_NAME, "optgroup")) == 7
    assert len(picker.find_elements(By.CSS_SELECTOR, 'option:not([value=""])')) == 209
    Select(picker).select_by_value(PASADENA)
    picker.find_element(By.XPATH, "ancestor::form").find_element(By.CSS_SELECTOR, '[type="submit"],button').click()
    wait.until(lambda d: urlsplit(d.current_url).path == BASE + "map/" and selected_query(d, "city") == PASADENA)
    browser.find_element(By.CSS_SELECTOR, 'noscript a[href$="/regions/"]').click()
    assert len(browser.find_elements(By.CSS_SELECTOR, 'li[id^="city-"]')) == 209
    city_entry = browser.find_element(By.ID, "city-" + PASADENA)
    assert city_entry.find_elements(By.CSS_SELECTOR, 'a[href$="/regions/pasadena/"]')
    print("Verified seven county filters, 209 cities, all indexed municipal issuers, polygon selection, "
          "mobile layout, share URLs, topic links, history, blocked map data, intersection lookup and script-free browsing.")


if __name__ == "__main__":
    options = webdriver.ChromeOptions()
    for flag in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage"):
        options.add_argument(flag)
    if os.environ.get("CHROME_BIN"):
        options.binary_location = os.environ["CHROME_BIN"]
    with serve_build() as site, webdriver.Chrome(options=options) as browser:
        run(browser, site)
