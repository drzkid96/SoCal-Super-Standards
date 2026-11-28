"""Exercise catalog selection, history and actual native ZIP downloads in Chrome."""
import hashlib
import json
import os
import re
from collections import Counter
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zipfile import ZipFile

import ezdxf
import fitz
from ezdxf import bbox

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from test_atlas_browser import serve_build


def check_legend(doc, groups, rows):
    """Each sign is one cell block at its cell's lower-left corner, with its code as MTEXT centered below the face."""
    model = doc.modelspace()
    placements = [e for e in model.query('INSERT') if e.dxf.layer == 'P-SIGN']
    labels = [e for e in model.query('MTEXT') if e.dxf.layer == 'P-SIGN-TEXT']
    titles = [e for e in model.query('MTEXT') if e.dxf.layer == 'P-SIGN-TITL']
    grid = [e for e in model.query('LINE') if e.dxf.layer == 'P-SIGN-TABL']
    ordered = [key for _,keys in groups for key in keys]
    assert len(placements) == len(labels) == len(ordered)
    expected_names = {rows[key]['blockName'] for key in ordered}
    definitions = {b.name for b in doc.blocks if not b.is_any_layout}
    assert definitions == expected_names | {name+'-FACE' for name in expected_names}, (definitions, expected_names)
    for name in expected_names:
        inner = list(doc.blocks[name])
        assert [e.dxftype() for e in inner] == ['INSERT'] and inner[0].dxf.name == name+'-FACE'
    tables = []
    for name, keys in groups:
        count = (len(keys)+27)//28
        for i in range(count):
            title = name.upper() + (f' ({i+1} OF {count})' if count > 1 else '')
            tables.append((title, keys[i*28:i*28+28]))
    assert [e.plain_text() for e in titles] == [name for name,_ in tables]
    assert all(e.dxf.style == 'ROMANS' for e in labels+titles)
    assert len(grid) == 18*len(tables)
    cursor = 0
    for n,(_,keys) in enumerate(tables):
        table_lines = grid[n*18:(n+1)*18]
        xs = sorted({round(e.dxf.start.x,3) for e in table_lines if abs(e.dxf.start.x-e.dxf.end.x)<.001})
        ys = sorted({round(e.dxf.start.y,3) for e in table_lines if abs(e.dxf.start.y-e.dxf.end.y)<.001})
        assert len(xs)==3 and xs[1]-xs[0]==xs[2]-xs[1]==41
        assert len(ys)==15 and all(b-a==48 for a,b in zip(ys,ys[1:]))
        for index,key in enumerate(keys):
            label = labels[cursor]
            insert = placements[cursor]
            row = rows[key]
            px,py,_ = insert.dxf.insert
            assert insert.dxf.xscale == insert.dxf.yscale == 40
            assert insert.dxf.name == row['blockName'] and label.plain_text() == row['code']
            left,right = xs[index%2:index%2+2]
            bottom,top = ys[13-index//2:15-index//2]
            assert abs(px-left)<1e-6 and abs(py-bottom)<1e-6, 'block base point must sit on the cell corner'
            face = bbox.extents(insert.virtual_entities())
            assert left<face.extmin.x<face.extmax.x<right and bottom<label.dxf.insert.y<face.extmin.y<face.extmax.y<top
            assert abs(label.dxf.insert.x-(left+right)/2)<.01 and label.dxf.attachment_point == 8
            cursor+=1


def check_zip(destination, groups, catalog):
    chosen = {key for _,keys in groups for key in keys}
    catalog = {key:dict(catalog[key]) for key in chosen}
    counts = Counter(record['code'] for record in catalog.values())
    for record in catalog.values():
        code = record['code']
        if re.fullmatch(r'R2-1\(\d{1,2}\)',code) and counts[code]==1:
            record['file']=f'individual/{code}.dwg'
            record['blockName']=code
    with ZipFile(destination) as package, TemporaryDirectory() as temp:
        expected = {catalog[i]['file'] for i in chosen}
        expected.update(('LADOT-SIGN-LEGENDS.dwg','LADOT-SIGN-LEGENDS.dxf'))
        assert set(package.namelist()) == expected, set(package.namelist()) ^ expected
        for key in chosen:
            row = catalog[key]
            data = package.read(row['file'])
            assert data[:6] == b'AC1015' and len(data) == row['bytes']
            assert hashlib.sha256(data).hexdigest() == row['sha256']
        dwg = Path(package.extract('LADOT-SIGN-LEGENDS.dwg',temp))
        assert dwg.read_bytes()[:2] == b'AC'
        check_legend(ezdxf.readfile(package.extract('LADOT-SIGN-LEGENDS.dxf',temp)), groups, catalog)
        decoder = os.environ.get('STANDARDS_DWG_DECODER')
        if decoder:
            native = Path(temp)/'reopened.dxf'
            subprocess.run([decoder,str(dwg),'-o',str(native),'-y'],capture_output=True,check=True,timeout=120)
            check_legend(ezdxf.readfile(native),groups,catalog)
    destination.unlink()


def run(browser, base, downloads):
    catalog = {row['id']: row for row in json.load(urlopen(base + 'data/sign-block-options.json'))}
    stop = 'official-r1-1'
    current = 'official-w3-1'
    historic = 'mutcd-sheet-w3-1-1120a'
    wait = WebDriverWait(browser, 20)
    css = lambda selector: browser.find_element(By.CSS_SELECTOR, selector)

    def click(element):
        browser.execute_script("arguments[0].scrollIntoView({block:'center',behavior:'instant'})", element)
        element.click()

    def picker(key):
        inputs = browser.find_elements(By.CSS_SELECTOR, f'input[data-cart-select="{key}"]')
        return next((field for field in inputs if field.is_displayed()), None)

    def count(expected):
        wait.until(lambda _: css('[data-cart-count]').text == str(expected))

    def search(query):
        field = css('#sq')
        field.clear()
        field.send_keys(query)

    def list_selections():
        click(css('[data-cart-open]'))
        wait.until(lambda _: css('[data-cart-dialog]').is_displayed())
        return set(wait.until(lambda _: browser.execute_script("return [...document.querySelectorAll('[data-cart-remove]')].map(button => button.dataset.cartRemove)")))

    def close():
        click(css('[data-cart-close]'))
        wait.until(lambda _: browser.switch_to.active_element == css('[data-cart-open]'))

    browser.get(base+'signs/')
    width = browser.execute_script('return innerWidth')
    search('R1-1')
    click(wait.until(lambda _: picker(stop)))
    count(1)
    click(picker(stop))
    count(0)
    click(picker(stop))
    search('W3-1')
    click(wait.until(lambda _: picker(current)))
    if not picker(historic):
        hidden = css(f'input[data-cart-select="{historic}"]')
        click(hidden.find_element(By.XPATH, 'ancestor::details[1]/summary'))
    click(wait.until(lambda _: picker(historic)))
    count(3)
    browser.refresh()
    count(3)
    assert list_selections() == {stop,current,historic}
    close()

    browser.get(base+'signs/cad/#block-'+current)
    assert wait.until(lambda _: picker(current)).is_selected()
    assert list_selections() == {stop,current,historic}
    close()
    browser.get(base+'signs/w3-1/')
    if not picker(historic):
        hidden = css(f'input[data-cart-select="{historic}"]')
        click(hidden.find_element(By.XPATH, 'ancestor::details[1]/summary'))
    assert wait.until(lambda _: picker(historic)).is_selected()
    assert picker(current).is_selected()
    click(picker(current))
    count(2)
    assert list_selections() == {stop,historic}
    rect = css('[data-cart-dialog]').rect
    assert rect['width'] <= width and rect['x'] >= 0, (width, rect)
    assert browser.execute_script('return document.documentElement.scrollWidth <= innerWidth'), width
    def code_order(ids):
        # the legend keeps sign-code order (R1-1, R1-2, R1-10P, R2-1 ...), the same rule as sign-cart.js
        def natural(text):
            return [(0, int(t), '') if t.isdigit() else (1, 0, t) for t in re.findall(r'\d+|[^\d]+', str(text).upper())]
        def key(rid):
            return natural(catalog[rid]['code']), natural(rid)
        return sorted(ids, key=key)

    def ordered_slots():
        return browser.execute_script("return [...document.querySelectorAll('[data-legend-cell][data-record-id]')].map(cell => cell.dataset.recordId)")

    def download(groups):
        button = css('[data-cart-download]')
        assert 'download sign legend' in button.text.lower()
        click(button)
        assert 'click again' in button.text.lower()   # downloads take two clicks
        click(button)
        destination = downloads/'LADOT-SIGN-LEGEND.zip'
        def downloaded(_):
            status = css('[data-cart-status]').text
            assert 'failed' not in status.lower(),status
            return destination.exists() and destination.stat().st_size > 0
        WebDriverWait(browser,90).until(downloaded)
        if os.environ.get('SIGN_CART_EVIDENCE_DIR'):
            evidence = Path(os.environ['SIGN_CART_EVIDENCE_DIR'])
            evidence.mkdir(parents=True,exist_ok=True)
            (evidence/f'legend-{width}-{sum(len(keys) for _,keys in groups)}.zip').write_bytes(destination.read_bytes())
        check_zip(destination,groups,catalog)

    assert not browser.find_elements(By.CSS_SELECTOR,'[data-cart-earlier],[data-cart-later]')   # order is automatic
    assert ordered_slots() == code_order([stop,historic])
    groups = browser.execute_script('return window.SSSSignCart.getGroups()')
    download([(groups[0]['label'],code_order([stop,historic]))])
    click(css(f'[data-cart-remove="{historic}"]'))
    count(1)
    close()
    browser.get(base+'signs/r1-1/')
    assert wait.until(lambda _: picker(stop)).is_selected()
    assert list_selections() == {stop}
    click(css('[data-cart-clear]'))
    count(0)
    assert css('[data-cart-download]').get_property('disabled')
    css('[data-cart-close]').send_keys(Keys.ESCAPE)
    wait.until(lambda _: not css('[data-cart-dialog]').is_displayed())
    browser.refresh()
    count(0)
    distinct = [stop,historic] + [r for r in sorted(catalog) if r.startswith('official-') and r not in (stop,historic)][:27]
    groups = [{'sheetId':'ss-1','label':'SS-1','records':distinct},{'sheetId':'ss-2','label':'SS-2','records':[stop]}]
    browser.execute_async_script('const done=arguments[arguments.length-1];window.SSSSignCart.importGroups(arguments[0],{mode:"replace",open:true}).then(done);',groups)
    count(30)
    assert ordered_slots() == code_order(distinct)[:28]
    assert len(browser.find_elements(By.CSS_SELECTOR,'[data-legend-cell]'))==28
    cells = browser.find_elements(By.CSS_SELECTOR,'[data-legend-cell]')
    assert cells[0].rect['x'] < cells[1].rect['x'] and cells[0].rect['y']==cells[1].rect['y']
    assert cells[2].rect['x']==cells[0].rect['x'] and cells[2].rect['y']>cells[0].rect['y']
    click(css('[data-legend-next]'))
    assert ordered_slots()==code_order(distinct)[28:] and 'SS-1' in css('[data-legend-caption]').text
    click(css('[data-legend-next]'))
    assert ordered_slots()==[stop] and 'SS-2' in css('[data-legend-caption]').text
    if width>1000:
        download([('SS-1',code_order(distinct)),('SS-2',[stop])])
    click(css('[data-cart-clear]'))
    close()
    browser.get(base+'tools/sign-import/')
    source_file = downloads/'two-sheet-callouts.pdf'
    with fitz.open() as doc:
        for lines in [('SHEET: SS-101','R1-1','W48(2)(CA)','R1-1','R3-7(R)(MOD)','W19-999A'),
                      ('SHEET: SS-102','R1-1','R2-1 (35 MPH)','R2-1 (25)','W48(2)(CA)')]:
            page = doc.new_page()
            for i,line in enumerate(lines):
                page.insert_text((65,65+i*19),line,fontsize=12)
        doc.save(source_file)
    wait.until(lambda _: css('#sign-import-file')).send_keys(str(source_file))
    wait.until(lambda _: len(browser.find_elements(By.CSS_SELECTOR,'.si-sheet'))==2)
    sheets = browser.find_elements(By.CSS_SELECTOR,'.si-sheet')
    duplicate = sheets[0].find_element(By.CSS_SELECTOR,'.si-row[data-key="R1-1"]')
    assert '2 occurrence' in duplicate.text
    assert sheets[0].find_element(By.CSS_SELECTOR,'.si-row[data-key="W19-999A"]').get_attribute('data-match')=='unmatched'
    click(sheets[1].find_element(By.TAG_NAME,'summary'))
    speed = sheets[1].find_element(By.CSS_SELECTOR,'.si-row[data-key="R2-1(35)"] input:checked')
    chosen_speed = speed.get_property('value')
    assert chosen_speed and not sheets[1].find_elements(By.CSS_SELECTOR,'.si-row[data-key="R2-1(35)"] select')
    click(browser.find_element(By.XPATH,'//button[.="Add selected DWGs"]'))
    wait.until(lambda _: 'cart=1' in browser.current_url and css('[data-cart-dialog]').is_displayed())
    imported = browser.execute_script('return window.SSSSignCart.getGroups()')
    expected = [('SS-101',code_order([stop,'official-callout-w48-2ca','3346-signs-1-13-1098640'])),
                ('SS-102',code_order([stop,chosen_speed,'3346-signs-1-13-10980d1','official-callout-w48-2ca']))]
    assert [(g['label'],g['records']) for g in imported] == expected
    count(7)
    download(expected)
    click(css('[data-cart-clear]'))
    close()
    if width>1000 and os.environ.get('STANDARDS_OCR_PDF'):
        browser.get(base+'tools/sign-import/')
        ocr_sample = downloads/'westwood-ss2.pdf'
        with fitz.open(os.environ['STANDARDS_OCR_PDF']) as source, fitz.open() as sample:
            sample.insert_pdf(source, from_page=3, to_page=3)
            sample.set_page_labels([{'startpage':0,'prefix':'SS-2'}])
            sample.save(ocr_sample)
        wait.until(lambda _: css('#sign-import-file')).send_keys(str(ocr_sample))
        WebDriverWait(browser,120).until(lambda _: browser.find_elements(By.CSS_SELECTOR,'.si-row'))
        candidates = ['OM1-3','R10-15(MOD)','R3-4']
        sheet = css('.si-sheet')
        for designation in candidates:
            assert sheet.find_elements(By.CSS_SELECTOR,f'.si-row[data-key="{designation}"] input:checked'),designation
        for row in sheet.find_elements(By.CSS_SELECTOR,'.si-row'):
            if row.get_attribute('data-key') not in candidates:
                for field in row.find_elements(By.CSS_SELECTOR,'input:checked'):
                    click(field)
        click(browser.find_element(By.XPATH,'//button[.="Add selected DWGs"]'))
        wait.until(lambda _: 'cart=1' in browser.current_url and css('[data-cart-dialog]').is_displayed())
        groups=browser.execute_script('return window.SSSSignCart.getGroups()')
        assert len(groups)==1 and groups[0]['label']=='SS-2' and len(groups[0]['records'])==3
        assert {catalog[k]['code'].upper() for k in groups[0]['records']}==set(candidates)
        download([(groups[0]['label'],groups[0]['records'])])
        click(css('[data-cart-clear]'))
        close()
    source_file.unlink()
    print(f'{width}px chart and 3-route persistence; native legend, order, sheet groups and 29th-cell overflow')


if __name__ == '__main__':
    with TemporaryDirectory() as temporary, serve_build() as origin:
        downloads = Path(temporary)
        options = webdriver.ChromeOptions()
        for flag in ('--headless=new', '--no-sandbox', '--disable-dev-shm-usage'):
            options.add_argument(flag)
        if os.environ.get('STANDARDS_TEST_ORIGIN','').startswith('https://'):
            proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
            if proxy:
                options.add_argument('--proxy-server='+proxy)
        if os.environ.get('CHROME_BIN'):
            options.binary_location = os.environ['CHROME_BIN']
        options.add_experimental_option('prefs', {'download.default_directory':str(downloads),'download.prompt_for_download':False})
        with webdriver.Chrome(options=options) as browser:
            browser.execute_cdp_cmd('Browser.setDownloadBehavior', {'behavior':'allow','downloadPath':str(downloads)})
            base = os.environ.get('STANDARDS_TEST_ORIGIN', origin).rstrip('/')+'/'
            for width,height in ((1440,900),(390,844)):
                browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',
                    {'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<600})
                run(browser,base,downloads)
