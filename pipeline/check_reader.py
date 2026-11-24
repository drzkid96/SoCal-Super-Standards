"""Verify the published descriptions, original images, redirects and comparison layouts."""
from collections import defaultdict
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit
from lxml import html
from current_catalog import BASE, read
from manual_art import ART, SHEET_COUNTS, source

dist=Path('dist')
details=read(dist/'data/details.json')
by_page=defaultdict(list)
for row in details:
    assert row.get('description'), row['url']
    by_page[urlsplit(row['url']).path].append(row)
for url,rows in by_page.items():
    file=dist/url.removeprefix(BASE).strip('/')/'index.html'
    doc=html.parse(str(file))
    notes={' '.join(el.text_content().split()) for el in doc.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," detail-description ")]')}
    for row in rows:
        assert ' '.join(row['description'].split()) in notes,(row['url'],row['description'][:60])
        if row['type'] in ('Figure','Table','Agency sheet'):
            assert (dist/row['full'].removeprefix(BASE+'/')).is_file(),row['full']
for route,dest in read('.standards/redirects.json').items():
    redirect=(dist/route.strip('/')/'index.html').read_text()
    assert 'content="0;url='+BASE+dest+'"' in redirect,route
for f in dist.rglob('*.html'):
    assert BASE+'/redraw/' not in f.read_text(),f
for family,minimum in [('bikeways',4),('speed-and-calming',6),('signals',10)]:
    page=html.parse(str(dist/'topics'/family/'index.html'))
    assert len(page.xpath('//figure[@class="type-example"]//img'))>=minimum
print(f'{len(details)} descriptions verified at their destinations. Original sheets, redirects and comparison illustrations passed.')

chapters = {}
checked_sheets = 0
for edition, items in SHEET_COUNTS.items():
    for key, count in items.items():
        kind, number = key.split()
        chapter = number.split('-')[0].lower()
        route = dist / edition / chapter / 'index.html'
        if route not in chapters:
            chapters[route] = html.parse(str(route))
        slug = number.lower().replace('(', '').replace(')', '')
        anchor = ('fig-' if kind == 'Figure' else 'table-') + slug
        group = chapters[route].xpath('//*[@id=$anchor]/ancestor::figure[1]/..', anchor=anchor)
        assert len(group) == 1, (edition, key, 'missing or duplicate figure')
        sheets = group[0].xpath('./figure')
        assert len(sheets) == count, (edition, key, len(sheets), count)
        first_page = ART[edition][key][1]
        for index, sheet in enumerate(sheets, 1):
            page = first_page + index - 1
            label = f'Sheet {index} of {count}'
            image = f'/figs/{edition}/p{page:04d}.webp'
            pdf, pdf_page = source(edition, number, page)
            assert sheet.xpath('./a/img/@src') == [BASE + image], (key, label, image)
            assert (dist / image.lstrip('/')).is_file(), image
            assert label in sheet.xpath('./figcaption')[0].text_content(), (key, label)
            assert pdf + '#page=' + str(pdf_page) in sheet.xpath('./figcaption/a/@href'), (key, label)
            checked_sheets += 1
print(f'{checked_sheets} individual sheets verified across {sum(map(len, SHEET_COUNTS.values()))} multi-sheet manual figures and tables.')

for page in (dist / 'details' / 'ladot').rglob('index.html'):
    doc = html.parse(str(page))
    sheets = doc.xpath('//figure[starts-with(@id,"sheet-") and @class="dfig"]')
    if len(sheets) < 2:
        continue
    headings = doc.xpath('//div[contains(concat(" ", @class, " "), " sl-markdown-content ")]/h3[starts-with(normalize-space(.),"Sheet ")]')
    assert len(headings) == len(sheets), (page, len(headings), len(sheets))
    for index, (heading, sheet) in enumerate(zip(headings, sheets), 1):
        assert heading.text_content().startswith(f'Sheet {index} of {len(sheets)}'), page
        assert heading.getnext() == sheet, (page, sheet.get('id'))

# Both the desktop and phone outlines must lead to the actual imported headings.
manual_pages = read('.standards/boe-navigation.json')
boe_heading_count = 0
for url, manual_page in manual_pages.items():
    page = dist / url.removeprefix(BASE).strip('/') / 'index.html'
    doc = html.parse(str(page))
    sidebar = doc.xpath('//*[@id="starlight__sidebar"]')[0]
    current = sidebar.xpath('.//a[@aria-current="page"]/@href')
    assert current == [url], (url, current)
    actual = doc.xpath('//*[contains(concat(" ",@class," "), " sl-markdown-content ")]//*[self::h2 or self::h3 or self::h4 or self::h5 or self::h6][normalize-space()]')
    expected_ids = [h['slug'] for h in manual_page['headings']]
    assert [el.get('id') for el in actual] == expected_ids, (url, expected_ids, [el.get('id') for el in actual])
    assert not doc.xpath('//*[contains(@class,"sl-markdown-content")]//img[not(normalize-space(@src))]'), url
    for menu in ('starlight-toc', 'mobile-starlight-toc'):
        links = doc.xpath(f'//{menu}//a/@href')
        assert [href for href in links if href != '#_top'] == ['#'+el.get('id') for el in actual], (url, menu)
    boe_heading_count += len(actual)
assert set(sidebar.xpath('.//a/@href')) >= set(manual_pages)
print(f'{boe_heading_count} BOE headings and both navigation menus verified on {len(manual_pages)} pages.')
