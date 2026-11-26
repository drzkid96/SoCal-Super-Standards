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

# Verify publication placement, credits and assets in built HTML. This also catches
# a homepage generator replacing an engineering example with an uncredited banner.
from project_photos import PAGES, PHOTOS

for filename, keys in PAGES.items():
    relative = Path(filename).with_suffix('')
    target = dist/relative/'index.html' if relative.name != 'index' else dist/relative.parent/'index.html'
    article = html.parse(str(target))
    for key in keys:
        photo = PHOTOS[key]
        src = BASE+'/figs/projects/'+photo.file+'.webp'
        matches = article.xpath('//figure[a/img[@src=$src] and figcaption/a[@href=$credit]]', src=src, credit=photo.source)
        assert len(matches) == 1, (target, photo.treatment)
        assert matches[0].find('a/img').get('alt') == photo.description, (target,src)
        assert (dist/src[len(BASE)+1:]).is_file(), (target,src)
home = html.parse(str(dist/'index.html'))
for key in ('redondo','venice'):
    photo = PHOTOS[key]
    preview = BASE+'/thumbs/figs/projects/'+photo.file+'.webp'
    assert home.xpath('//figure[@class="home-photo" and img[@src=$src] and figcaption/a[@href=$credit]]',
                      src=preview, credit=photo.source), key
    assert (dist/preview[len(BASE)+1:]).is_file(), preview
print(f'{len(PHOTOS)} documented regional photos, {sum(map(len,PAGES.values()))} field placements, 2 credited homepage photos')
