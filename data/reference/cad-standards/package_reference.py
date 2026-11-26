"""Build the portable size-reference ZIP from the repository's verified index."""
import argparse
import gzip
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

BASE=Path(__file__).resolve().parent
NAME='CA-FHWA-SIGN-STANDARDS-REFERENCE.zip'

def package(destination):
    source=BASE/'sign-standards.json.gz'
    raw = gzip.decompress(source.read_bytes()) if source.exists() else (BASE/'sign-standards.json').read_bytes()
    data=json.loads(raw)
    rows=data['tableRows']
    assert {r['publisher'] for r in rows.values()}=={'Caltrans','FHWA'}
    members={'README.md':(BASE/'README.md').read_bytes(),'sign-standards.json':raw,
             'lookup.py':(BASE/'lookup.py').read_bytes(),'sources/retrieval.json':(BASE/'sources/retrieval.json').read_bytes()}
    with ZipFile(destination,'w') as out:
        for name,contents in members.items():
            entry=ZipInfo(name,(1980,1,1,0,0,0))
            entry.external_attr=0o100644<<16
            out.writestr(entry,contents,compress_type=ZIP_DEFLATED,compresslevel=9)
    with ZipFile(destination) as check:
        assert check.testzip() is None
        assert check.read('sign-standards.json')==raw
    print(f'{destination} ({destination.stat().st_size:,} bytes)')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path,nargs='?',default=Path(NAME))
    package(parser.parse_args().destination)
