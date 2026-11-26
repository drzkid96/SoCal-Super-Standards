"""Check navigation and reference access on phone, desktop and wide desktop."""
import json
import os
from urllib.parse import urlencode, urlsplit

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait

from test_atlas_browser import BASE, DIST, serve_build


PAGES = {
    "": "main form select[name=city]",
    "map/": "#atlas-city",
    "transit/omnitrans/": ".operator-book",
    "ca-mutcd/4i/": ".prov",
    "signs/r1-1/": ".sdetail",
    "details/ladot/mpp-531-s-481-0/": "#sheet-1",
    "regions/pasadena/": ".authority-books a",
    "topics/bikeways/": "main",
}


def verify_header(driver, page, scope=None):
    driver.get(page)
    for width in (320, 390, 768, 1440, 1920):
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width < 800,
        })
        driver.execute_async_script("document.fonts.ready.then(() => requestAnimationFrame(arguments[0]))")
        overlaps = driver.execute_script("""
            const selectors = ['header .site-title', 'header nav details > summary',
                'header .sss-search-link', 'header .settings-menu > summary', 'button.sl-menu-button'];
            const controls = selectors.map(s => [s, document.querySelector(s)?.getBoundingClientRect()])
                .filter(([,r]) => r && r.width && r.height);
            const failures = [];
            for (let i = 0; i < controls.length; i++) {
                const [name, a] = controls[i];
                for (const [other, b] of controls.slice(i+1)) {
                    if (Math.min(a.right,b.right)-Math.max(a.left,b.left)>1 &&
                        Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1) failures.push([name, other]);
                }
            }
            return failures;
        """)
        assert not overlaps, (width, overlaps)
        if scope:
            label = driver.find_element(By.CSS_SELECTOR, "[data-workspace-name]")
            assert label.text == scope and label.rect["width"] > 20, (width, scope)


def verify_layout(driver, base):
    wait = WebDriverWait(driver, 10)
    for width, height in ((1440, 900), (1920, 1080), (390, 844)):
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": height, "deviceScaleFactor": 1, "mobile": width < 500,
        })
        for route, selector in PAGES.items():
            driver.get(base + route)
            wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, selector), f"Missing reference on {route}")
            driver.execute_async_script("document.fonts.ready.then(arguments[0])")
            actual_width = driver.execute_script("return document.documentElement.scrollWidth")
            assert actual_width <= width + 1, (route, width, actual_width)
            headings = driver.find_elements(By.TAG_NAME, "h1")
            assert len(headings) == 1 and headings[0].is_displayed(), (route, width)
            assert urlsplit(driver.current_url).path == urlsplit(base + route).path


def verify_sign_routes(driver, base):
    wait = WebDriverWait(driver, 10)
    driver.get(base + "signs/")
    driver.find_element(By.CSS_SELECTOR, "#sign-filter-options > summary").click()
    origin = Select(driver.find_element(By.ID, "sorigin"))
    assert {"cad", "plan", "mod"} <= {item.get_attribute("value") for item in origin.options}
    origin.select_by_value("mod")
    driver.find_element(By.ID, "sq").send_keys("R10-15")
    modified_url = base + "signs/r10-15/#plan-r10-15-mod"
    modified = wait.until(lambda d: next((a for a in d.find_elements(By.CSS_SELECTOR, ".scard:not([hidden])")
                                         if a.get_attribute("href") == modified_url and a.is_displayed()), False))
    modified.click()
    wait.until(lambda d: d.current_url == modified_url)
    assert "MOD" in driver.find_element(By.ID, "plan-r10-15-mod").text.upper()
    face = driver.find_element(By.CSS_SELECTOR, 'figure img[src$="/plan-examples/sign-8.webp"]')
    driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", face)
    wait.until(lambda d: face.get_property("naturalWidth") > 0)
    source_link = driver.find_element(By.CSS_SELECTOR, 'main a[href$="#cad-geo-r10-15-mod"]')
    driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", source_link)
    source_link.click()
    wait.until(lambda d: urlsplit(d.current_url).fragment == "cad-geo-r10-15-mod")
    assert driver.find_element(By.ID, "cad-geo-r10-15-mod").is_displayed()
    driver.back()
    wait.until(lambda d: d.current_url == modified_url)
    driver.back()
    wait.until(lambda d: urlsplit(d.current_url).path == urlsplit(base + "signs/").path)
    assert Select(driver.find_element(By.ID, "sorigin")).first_selected_option.get_attribute("value") == "mod"
    assert driver.find_element(By.ID, "sq").get_property("value") == "R10-15"

    cases = [
        ("R10-15", "signs/r10-15/"),
        ("R10-15(MOD)", "signs/r10-15/#plan-r10-15-mod"),
        ("OM4-3(CA)", "signs/plan-om4-3ca/"),
    ]
    for query, path in cases:
        driver.get(base + "search/?" + urlencode({"q": query}))
        first = wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "#standards-results li a") or False)[0]
        assert first.get_attribute("href") == base + path, (query, first.text, first.get_attribute("href"))
        first.click()
        wait.until(lambda d: d.current_url == base + path)
        if "#" in path:
            assert driver.find_element(By.ID, path.split("#")[1]).is_displayed()
        else:
            assert driver.find_element(By.TAG_NAME, "h1").is_displayed()


def verify_menus(driver, base):
    wait = WebDriverWait(driver, 10)
    driver.get(base + "ca-mutcd/4i/")
    assert len(driver.find_elements(By.CSS_SELECTOR, 'main nav[aria-label="Breadcrumb"]')) == 1
    navigate = driver.find_element(By.CSS_SELECTOR, "main details.page-navigation > summary")
    navigate.send_keys(Keys.ENTER)
    next_page = driver.find_element(By.CSS_SELECTOR, "main .page-navigation a[rel=next]").get_attribute("href")
    navigate.send_keys(Keys.ENTER)
    footer_next = driver.find_element(By.CSS_SELECTOR, "main footer a[rel=next]")
    assert footer_next.get_attribute("href") == next_page
    footer_next.send_keys(Keys.ENTER)
    wait.until(lambda d: d.current_url == next_page)
    browse = driver.find_element(By.CSS_SELECTOR, "header nav details > summary")
    driver.find_element(By.CSS_SELECTOR, "header .site-title").send_keys(Keys.TAB)
    assert driver.switch_to.active_element == browse
    browse.send_keys(Keys.TAB)
    search = driver.switch_to.active_element
    assert search.get_attribute("aria-label") == "Search all standards"
    search.send_keys(Keys.TAB)
    assert driver.switch_to.active_element == driver.find_element(By.CSS_SELECTOR, "header .settings-menu > summary")
    browse.send_keys(Keys.ENTER)
    catalog = wait.until(lambda d: next((a for a in d.find_elements(By.CSS_SELECTOR, "header nav details a")
                                        if a.get_attribute("href") == base + "signs/" and a.is_displayed()), False))
    box = catalog.rect
    assert 0 <= box["x"] and box["x"] + box["width"] <= 391, box
    catalog.send_keys(Keys.ENTER)
    wait.until(lambda d: d.current_url == base + "signs/")
    settings = driver.find_element(By.CSS_SELECTOR, "header .settings-menu > summary")
    settings.send_keys(Keys.ENTER)
    preference = driver.find_element(By.CSS_SELECTOR, 'header select[data-pref="width"]')
    Select(preference).select_by_value("wide")
    driver.refresh()
    wait.until(lambda d: d.find_element(By.TAG_NAME, "html").get_attribute("data-readerwidth") == "wide")
    driver.find_element(By.CSS_SELECTOR, "header .settings-menu > summary").send_keys(Keys.ENTER)
    Select(driver.find_element(By.CSS_SELECTOR, 'header select[data-pref="width"]')).select_by_value("auto")
    Select(driver.find_element(By.ID, "agency-mode")).select_by_value("pasadena")
    wait.until(lambda d: urlsplit(d.current_url).path == urlsplit(base + "regions/pasadena/").path)
    assert "Pasadena" in driver.find_element(By.CSS_SELECTOR, "[data-workspace-name]").text


def verify_cad_faces(driver, base):
    records = {r["key"]: r for r in json.loads((DIST / "data/plan-signs.json").read_text())}
    wait = WebDriverWait(driver, 10)
    for key in ("R61-19CA-MOD-LEFT", "R61-19CA-MOD-RIGHT", "R61-34CA-MOD", "W16-MOD"):
        record = records[key]
        assert record["art"], f"Missing verified CAD face for {key}"
        driver.get(base + record["url"].removeprefix(BASE))
        image = driver.find_element(By.CSS_SELECTOR, f'figure img[src$="{record["art"][0]["image"]}"]')
        driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", image)
        wait.until(lambda d: image.get_property("naturalWidth") > 0, f"CAD face failed to render for {key}")
        assert image.is_displayed()
        caption = image.find_element(By.XPATH, "ancestor::figure/figcaption")
        assert caption.find_elements(By.CSS_SELECTOR, 'a[href*="/plan-reference/"]'), (key, caption.text)


if __name__ == "__main__":
    options = webdriver.ChromeOptions()
    for flag in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage"):
        options.add_argument(flag)
    if os.environ.get("CHROME_BIN"):
        options.binary_location = os.environ["CHROME_BIN"]
    with serve_build() as origin, webdriver.Chrome(options=options) as browser:
        verify_header(browser, origin + "ca-mutcd/4i/")
        verify_layout(browser, origin)
        verify_sign_routes(browser, origin)
        verify_cad_faces(browser, origin)
        verify_menus(browser, origin)
        verify_header(browser, origin + "details/pasadena/pasadena-std-plans-s-709/", "Pasadena")
    print("Verified reference navigation at 390, 1440 and 1920 pixels.")
