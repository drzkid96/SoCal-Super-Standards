"""Check every generated inline example against the built site and its destination."""
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit
from lxml import html
from current_catalog import BASE

dist = Path('dist')
families = Counter()
placements = Counter()
targets = {}
pictures = set()
for file in dist.rglob('*.html'):
    raw = file.read_text()
    if 'class="inline-examples"' not in raw:
        continue
    doc = html.fromstring(raw)
    group = file.relative_to(dist).parts[0]
    families[group] += 1
    for strip in doc.xpath('//div[@class="inline-examples"]'):
        assert strip.getprevious() is not None and strip.getprevious().tag == 'p', file
        assert not strip.xpath('ancestor::nav|ancestor::figure|ancestor::del|ancestor::table'), file
        cards = strip.findall('a')
        assert 1 <= len(cards) <= 3, file
        for card in cards:
            image = card.find('img')
            src = image.get('src')
            assert src.startswith(BASE+'/') and (dist/src[len(BASE)+1:]).is_file(), (file, src)
            assert image.get('loading') == 'lazy' and card.text_content().strip(), file
            url = urlsplit(card.get('href'))
            assert not url.netloc and url.path.startswith(BASE+'/'), card.get('href')
            path = dist/unquote(url.path[len(BASE)+1:])
            if path.is_dir():
                path = path/'index.html'
            assert path.is_file(), (file, path)
            if url.fragment:
                if path not in targets:
                    targets[path] = set(html.parse(str(path)).xpath('//*[@id]/@id'))
                assert unquote(url.fragment) in targets[path], (file, card.get('href'))
            pictures.add(src)
            placements[group] += 1
assert {'mutcd','ca-mutcd','ladot'} <= families.keys(), families
print(f'{sum(placements.values())} inline examples, {len(pictures)} distinct images, {sum(families.values())} illustrated pages')
for group in sorted(families):
    print(f'{group}: {placements[group]} examples on {families[group]} pages')
