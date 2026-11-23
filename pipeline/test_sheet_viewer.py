"""Exercise actual built pages at desktop and phone widths in Chrome."""
import contextlib
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
            browser.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})",bar)
            bar.find_elements(By.TAG_NAME,'button')[1].click()
            assert Select(selector).first_selected_option.text.startswith('Sheet 4')
            assert not bar.find_elements(By.TAG_NAME,'button')[1].is_enabled()
            Select(selector).select_by_index(0)
            assert browser.find_element(By.ID,'sheet-1').is_displayed()
            assert not browser.find_element(By.ID,'sheet-4').is_displayed()
        browser.get(base)
        q=browser.find_element(By.CSS_SELECTOR,'.quick-lookup input')
        wait=WebDriverWait(browser,15)
        q.send_keys('R81 (CA)')
        wait.until(lambda d:'Retired' in d.find_element(By.CSS_SELECTOR,'.ql-item').text)
        q.send_keys(Keys.ARROW_DOWN)
        assert q.get_attribute('aria-activedescendant')
        q.send_keys(Keys.ESCAPE)
        assert q.get_attribute('aria-expanded')=='false'
        q.clear()
        q.send_keys('BOE E 550',Keys.ENTER)
        wait.until(lambda d:'/boe/street-design/' in d.current_url)
        assert browser.find_element(By.TAG_NAME,'h1').text.startswith('E 550')
        browser.get(base+'boe/street-design/')
        field=browser.find_element(By.ID,'boe-filter')
        field.send_keys('E550')
        hits=browser.find_elements(By.CSS_SELECTOR,'.boe-group:not([hidden]) li:not([hidden])')
        assert len(hits)==1 and 'Intersections' in hits[0].text
        field.clear()
        field.send_keys('no such engineering phrase')
        assert 'No matching sections' in browser.find_element(By.ID,'boe-count').text
        browser.get(base+'signs/?q=R10-3b')
        card=wait.until(lambda d:next((a for a in d.find_elements(By.CSS_SELECTOR,'.scard:not([hidden])') if a.get_attribute('data-code')=='R10-3b'),False))
        card.click()
        wait.until(lambda d:'R10-3b' in d.find_element(By.TAG_NAME,'h1').text)
        assert len(browser.find_elements(By.CSS_SELECTOR,'.mfig-grid figure'))==2
        browser.get(base+'ca-mutcd/6b/#6b08')
        assert browser.find_element(By.ID,'6b08').is_enabled()
        assert 'chapter for the marked-up' not in browser.find_element(By.ID,'6b08-p01').text
        browser.get(base+'ca-mutcd/4i/#4i05-p10')
        note=browser.find_element(By.ID,'4i05-p10')
        assert 'adjacent to' in note.find_element(By.TAG_NAME,'del').text
        assert 'immediately above' in note.find_element(By.CSS_SELECTOR,'.ca').text
        browser.get(base+'ca-mutcd/2b/#2b04')
        assert 'STOP' in browser.find_element(By.ID,'2b04-p01').text
    server.shutdown()
print('Sheet viewer passed at 1280 and 390 pixels.')
