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
            groups[row['group']].append((code, row['name'], asset))
        if not used:
            lines.append('No DWG blocks have been published yet. Browse the design references below.')
        for group, rows in groups.items():
            if rows:
                lines.extend(['', '## ' + group, ''])
            for code, name, asset in sorted(rows):
                lines.append(f'<p><strong>{escape(code)}</strong> · {escape(name)} · <a download href="{BASE}/{quote(asset.as_posix())}">Download DWG</a></p>')
        lines.extend(['', '## Design references', ''])
        for name, path in collection['references'].items():
            url = path if path.startswith('https://') else f'{BASE}/{path}'
            lines.append(f'- [{name}]({url})')
        page.write_text('\n'.join(lines)+'\n')
        lookup.setdefault(title.upper(), []).append([title, href])
