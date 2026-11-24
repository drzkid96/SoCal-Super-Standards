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
            slider=art.find_element(By.CSS_SELECTOR,'.loose-size input[type=range]')
            slider.send_keys(Keys.HOME)
            standalone=fig.find_element(By.CSS_SELECTOR,'img.sized-scan')
            assert standalone.rect['width'] < fig.rect['width']*.20
            slider.send_keys(Keys.END)
            assert standalone.rect['width'] > fig.rect['width']*.90
            browser.get(base+'details/ladot/mpp-531-s-481-0/#sheet-3-note-1')
            wait=WebDriverWait(browser,12)
            selector=wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'.sheet-controls select'))
            assert Select(selector).first_selected_option.text.startswith('Sheet 3')
            assert browser.find_element(By.ID,'sheet-3-note-1').is_displayed()
            bar=selector.find_element(By.XPATH,'..')
            browser.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})",bar)
            bar.find_element(By.CSS_SELECTOR,'.sc-next').click()
            assert Select(selector).first_selected_option.text.startswith('Sheet 4')
            assert not bar.find_element(By.CSS_SELECTOR,'.sc-next').is_enabled()
            Select(selector).select_by_index(0)
            assert browser.find_element(By.ID,'sheet-1').is_displayed()
            assert not browser.find_element(By.ID,'sheet-4').is_displayed()
            scan=browser.find_element(By.CSS_SELECTOR,'.sheet-frame:not([hidden]) figure.dfig img')
            frame=scan.find_element(By.XPATH,'ancestor::figure')
            fit=bar.find_element(By.XPATH,'.//button[text()="Fit page"]')
            fit.click()
            assert fit.get_attribute('aria-pressed')=='true'
            assert scan.rect['height']<=browser.execute_script('return innerHeight')*.75
            bar.find_element(By.XPATH,'.//button[text()="Full width"]').click()
            assert scan.rect['width'] >= frame.rect['width']*.94, (width,scan.rect,frame.rect)
            toggle=bar.find_element(By.CSS_SELECTOR,'.sc-mode')
            toggle.click()
            assert browser.find_element(By.ID,'sheet-4').is_displayed()
            toggle.click()
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
        for query, expected in [('G1-4(CA)', '/signs/g1-4ca/'), ('S 481.0','/details/ladot/mpp-531-s-481-0/'), ('Caltrans T31','#plan-t31')]:
            browser.get(base+'search/?q='+__import__('urllib.parse',fromlist=['quote']).quote(query))
            first=wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'#standards-results li a'))
            assert expected in first.get_attribute('href'), (query,first.text,first.get_attribute('href'))
        browser.get(base+'search/?q=G14(CA)')
        assert 'deletion notice' in wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'#standards-results li a')).text
        browser.get(base+'search/?q=pedestrian&source=Federal+MUTCD')
        wait.until(lambda d:len(d.find_elements(By.CSS_SELECTOR,'#standards-results li'))>0)
        assert all(x.text=='Federal MUTCD' for x in browser.find_elements(By.CSS_SELECTOR,'#standards-results small'))
        browser.get(base+'topics/bikeways/')
        assert len(browser.find_elements(By.CSS_SELECTOR,'.type-example img'))>=4
        assert 'Motorcycle Parking' not in browser.find_element(By.CSS_SELECTOR,'.sl-markdown-content').get_attribute('textContent')
        browser.get(base+'details/ladot/mpp-531-s-481-0/')
        assert not browser.find_elements(By.CSS_SELECTOR,'a[href*="/redraw/"]')
        assert browser.find_element(By.CSS_SELECTOR,'.detail-description').is_displayed()
        browser.get(base+'santa-monica/standard-plans/#sheet-ttcp-requirements-6')
        uploads=browser.find_element(By.ID,'sheet-ttcp-requirements-6').find_element(By.XPATH,'ancestor::figure')
        assert uploads.is_displayed()
        viewer=uploads.find_element(By.XPATH,'ancestor::div[contains(@class,"sss-ms-wrap")]')
        assert len(Select(viewer.find_element(By.TAG_NAME,'select')).options)==14
        assert 'page 6 of 14' in uploads.text
        assert '#page=6' in uploads.find_element(By.CSS_SELECTOR,'figcaption a').get_attribute('href')
        browser.get(base+'boe/street-design/')
        field=browser.find_element(By.ID,'boe-filter')
        field.send_keys('E550')
        hits=browser.find_elements(By.CSS_SELECTOR,'.boe-group:not([hidden]) li:not([hidden])')
        assert len(hits)==1 and 'Intersections' in hits[0].text
        field.clear()
        field.send_keys('no such engineering phrase')
        assert 'No matching sections' in browser.find_element(By.ID,'boe-count').text
        browser.get(base+'search/?q=BOE+E+664.12')
        storage=wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'#standards-results li a'))
        assert storage.get_attribute('href').endswith('#e-664-12'), storage.text
        storage.click()
        assert browser.find_element(By.ID,'e-664-12').text == 'E 664.12 Storage Length'
        for width, menu in [(1280,'starlight-toc'),(390,'mobile-starlight-toc')]:
            browser.set_window_size(width,900)
            outline=browser.find_element(By.TAG_NAME,menu)
            if menu.startswith('mobile'):
                outline.find_element(By.TAG_NAME,'summary').click()
            transition=outline.find_element(By.CSS_SELECTOR,'a[href="#e-664-21"]')
            transition.click()
            assert browser.current_url.endswith('#e-664-21')
        browser.get(base+'signs/?q=R10-3b')
        card=wait.until(lambda d:next((a for a in d.find_elements(By.CSS_SELECTOR,'.scard:not([hidden])') if a.get_attribute('data-code')=='R10-3b'),False))
        card.click()
        wait.until(lambda d:'R10-3b' in d.find_element(By.TAG_NAME,'h1').text)
        assert len(browser.find_elements(By.CSS_SELECTOR,'.mfig-grid figure'))==2
        for route,groups in [('signs/', '.sseries .sgrid'),('markings/', '.mcat-sec .mgrid')]:
            browser.get(base+route)
            controls=browser.find_element(By.CSS_SELECTOR,'.chart-size')
            selector=Select(controls.find_element(By.TAG_NAME,'select'))
            slider=controls.find_element(By.CSS_SELECTOR,'input[type=range]')
            assert len(selector.options)>2
            slider.send_keys(Keys.HOME)
            grids=browser.find_elements(By.CSS_SELECTOR,groups)
            assert all(g.get_attribute('data-chart-level')=='0' for g in grids)
            selector.select_by_index(1)
            slider.send_keys(Keys.END)
            levels={g.get_attribute('data-chart-level') for g in grids}
            assert levels=={'0','6'}, (route,levels)
            browser.refresh()
            assert {g.get_attribute('data-chart-level') for g in browser.find_elements(By.CSS_SELECTOR,groups)}==levels
        browser.get(base+'ca-mutcd/9e/#fig-9e-3ca-sheet-7')
        seventh=browser.find_element(By.ID,'fig-9e-3ca-sheet-7').find_element(By.XPATH,'ancestor::figure')
        assert seventh.is_displayed() and 'Sheet 7 of 7' in seventh.text
        options=Select(seventh.find_element(By.XPATH,'ancestor::div[contains(@class,"sss-ms-wrap")]//select')).options
        assert len(options)==7
        assert all(option.text.startswith(f'Sheet {i} of 7') for i, option in enumerate(options, 1))
        browser.get(base+'details/ladot/mpp-531-s-418-6/')
        deck=browser.find_element(By.ID,'sheet-1').find_element(By.XPATH,'ancestor::div[contains(@class,"sss-ms-wrap")]')
        tabs=deck.find_elements(By.CSS_SELECTOR,'.sheet-strip .sc-thumb')
        assert len(tabs)==16, [tab.text for tab in tabs]
        for number in (7,8,16):
            tabs[number-1].click()
            frame=deck.find_element(By.CSS_SELECTOR,'.sheet-frame:not([hidden])')
            images=frame.find_elements(By.CSS_SELECTOR,'figure.dfig')
            assert [img.get_attribute('id') for img in images]==[f'sheet-{number}']
        deck.find_element(By.CSS_SELECTOR,'.sc-mode').click()
        Select(deck.find_element(By.CSS_SELECTOR,'.sc-select')).select_by_index(7)
        active=deck.find_element(By.CSS_SELECTOR,'.sheet-frame:not([hidden])')
        source=active.find_element(By.CSS_SELECTOR,'.sheet-source-actions a').get_attribute('href')
        assert source.endswith('#page=79') and browser.current_url.endswith('#sheet-8')
        assert not browser.find_elements(By.CSS_SELECTOR,'nav[aria-label="Drawing sheets"]')
        browser.execute_script("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async value=>{window.lastCitation=value}}})")
        browser.execute_script("document.querySelector('.sp-cite').click()")
        assert 'sheet 8 of 16' in browser.execute_script('return window.lastCitation')
        assert browser.execute_script('return window.lastCitation').endswith(source)
        for query, fragment in [('MPP 531 S-418.6 sheet 8','#sheet-8'), ('MPP 531 S-418.6 p.79','#sheet-8'),
                                ('CA MUTCD Figure 9E-3(CA) sheet 7','#fig-9e-3ca-sheet-7'),
                                ('Santa Monica TTCP page 6','#sheet-ttcp-requirements-6')]:
            browser.get(base+'search/?q='+__import__('urllib.parse',fromlist=['quote']).quote(query))
            first=wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'#standards-results li a'))
            assert first.get_attribute('href').endswith(fragment), (query,first.text)
        browser.get(base+'search/?q=pedestrian&source=Federal+MUTCD')
        more=wait.until(lambda d:d.find_element(By.ID,'standards-more') if d.find_element(By.ID,'standards-more').is_displayed() else False)
        more.click()
        returned=wait.until(lambda d: d.find_elements(By.CSS_SELECTOR,'#standards-results li a')[18] if len(d.find_elements(By.CSS_SELECTOR,'#standards-results li a'))>18 else False)
        target=returned.get_attribute('href')
        returned.click()
        wait.until(lambda d:'/search/' not in d.current_url)
        browser.back()
        wait.until(lambda d:len(d.find_elements(By.CSS_SELECTOR,'#standards-results li a'))>18)
        assert browser.find_elements(By.CSS_SELECTOR,'#standards-results li a')[18].get_attribute('href')==target
        browser.get(base+'details/?agency=LADOT')
        assert wait.until(lambda d:Select(d.find_element(By.ID,'dx-sg')).first_selected_option.text=='LADOT')
        for agency in ['caltrans','fhwa','ada','boe','ladot']:
            browser.get(base+agency+'/')
            heading=browser.find_element(By.CSS_SELECTOR,'.agency-heading')
            assert heading.get_attribute('data-agency')==agency and heading.find_element(By.TAG_NAME,'h1').is_displayed()
        browser.get(base+'cities/')
        maplink=browser.find_element(By.CSS_SELECTOR,'.map-hero figcaption a[href$=".pdf"]')
        assert maplink.get_attribute('textContent').strip()=='Original county map (PDF)'
        assert 'planning.lacounty.gov/' in maplink.get_attribute('href')
        assert browser.execute_script("return getComputedStyle(arguments[0],'::after').content",maplink).find('↗')>=0
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
