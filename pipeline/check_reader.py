from check_atlas import verify as verify_atlas
"""Verify the published descriptions, original images, redirects and comparison layouts."""
from collections import defaultdict
from html import unescape
from pathlib import Path
import re
from urllib.parse import urlsplit
from lxml import html
from current_catalog import BASE, read
from manual_art import ART, SHEET_COUNTS, illustration_url, source

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

# A valid raw image or source PDF can still be the wrong destination for a
# provision's figure reference. The reader must land on its own captioned sheet.
manual_links = 0
for edition in ART:
    for chapter in (dist / edition).glob('*/index.html'):
        doc = chapters.setdefault(chapter, html.parse(str(chapter)))
        for anchor in doc.xpath('//div[contains(concat(" ",@class," ")," prov ")]//a[@href]'):
            text = ' '.join(anchor.text_content().split())
            match = re.fullmatch(r'(Figures?|Tables?)\s+(\d[A-Z]-\d+(?:\s*\(CA\))?)', text)
            if not match:
                continue
            target = illustration_url(edition, *match.groups())
            if not target:
                continue
            assert anchor.get('href') == target, (chapter, text, anchor.get('href'), target)
            route, fragment = target.split('#')
            dest = dist / route.removeprefix(BASE).strip('/') / 'index.html'
            if dest not in chapters:
                chapters[dest] = html.parse(str(dest))
            figures = chapters[dest].xpath('//*[@id=$fragment]/ancestor::figure[1]', fragment=fragment)
            assert len(figures) == 1 and figures[0].xpath('./a/img[@src]') and figures[0].xpath('./figcaption'), target
            manual_links += 1
print(f'{manual_links} MUTCD provision citations verified against their edition’s captioned figures and tables.')

for page in (dist / 'details' / 'ladot').rglob('index.html'):
    doc = html.parse(str(page))
    sheets = doc.xpath('//figure[starts-with(@id,"sheet-") and @class="dfig"]')
    if len(sheets) < 2:
        continue
    headings = doc.xpath('//div[contains(concat(" ", @class, " "), " sl-markdown-content ")]/h3[starts-with(normalize-space(.),"Sheet ") or starts-with(normalize-space(.),"Supplement to S-")]')
    assert len(headings) == len(sheets), (page, len(headings), len(sheets))
    for index, (heading, sheet) in enumerate(zip(headings, sheets), 1):
        label=f'Sheet {index} of {len(sheets)}'
        if page.parent.name=='mpp-531-s-440-0':label=('Sheet 1 of 2','Sheet 2 of 2','Supplement to S-440.0')[index-1]
        assert heading.text_content().startswith(label), page
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

# The left navigation is scoped to the current publication and works without JavaScript.
for edition in ('ca-mutcd', 'mutcd'):
    chapter = html.parse(str(dist / edition / '4i/index.html'))
    side = chapter.xpath('//*[@id="starlight__sidebar"]')[0]
    hrefs = side.xpath('.//a/@href')
    index = BASE + '/' + edition + '/'
    assert side.xpath('.//a[@aria-current="page"]/@href') == [index + '4i/']
    assert {index + '4h/', index + '4j/', index + '#part-2'} <= set(hrefs)
    contents = html.parse(str(dist / edition / 'index.html'))
    for href in hrefs:
        if href.startswith(index + '#'):
            assert contents.xpath('//*[@id=$fragment]', fragment=href.split('#')[1]), href
sign_page = html.parse(str(dist / 'signs/r1-1/index.html'))
sign_sidebar = sign_page.xpath('//*[@id="starlight__sidebar"]')[0]
sign_links = sign_sidebar.xpath('.//a/@href')
assert {BASE + '/signs/', BASE + '/signs/cad/', BASE + '/signs/r1-1/'} <= set(sign_links)
assert len(sign_links) <= 16, len(sign_links)
print('Scoped sidebar links verified on the sign catalog and both MUTCD editions.')

# A page can have zero broken URLs while showing unrendered math or unlinked citations.
import re
from boe_references import math_matches

math_count = figure_links = footnote_links = 0
for url in manual_pages:
    path = dist / url.removeprefix(BASE).strip('/') / 'index.html'
    article = html.parse(str(path)).xpath('//*[@class="sl-markdown-content"]')[0]
    for node in article.xpath('.//text()[not(ancestor::math or ancestor::code or ancestor::pre)]'):
        assert not math_matches(node) and not re.search(r'\\(?:frac|sqrt)\s*\{', node), (url, str(node)[:80])
    equations = article.xpath('.//*[@data-source-tex]')
    for eq in equations:
        assert eq.xpath('.//math/semantics/annotation'), (url, eq.get('data-source-tex'))
        for command, element in [(r'\frac', 'mfrac'), (r'\sqrt', 'msqrt')]:
            assert eq.get('data-source-tex').count(command) == len(eq.xpath('.//'+element)), (url, command)
    math_count += len(equations)
    refs = article.xpath('.//a[@class="boe-figure-ref"]')
    for anchor in refs:
        target, fragment = anchor.get('href').split('#')
        dest = dist / target.removeprefix(BASE).strip('/') / 'index.html'
        if dest not in chapters:
            chapters[dest] = html.parse(str(dest))
        matches = chapters[dest].xpath('//*[@id=$id]',id=fragment)
        assert len(matches)==1 and (matches[0].tag=='img' or matches[0].xpath('.//img[@src]')), anchor.get('href')
    figure_links += len(refs)
    for anchor in refs:
        block = next(el for el in (anchor, *anchor.iterancestors()) if el.tag in ('p','li','td','dd','blockquote'))
        strip = block.getnext() if block.tag in ('p','blockquote') else block.xpath('./div[@class="boe-fig-strip"]')[0]
        assert strip is not None and strip.get('class') == 'boe-fig-strip' and strip.xpath('.//a[@class="boe-fig-thumb"][@href=$h]/img[@src]', h=anchor.get('href')), (url, anchor.get('href'))
    notes = article.xpath('.//sup/a[starts-with(@href,"#boe-note-")]')
    for anchor in notes:
        assert article.xpath('.//li[@id=$id]',id=anchor.get('href')[1:]), (url, anchor.get('href'))
    footnote_links += len(notes)
    if '/e-664-median-left-turn-lanes-' in url:
        assert len(equations)==5 and len(article.xpath('.//math//mfrac'))==4
        layout = article.get_element_by_id('e-664-2').getnext()
        assert [a.get('href').split('#')[-1] for a in layout.xpath('.//a[@class="boe-figure-ref"]')] == [
            'boe-figure-464-2a','boe-figure-464-2b','boe-figure-464-2c','boe-figure-464-2b','boe-figure-464-2b']
        assert 'no longer in use' in article.get_element_by_id('boe-note-1').text_content()
        assert article.xpath('.//p[@class="boe-reading-note"]//a[@href]')
assert math_count >= 41 and figure_links >= 100 and footnote_links > 0
print(f'BOE presentation verified: {math_count} rendered equations, {figure_links} figure citations, {footnote_links} footnote links.')

import runpy
runpy.run_path(str(Path(__file__).with_name('check_inline_examples.py')))

verify_atlas()
