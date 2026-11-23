"""Restore the reviewed BOE text and catalog for clean, offline builds."""
from pathlib import Path
from zipfile import ZipFile
import json

SNAPSHOT=Path('data/reference/boe-street-design.zip')
CATALOG=Path('public/data/boe-sections.json')
PREFIX='src/content/docs/boe/street-design/'


def restore(target, catalog=CATALOG):
    with ZipFile(SNAPSHOT) as archive:
        expected=json.loads(archive.read('public/data/boe-sections.json'))
        if len(expected)<50:raise ValueError('Incomplete BOE snapshot')
        pages={name.removeprefix(PREFIX):name for name in archive.namelist() if name.startswith(PREFIX) and name.endswith('.md')}
        if len(pages)!=len(expected)+1:raise ValueError('BOE snapshot catalog disagrees with page count')
        target.mkdir(parents=True,exist_ok=True)
        for filename,member in pages.items():
            if Path(filename).name!=filename:raise ValueError('Unexpected BOE page path')
            (target/filename).write_bytes(archive.read(member))
        catalog.parent.mkdir(parents=True,exist_ok=True)
        catalog.write_bytes(archive.read('public/data/boe-sections.json'))
