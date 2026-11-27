"""Check the deployed master, collection, every native drawing and its sign page."""
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from zipfile import ZipFile

from lxml import html
from current_catalog import BASE

dist=Path('dist')
folder=dist/'downloads/sign-blocks'
manifest=json.loads((folder/'manifest.json').read_text())
browser=html.parse(str(dist/'signs/cad/index.html'))
cards=browser.xpath('//*[@data-cad-downloads]//ul[@class="cad-records"]/li[@data-availability="dwg"]')
assert len(cards)==len(manifest['records'])>0
assert len({c.get('id') for c in cards})==len(cards)
def local_asset(file):
    return BASE+'/downloads/sign-blocks/'+quote(file)
master=manifest['master']
packed=manifest['bundle']
assert browser.xpath('//div[@class="cad-bulk"]/a/@href')==[local_asset(master),local_asset(packed)]
assert browser.xpath('//div[@class="cad-bulk"]/a/@download')==['SOCAL-SIGN-CATALOG.dwg','SOCAL-SIGN-BLOCKS.zip']
def verify(file,n,expected,drawing=True):
    data=(folder/file).read_bytes()
    assert n==len(data) and sha256(data).hexdigest()==expected,file
    if drawing:assert data[:4]==b'AC10',file
    return data
verify(master,manifest['masterBytes'],manifest['masterSha256'])
verify(packed,manifest['bundleBytes'],manifest['bundleSha256'],False)
files={c.xpath('.//a[@download]/@href')[0]:c for c in cards}
pages={}
with ZipFile(folder/packed) as z:
    assert z.testzip() is None
    assert master not in z.namelist()   # the master is a separate download, not duplicated in the bundle
    for record in manifest['records']:
        file=record['file']
        data=verify(file,record['bytes'],record['sha256'])
        assert z.read(file)==data,file
        card=files[local_asset(file)]
        assert card.get('data-code')==record['code']
        assert card.get('data-status') and card.get('data-kind')
        if record.get('currentArtworkId') and record.get('currentArtworkUrl'):
            href=record['currentArtworkUrl']
            assert card.xpath('.//a[@href=$href]',href=href) and href.startswith(BASE+'/signs/cad/#')
            assert browser.xpath('//*[@id=$id]',id=href.partition('#')[2])
        url=card.xpath('.//strong[@class="cad-code"]/a/@href')[0]
        assert url==record['signUrl']
        target=urlsplit(url)
        if target.path not in pages:
            pages[target.path]=html.parse(str(dist/target.path.removeprefix(BASE+'/')/'index.html'))
        page=pages[target.path]
        if target.fragment:
            anchor=page.xpath('//*[@id=$id]',id=unquote(target.fragment))
            assert len(anchor)==1,(record['code'],target.fragment)
            sections=anchor[0].xpath('following::section[@class="cad-local"][1]')
        else:
            sections=page.xpath('//section[@class="cad-local"]')
        assert any(local_asset(file) in s.xpath('.//a[@download]/@href') for s in sections),(record['code'],file)
        for alternate in record.get('aliasSignUrls',[]):
            target=urlsplit(alternate)
            linked=html.parse(str(dist/target.path.removeprefix(BASE+'/')/'index.html'))
            if target.fragment:
                linked=linked.xpath('//*[@id=$id]/following::section[@class="cad-local"][1]',id=unquote(target.fragment))[0]
            assert linked.xpath('.//a[@download and @href=$href]',href=local_asset(file)),(alternate,file)
        if record.get('preview'):
            image=dist/record['preview'].lstrip('/')
            preview=image.read_bytes()
            assert len(preview)==record['previewBytes'] and sha256(preview).hexdigest()==record['previewSha256']
            assert z.read('previews/'+image.name)==preview and card.xpath('./a[contains(@class,"cad-preview")]/img')
        if record.get('publishedSides'):
            assert [float(card.get('data-published-width')),float(card.get('data-published-height'))]==record['publishedSides'][:2]
            assert card.xpath('.//a[@href=$url]',url=record['sizeTableUrl'])
    previews={'previews/'+Path(r['preview']).name for r in manifest['records'] if r.get('preview')}
    reference=manifest.get('standardReference')
    if reference:
        file=reference['file']
        assert z.read(file)==verify(file,reference['bytes'],reference['sha256'],False)
        assert browser.xpath('//a[@href=$target]',target=local_asset(file))
    allowed=previews|({reference['file']} if reference else set())|{r['file'] for r in manifest['records']}|{'manifest.json','README.txt',master}
    assert not set(z.namelist())-allowed,'Unexpected material in downloadable archive'
chart=html.parse(str(dist/'signs/index.html'))
assert chart.xpath('//a[@href=$url]',url=BASE+'/signs/cad/')
assert chart.xpath('//*[@id="sorigin"]//option[@value="dwg"]')
extra=json.loads((dist/'data/plan-face-options.json').read_text())
for row in extra: verify(row['file'],row['bytes'],row['sha256'])
native_ids={r['id'] for r in manifest['records']+extra}
chart_ids=set(chart.xpath('//input[@type="checkbox"]/@data-cart-select'))
assert chart_ids<=native_ids
for r in manifest['records']+extra:
    if r['id'] not in chart_ids:assert r['code'].upper().startswith('R2-1'),r['code']
assert not chart.xpath('//input[@data-cart-select]/ancestor::a'),'Checkboxes must sit outside the sign detail links'
options=json.loads((dist/'data/sign-block-options.json').read_text())
assert {r['id']:(r['file'],r['sha256']) for r in options}=={r['id']:(r['file'],r['sha256']) for r in manifest['records']+extra}
for view in (browser,chart):
    assert len(view.xpath('//dialog[@data-cart-dialog]'))==1
    assert view.xpath('//*[@data-cart-open]') and view.xpath('//*[@data-cart-download]')
text=browser.getroot().text_content()
for meta in ('Source and size evidence','Size evidence','File checksums','Source record only','CAD evidence','Reopened after DWG conversion'):
    assert meta not in text,meta
assert not browser.xpath('//*[contains(@class,"cad-evidence")]')
print(f'Verified {len(cards)} native DWG downloads, master, ZIP, SHA-256, sign routes and variant anchors.')

# Check the image served by every sign card, including cards without a DWG.
from PIL import Image
from lxml import etree

chart=html.parse(str(dist/'signs/index.html'))
checked=set()
for url in chart.xpath('//a[@data-code]//img/@src'):
    if url in checked:
        continue
    checked.add(url)
    assert url.startswith(BASE+'/'),url
    path=dist/unquote(url[len(BASE)+1:])
    if path.suffix=='.svg':
        assert etree.QName(etree.parse(str(path)).getroot()).localname=='svg',url
    else:
        with Image.open(path) as picture:
            picture.load()
codes=chart.xpath('//h3[@id="series-r1"]/following-sibling::div[1]//a/@data-code')
assert codes.index('R1-2')<codes.index('R1-3')<codes.index('R1-4')<codes.index('R1-10P'),codes
speeds=chart.xpath('(//h3[@id="series-r2"])[1]/following-sibling::div[1]//a/@data-code')
speeds=speeds[:speeds.index('R2-2')]
assert speeds==[f'R2-1({n})' for n in range(15,60,5)],speeds
print(f'Decoded {len(checked)} sign-chart images and verified R1 and posted-speed ordering.')
