"""Large-download store: keeps big download-only files off GitHub Pages.

GitHub Pages serves at most 1 GB. Large files that are only ever downloaded (bundles, master
drawings, library drawings) are published as assets of one GitHub Release instead (2 GB per
file, no total limit), and every link to them in the built site points at the release.

Rules live in data/reference/asset-store.json:
  release   tag of the store release
  minBytes  files under dist/downloads/ at or above this size move to the store
  keep      site paths that always stay on Pages (for example files fetched by page scripts)
  names     site path -> asset name (the file name the user receives); default is the file name

Run after the site is built and tested:
  python pipeline/asset_store.py            # plan only: rewrite links, remove files from dist
  python pipeline/asset_store.py --upload   # also upload new or changed assets (main branch)
Uploads need GITHUB_TOKEN with contents: write and GITHUB_REPOSITORY.
The plan is written to dist/data/asset-store.json (site path, asset url, bytes, sha256).
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from current_catalog import BASE

DIST = Path('dist')
RULES = Path('data/reference/asset-store.json')
TEXT = {'.html', '.js', '.json', '.xml', '.txt', '.css'}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def plan(rules, repo):
    entries, names = [], {}
    for path in sorted((DIST / 'downloads').rglob('*')):
        if not path.is_file():
            continue
        site = path.relative_to(DIST).as_posix()
        size = path.stat().st_size
        if size < rules['minBytes'] or site in rules.get('keep', []):
            continue
        name = rules.get('names', {}).get(site, path.name)
        if name in names:
            raise SystemExit(f'Asset name {name} is used by {names[name]} and {site}; add a names entry')
        names[name] = site
        url = f'https://github.com/{repo}/releases/download/{rules["release"]}/{urllib.parse.quote(name)}'
        entries.append(dict(site=site, name=name, url=url, bytes=size, sha256=sha(path)))
    return entries


def rewrite(entries):
    swaps = {}
    for e in entries:
        local = f'{BASE}/{e["site"]}'
        swaps[local] = e['url']
        swaps[f'{BASE}/{urllib.parse.quote(e["site"])}'] = e['url']
    changed = 0
    for path in DIST.rglob('*'):
        if path.suffix not in TEXT or not path.is_file():
            continue
        text = path.read_text(errors='surrogateescape')
        new = text
        for local, url in swaps.items():
            if local in new:
                new = new.replace(f'"{local}"', f'"{url}"').replace(f"'{local}'", f"'{url}'")
        if new != text:
            path.write_text(new, errors='surrogateescape')
            changed += 1
    return changed


def api(method, url, token, data=None, kind='application/json'):
    req = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': kind})
    with urllib.request.urlopen(req, timeout=600) as r:
        body = r.read()
    return json.loads(body) if body else None


def upload(entries, rules, repo, token):
    root = f'https://api.github.com/repos/{repo}'
    tag = rules['release']
    try:
        release = api('GET', f'{root}/releases/tags/{tag}', token)
    except urllib.error.HTTPError as err:
        if err.code != 404:
            raise
        release = api('POST', f'{root}/releases', token, json.dumps(dict(
            tag_name=tag, name='Download store', make_latest='false',
            body='Large downloads for the SoCal Super Standards site. Managed by pipeline/asset_store.py.')).encode())
    assets, page = [], 1
    while True:
        batch = api('GET', f'{root}/releases/{release["id"]}/assets?per_page=100&page={page}', token)
        assets += batch
        if len(batch) < 100:
            break
        page += 1
    current = {a['name']: a for a in assets}
    target = release['upload_url'].split('{')[0]
    sent = 0
    for e in entries:
        have = current.get(e['name'])
        if have and have.get('digest') == 'sha256:' + e['sha256']:
            continue
        if have and not have.get('digest') and have['size'] == e['bytes']:
            continue
        temp = 'incoming-' + e['sha256'][:12] + '-' + e['name']
        if temp in current:
            api('DELETE', f'{root}/releases/assets/{current[temp]["id"]}', token)
        data = (DIST / e['site']).read_bytes()
        new = api('POST', f'{target}?name={urllib.parse.quote(temp)}', token, data, 'application/octet-stream')
        if have:
            api('DELETE', f'{root}/releases/assets/{have["id"]}', token)
        api('PATCH', f'{root}/releases/assets/{new["id"]}', token, json.dumps({'name': e['name']}).encode())
        sent += 1
        print(f'  uploaded {e["name"]} ({e["bytes"]:,} bytes)')
    return sent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--upload', action='store_true')
    args = ap.parse_args()
    rules = json.loads(RULES.read_text())
    repo = os.environ.get('GITHUB_REPOSITORY', rules.get('repository', ''))
    entries = plan(rules, repo)
    if args.upload:
        token = os.environ.get('GITHUB_TOKEN')
        if not token:
            sys.exit('GITHUB_TOKEN is required for --upload')
        print(f'Store: {upload(entries, rules, repo, token)} asset(s) uploaded')
    changed = rewrite(entries)
    for e in entries:
        (DIST / e['site']).unlink()
    out = DIST / 'data/asset-store.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(release=rules['release'], assets=entries), indent=1) + '\n')
    moved = sum(e['bytes'] for e in entries)
    print(f'Store: {len(entries)} file(s), {moved:,} bytes moved off Pages; links rewritten in {changed} file(s)')


if __name__ == '__main__':
    main()
