"""Exercise actual built pages at desktop and phone widths in Chrome."""
import contextlib
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


with TemporaryDirectory() as temp:
    (Path(temp)/'SoCal-Super-Standards').symlink_to(Path('dist').resolve(), target_is_directory=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=temp))
    Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}/SoCal-Super-Standards/'
    options=webdriver.ChromeOptions()
    for flag in ('--headless=new','--no-sandbox','--disable-dev-shm-usage'):options.add_argument(flag)
    with contextlib.closing(webdriver.Chrome(options=options)) as browser:
        for width in (1280,390):
            browser.set_window_size(width,900)
            browser.get(base+'ca-mutcd/4i/')
            art=browser.find_element(By.CSS_SELECTOR,'.sl-markdown-content')
            fig=art.find_element(By.CSS_SELECTOR,'.mfig-inline.single')
            assert abs(fig.rect['width']-art.rect['width'])<=2, (width,fig.rect,art.rect)
            browser.get(base+'details/ladot/mpp-531-s-481-0/#sheet-3-note-1')
            wait=WebDriverWait(browser,12)
            selector=wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'.sheet-controls select'))
            assert Select(selector).first_selected_option.text.startswith('Sheet 3')
            assert browser.find_element(By.ID,'sheet-3-note-1').is_displayed()
            bar=selector.find_element(By.XPATH,'..')
            bar.find_elements(By.TAG_NAME,'button')[1].click()
            assert Select(selector).first_selected_option.text.startswith('Sheet 4')
            assert not bar.find_elements(By.TAG_NAME,'button')[1].is_enabled()
            Select(selector).select_by_index(0)
            assert browser.find_element(By.ID,'sheet-1').is_displayed()
            assert not browser.find_element(By.ID,'sheet-4').is_displayed()
    server.shutdown()
print('Sheet viewer passed at 1280 and 390 pixels.')
