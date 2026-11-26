"""Validate every LADOT drawing page and exercise the visible sheet/PDF workflow in Chrome."""
from contextlib import closing
from functools import partial
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import json
import os
import pymupdf
from lxml import html
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from ladot_drawings import ownership, native_route
from current_catalog import BASE,read

dist=Path('dist')
editions=read('data/reference/ladot-editions.json')
total=0
for key,edition in editions.items():
    source=dist/'ladot-publications'/(key+'.pdf')
    assert sha256(source.read_bytes()).hexdigest()==edition['sha256']
    with pymupdf.open(source) as pdf:
        doc=read('data/docs/ladot__'+key+'.json')
        groups=ownership(key,pdf,doc,edition)
        published=read(dist/'data/publications/ladot'/(key+'.json'))
        manual=html.parse(str(dist/'ladot'/key/'index.html'))
        assert len(manual.xpath('//*[@data-drawing-index]//li/a'))==len(groups)
        for page in range(1,edition['count']+1):
            assert manual.xpath('//*[@id=$id]/a[@href=$href]',id='p'+str(page),href=BASE+'/ladot-publications/'+key+'.pdf#page='+str(page))
        for code,pages in groups.items():
            href=native_route(key,code)
            assert manual.xpath('//*[@data-drawing-index]//a[@href=$href]',href=href+'#sheet-1')
            rendered=html.parse(str(dist/href.removeprefix(BASE+'/')/'index.html'))
            plates=rendered.xpath('//figure[starts-with(@id,"sheet-")]')
            assert len(plates)==len(pages),(key,code,len(plates),pages)
            for i,(fig,page) in enumerate(zip(plates,pages),1):
                assert fig.get('id')==f'sheet-{i}'
                assert fig.xpath('.//img')[0].get('src').endswith(f'/p{page:04d}.webp')
                assert fig.xpath('.//a[@href=$href]',href=edition['url']+'#page='+str(page))
                assert published[page-1]['drawings']==[[code,i,len(pages)]],(key,code,page)
                total+=1
print(f'All {total} drawing sheets match native publisher indexes and scans.')

class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

with TemporaryDirectory() as temp:
    files=Path(temp);(files/'SoCal-Super-Standards').symlink_to(dist.resolve(),target_is_directory=True)
    download=files/'downloads';download.mkdir()
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=temp))
    Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'+BASE+'/'
    opts=webdriver.ChromeOptions()
    if os.getenv('CHROME_BIN'):opts.binary_location=os.environ['CHROME_BIN']
    for arg in ('--headless=new','--no-sandbox','--disable-dev-shm-usage'):opts.add_argument(arg)
    opts.add_experimental_option('prefs',{'download.default_directory':str(download),'download.prompt_for_download':False,'plugins.always_open_pdf_externally':True})
    with closing(webdriver.Chrome(options=opts)) as driver:
        driver.execute_cdp_cmd('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(download)})
        wait=WebDriverWait(driver,25)
        for width in (1440,390):
            driver.set_window_size(width,900)
            driver.get(base+'ladot/')
            a=driver.find_element(By.CSS_SELECTOR,'main a[href$="/details/ladot/mpp-531-s-481-0/#sheet-1"]')
            driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})",a)
            a.click()
            fig=wait.until(lambda d:d.find_element(By.ID,'sheet-1'))
            assert fig.is_displayed()
            assert fig.find_element(By.TAG_NAME,'img').get_attribute('src').endswith('p0108.webp')
            for key,code,slug,page,count in [('mpp-521','S75.0','s-75-0',33,6),('red-book','S-52.1','s-52-1',86,1)]:
                driver.get(base+'ladot/'+key+'/')
                query=wait.until(lambda d:d.find_element(By.CSS_SELECTOR,'[data-drawing-index] input'))
                query.send_keys(code)
                link=driver.find_element(By.CSS_SELECTOR,'[data-drawing-index] li:not([hidden]) a')
                assert link.get_attribute('href').endswith('/'+key+'-'+slug+'/#sheet-1')
                driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})",link)
                link.click()
                if count>1:
                    driver.execute_script("location.hash='sheet-5'")
                selected=wait.until(lambda d:next((x for x in d.find_elements(By.CSS_SELECTOR,'figure[id^=sheet-]') if x.is_displayed() and x.find_element(By.TAG_NAME,'img').get_attribute('src').endswith(f'p{page:04d}.webp')),False))
                assert selected.find_element(By.CSS_SELECTOR,'.sheet-source-actions a').get_attribute('href').endswith('#page='+str(page))
                if width==1440 and key=='mpp-521':
                    def verify_download(button,expected):
                        driver.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})",button);button.click()
                        dest=wait.until(lambda _:next(iter(download.glob('*.pdf')),False),message='Expected PDF download. '+button.get_attribute('textContent'))
                        with pymupdf.open(dest) as pdf,pymupdf.open(dist/'ladot-publications/mpp-521.pdf') as native:
                            assert len(pdf)==len(expected)
                            for j,p in enumerate(expected):
                                assert pdf[j].rect==native[p-1].rect
                                assert pdf[j].get_text()==native[p-1].get_text()
                                render=dict(matrix=pymupdf.Matrix(.7,.7),alpha=False)
                                assert pdf[j].get_pixmap(**render).digest==native[p-1].get_pixmap(**render).digest
                        dest.unlink()
                    verify_download(selected.find_element(By.XPATH,'.//button[text()="Sheet PDF"]'),[33])
                    verify_download(driver.find_element(By.XPATH,'//button[text()="Drawing set PDF"]'),list(range(29,35)))
            driver.get(base+'ladot/mpp-521/#table-1')
            panel=wait.until(lambda d:next((e for e in d.find_elements(By.CSS_SELECTOR,'.publication-window') if e.is_displayed() and e.find_elements(By.CSS_SELECTOR,'a[href$="#page=19"]')),False))
            assert 'left-turn phasing' in panel.text.lower()
            driver.get(base+'ladot/plan-reference/#geo-7')
            target=wait.until(lambda d:d.find_element(By.ID,'geo-7'))
            assert target.is_displayed()
            assert not driver.find_elements(By.XPATH,'//summary[contains(.,"Drawing evidence")]')
        driver.execute_cdp_cmd('Emulation.setScriptExecutionDisabled',{'value':True})
        driver.get(base+'ladot/mpp-531/#p108')
        direct=driver.find_element(By.CSS_SELECTOR,'#p108 a')
        assert direct.is_displayed() and direct.get_attribute('href').endswith('mpp-531.pdf#page=108')
        print('Desktop and mobile LADOT index, correct cross-manual sheet, native one/six-page PDFs, table and plan-detail links passed.')
    server.shutdown()
