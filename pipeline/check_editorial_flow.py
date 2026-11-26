"""Verify rendered guidance precedes exhibits and reader links reach actual sections."""
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit
from lxml import html
from current_catalog import BASE

dist = Path(sys.argv[1]) if len(sys.argv)>1 else Path('dist')
target_ids = {}
def article(file):
    return html.parse(str(file)).xpath('//*[contains(concat(" ",normalize-space(@class)," ")," sl-markdown-content ")]')[0]

def guide(slug):
    return article(dist/'guides'/slug/'index.html')

def order(nodes):
    return [node for node in nodes if isinstance(node.tag, str)]

# These used to put two galleries and a legal notice ahead of the value table.
for slug in ('nacto-urban-street','nacto-urban-bikeway','cpbs-plts','aashto-bike-guide'):
    doc = guide(slug)
    children = order(doc)
    table = next(i for i,node in enumerate(children) if node.tag=='table')
    first_gallery = next(i for i,node in enumerate(children) if 'gallery' in (node.get('class') or ''))
    assert table < first_gallery, (slug, table, first_gallery)

lpi = article(dist/'bulletins/ladot-lpi-2021/index.html')
design = lpi.xpath('.//h2[@id="design"]')[0]
assert design.xpath('following-sibling::*[1]')[0].tag == 'ul', 'LPI design rules should open the section'
figure = lpi.xpath('.//figure[.//img[contains(@src,"/R10-15.svg")]]')[0]
assert 'NO TURN ON RED' not in figure.text_content().upper()
assert figure.xpath('.//a/@href')[0].endswith('/signs/r10-15/')
dib = article(dist/'bulletins/caltrans-dib-82-06/index.html')
assert dib.xpath('.//*[@class="article-source-line"]/a[contains(@href,"dib82-06-a11y.pdf")]')
assert guide('cpbs-plts').xpath('.//a[@href="https://rosap.ntl.bts.gov/view/dot/93236"]')

checked = source_refs = editions = 0
for family in ('guides','bulletins'):
    for file in sorted((dist/family).glob('*/index.html')):
        doc = article(file);checked += 1
        for panel in doc.xpath('.//*[@class="bul-meta"]'):
            assert panel.xpath('ancestor::details'),file
            editions += 1
        for href in doc.xpath('.//figure[@class="mfig"]/a/@href'):
            url = urlsplit(href)
            if not url.path.startswith(BASE+'/') or url.path.endswith(('.svg','.webp','.png','.jpg')):
                continue
            destination = dist/unquote(url.path[len(BASE)+1:])
            if destination.is_dir(): destination /= 'index.html'
            assert destination.is_file(),(file, href)
            if url.fragment:
                if destination not in target_ids:
                    target_ids[destination] = set(html.parse(str(destination)).xpath('//*[@id]/@id'))
                assert unquote(url.fragment) in target_ids[destination],(file, href)
            source_refs += 1
assert checked >=24 and editions >=17 and source_refs >=100,(checked,editions,source_refs)
print(f'{checked} editorial routes, {editions} edition disclosures, {source_refs} verified source-reader links; guidance precedes illustrations.')
