"""Publish optional local street evidence separately from regional HPMS ownership."""
import argparse
import gzip
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from sources import CACHE, OUTPUT, arc_features, get

PASADENA = 'https://services2.arcgis.com/zNjnZafDYCAJAbN0/arcgis/rest/services/Streets/FeatureServer/1'
PASADENA_ITEM = 'https://www.arcgis.com/home/item.html?id=f97f292f02134450b790653e7cc5dc23'
SOURCE_KEY = 'pasadena-streets'
SNAPSHOT = Path('data/reference/atlas/pasadena-streets.geojson.gz')


def write_json(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, separators=(',', ':'), ensure_ascii=False, allow_nan=False))
    temporary.replace(path)


def prepare(features, edited):
    paths = []
    identifiers = set()
    west, south, east, north = 180, 90, -180, -90
    for feature in sorted(features, key=lambda row: row['properties']['OBJECTID']):
        row = feature['properties']
        name = row['FULL_ST_NAME'].strip()
        uid = row['GlobalID'].strip('{}').lower()
        if not uid or uid in identifiers or not name:
            raise ValueError(f'Invalid street name or identifier at object {row["OBJECTID"]}')
        identifiers.add(uid)
        geometry = feature['geometry']
        if not geometry or geometry['type'] not in {'MultiLineString', 'LineString'}:
            raise ValueError(f'Missing street geometry at object {row["OBJECTID"]}')
        lines = geometry['coordinates'] if geometry['type'] == 'MultiLineString' else [geometry['coordinates']]
        for part, line in enumerate(lines):
            if len(line) < 2:
                raise ValueError(f'Invalid street path at object {row["OBJECTID"]}')
            for lon, lat in line:
                if not math.isfinite(lon) or not math.isfinite(lat) or not (-119 < lon < -117 and 33 < lat < 35):
                    raise ValueError(f'Invalid Pasadena coordinates at object {row["OBJECTID"]}')
                west, south = min(west, lon), min(south, lat)
                east, north = max(east, lon), max(north, lat)
            paths.append({
                'type': 'Feature', 'id': f'{uid}.{part}' if len(lines) > 1 else uid,
                'properties': {'name': name, 'agency': 'City of Pasadena', 'source': SOURCE_KEY,
                               'role': 'inventory', 'classification': row['LABEL'], 'ref': row['OBJECTID']},
                'geometry': {'type': 'LineString', 'coordinates': line}
            })
    if not paths:
        raise ValueError('The Pasadena street inventory is empty')
    source = {
        'title': 'City of Pasadena GIS · Streets', 'url': PASADENA, 'catalog': PASADENA_ITEM,
        'publisher': 'City of Pasadena', 'sourceEdited': edited, 'role': 'inventory',
        'verificationUrl': 'https://www.cityofpasadena.net/public-works/engineering-and-construction/public-works-permitting/',
        'privateStreetsUrl': 'https://www.cityofpasadena.net/wp-content/uploads/sites/29/List-of-Private-Streets-in-Pasadena.pdf',
        'scope': 'Named centerlines flagged in-city by the publisher. Street classification comes from its LABEL field.'
    }
    return {'type': 'FeatureCollection', 'features': paths}, {
        'file': 'road-context.geojson', 'bbox': [west, south, east, north], 'count': len(paths),
        'sources': {SOURCE_KEY: source}
    }


def refresh():
    """Refresh the reviewed source snapshot only when explicitly requested."""
    # Use the publisher revision as a cache key so a build cannot mix source editions.
    def revision():
        info = json.loads(get(PASADENA + '?f=json')[0])
        return int(info['editingInfo']['dataLastEditDate'])
    stamp = revision()
    features = arc_features(f'pasadena-streets-{stamp}', PASADENA, 'GlobalID,FULL_ST_NAME,LABEL',
                            "IN_CITY_NY = 'Y' AND FULL_ST_NAME IS NOT NULL", generalize=.000006, chunk=250)
    if revision() != stamp:
        (CACHE / f'pasadena-streets-{stamp}.geojson').unlink(missing_ok=True)
        raise RuntimeError('The source changed during the Pasadena street export. Rebuild the current edition.')
    edited = datetime.fromtimestamp(stamp / 1000, timezone.utc).date().isoformat()
    prepare(features, edited)
    release = {'type': 'FeatureCollection', 'publisherLayer': PASADENA, 'sourceEdited': edited, 'features': features}
    raw = json.dumps(release, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    temporary = SNAPSHOT.with_suffix('.tmp')
    temporary.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    temporary.replace(SNAPSHOT)


def publish():
    with gzip.open(SNAPSHOT, 'rt') as source:
        release = json.load(source)
    if release['publisherLayer'] != PASADENA:
        raise ValueError('Unexpected Pasadena inventory source')
    data, spec = prepare(release['features'], release['sourceEdited'])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / spec['file']
    write_json(path, data)
    spec['bytes'] = path.stat().st_size
    compressed = path.with_suffix('.geojson.gz')
    temporary = compressed.with_suffix('.tmp')
    temporary.write_bytes(gzip.compress(path.read_bytes(), compresslevel=9, mtime=0))
    temporary.replace(compressed)
    spec['compressedFile'] = compressed.name
    spec['compressedBytes'] = compressed.stat().st_size
    write_json(OUTPUT / 'road-context.json', spec)
    print(f"Pasadena street inventory: {spec['count']:,} centerlines", flush=True)
    return spec


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Download and validate a new publisher snapshot')
    if parser.parse_args().refresh:
        refresh()
    publish()
