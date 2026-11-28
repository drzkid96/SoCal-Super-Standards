"""Publish marking and signal block libraries from their shared catalog."""
import json
from html import escape
from pathlib import Path
from urllib.parse import quote

from current_catalog import BASE


def build(root, lookup):
    catalog = json.loads(Path('data/reference/design-blocks.json').read_text())
    for route, collection in catalog.items():
        title = collection['title']
        href = f'{BASE}/{route}/'
        page = root / route / 'index.md'
        page.parent.mkdir(parents=True, exist_ok=True)
        lines = ['---', 'title: ' + json.dumps(title), 'tableOfContents: false', '---', '']
        lines.extend([f'<link rel="stylesheet" href="{BASE}/js/block-cart.css">',
                      f'<script src="{BASE}/js/block-generators.js" defer></script>',
                      f'<script src="{BASE}/js/block-cart.js" defer></script>', ''])
        if collection.get('note'):
            lines.extend([escape(collection['note']), ''])
        lines.extend(['<div class="block-tools"><button type="button" onclick="window.SSSBlockCart&&SSSBlockCart.open()">Open block cart</button>'
                      '<button type="button" data-block-editor="crosswalk">Block editor</button></div>', ''])
        if collection.get('preview'):
            image = Path('public') / collection['preview']
            if not image.is_file():
                raise ValueError(f'Missing preview: {image}')
            lines.extend([f'<img src="{BASE}/{quote(collection["preview"])}" alt="{escape(title)} overview" loading="lazy" style="max-width:100%;background:#fff">', ''])
        for item in collection.get('downloads', []):
            asset = Path('public') / item['path']
            if not asset.is_file():
                raise ValueError(f'Missing download: {asset}')
            lines.append(f'<p><strong>{escape(item["label"])}</strong> · {escape(item["note"])} · <a download href="{BASE}/{quote(item["path"])}">Download</a></p>')
        if collection.get('downloads'):
            lines.append('')
        groups = {name: [] for name in collection['groups']}
        used = set()
        for row in collection['blocks']:
            code, filename = row['code'], row['file']
            if not code.strip() or code.casefold() in used or Path(filename).name != filename or not filename.lower().endswith('.dwg'):
                raise ValueError(f'Invalid block in {route}: {row}')
            used.add(code.casefold())
            asset = Path('downloads') / route / filename
            with (Path('public') / asset).open('rb') as drawing:
                if not drawing.read(6).startswith(b'AC10'):
                    raise ValueError(f'Invalid DWG: {asset}')
            size = row.get('size')
            label = row['name'] + (f' · {size[0]:g} × {size[1]:g} ft' if size else '') + (f' · {row["dynamic"]}' if row.get('dynamic') else '')
            preview = Path('block-previews') / route / (Path(filename).stem + '.svg')
            if not (Path('public') / preview).is_file():
                raise ValueError(f'Missing preview picture: {preview} (run pipeline/block_previews.py)')
            groups[row['group']].append((code, label, asset, preview, row.get('placement', '')))
        if not used:
            lines.append('No DWG blocks have been published yet. Browse the design references below.')
        for group, rows in groups.items():
            if not rows:
                continue
            lines.extend(['', '## ' + group, '', '<div class="block-grid">'])
            for code, name, asset, preview, place in sorted(rows):
                href = f'{BASE}/{quote(asset.as_posix())}'
                lines.append(f'<figure class="block-card" id="{escape(code.lower())}" data-place="{escape(place, quote=True)}"><a class="block-zoom" href="{BASE}/{quote(preview.as_posix())}" aria-label="View {escape(code)} larger">'
                             f'<img src="{BASE}/{quote(preview.as_posix())}" alt="{escape(name)}" loading="lazy" decoding="async"></a>'
                             f'<figcaption><strong>{escape(name.split(" · ")[0])}</strong><span class="block-code">{escape(code)}</span>' +
                             f'<span class="block-actions"><button type="button" data-block-add="{escape(code)}">Add</button>'
                             f'<a download href="{href}">DWG</a></span></figcaption></figure>')
            lines.append('</div>')
        lines.extend(['', '## Design references', ''])
        for name, path in collection['references'].items():
            url = path if path.startswith('https://') else f'{BASE}/{path}'
            lines.append(f'- [{name}]({url})')
        page.write_text('\n'.join(lines)+'\n')
        lookup.setdefault(title.upper(), []).append([title, href])
