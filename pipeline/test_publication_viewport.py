"""Exercise the reading pane, page actions and zoom on a real STEP source page."""
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

from test_atlas_browser import serve_build


def verify(driver, origin):
    def viewport(width, height, mobile=False):
        driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': mobile,
        })

    def geometry():
        driver.execute_async_script('const done=arguments[0]; requestAnimationFrame(()=>requestAnimationFrame(done))')
        return driver.execute_script("""
            const pane=document.querySelector('.publication-window');
            const actions=document.querySelector('.publication .document-actions');
            return {height:pane.getBoundingClientRect().height,
                    bottom:actions.getBoundingClientRect().bottom,
                    overflow:getComputedStyle(pane).overflowY,
                    scrollHeight:pane.scrollHeight};
        """)

    viewport(1961, 1264)
    driver.get(origin + 'fhwa/step-uncontrolled-crossings/#p11')
    WebDriverWait(driver, 15).until(lambda _: driver.find_element(By.CSS_SELECTOR, '.publication-paper').text)
    desktop = geometry()
    assert desktop['height'] > 700 and 0 <= 1264 - desktop['bottom'] < 32, desktop
    zoom = Select(driver.find_element(By.CSS_SELECTOR, '[aria-label="Source page zoom"]'))
    zoom.select_by_visible_text('200%')
    enlarged = geometry()
    assert abs(enlarged['height'] - desktop['height']) < 2
    assert enlarged['scrollHeight'] > desktop['scrollHeight']
    viewport(1366, 768)
    laptop = geometry()
    assert laptop['height'] > 280 and 0 <= 768 - laptop['bottom'] < 32, laptop
    viewport(390, 844, True)
    phone = geometry()
    assert phone['overflow'] == 'visible' and 0 < phone['bottom'] <= 845, phone
    viewport(1024, 490)
    assert geometry()['overflow'] == 'visible'


if __name__ == '__main__':
    options = webdriver.ChromeOptions()
    for flag in ('--headless=new', '--no-sandbox', '--disable-dev-shm-usage'):
        options.add_argument(flag)
    if os.environ.get('CHROME_BIN'):
        options.binary_location = os.environ['CHROME_BIN']
    with serve_build() as origin, webdriver.Chrome(options=options) as browser:
        verify(browser, origin)
    print('Verified the STEP reading viewport, source zoom and export controls at four sizes.')
