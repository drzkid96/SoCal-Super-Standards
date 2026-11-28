"""Fail when a sign name carries unread legend text: letters spaced apart, times run together, split words.

  python3 pipeline/check_sign_names.py
"""
import json
import re
from pathlib import Path

GARBLED = re.compile(r'(?:\b[A-Za-z]\b\s){3}|\d(?:Am|Pm)\b|\bTo\d|\bMp H\b|\b(?:Pla|Ow|Rth|Outh|Ast|Est)\b')


def main():
    rows = json.loads(Path('data/signs/signs.json').read_text())
    rows = rows if isinstance(rows, list) else list(rows.values())
    bad = [(r['code'], r['name']) for r in rows if GARBLED.search(r.get('name') or '')]
    for code, name in bad:
        print(f'{code}: {name}')
    print(f'{len(rows)} sign names, {len(bad)} garbled')
    return bool(bad)


if __name__ == '__main__':
    raise SystemExit(main())
