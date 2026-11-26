"""Attach reviewed city portal citations to the geographic place index."""
import json
from pathlib import Path
from urllib.parse import urlsplit

ROSTER = 'https://admin.cdn.sos.ca.gov/ca-roster/2026/cities-towns.pdf'
PORTALS = Path('data/reference/atlas/municipal-portals.json')

def attach_municipal_portals(places):
    record = json.loads(PORTALS.read_text())
    cities = {item['id']:item for item in places if item['kind']=='city'}
    if set(cities) != set(record['cities']):
        raise ValueError('Municipality boundaries and official portal coverage differ')
    for geoid, place in cities.items():
        entry = record['cities'][geoid]
        if (place['name'],place['county']) != (entry['name'],entry['county']):
            raise ValueError(f'Municipality identity changed for {geoid}')
        page = entry['page']
        if not isinstance(page,int) or not 1 <= page <= record['pages']:
            raise ValueError(f'Invalid source page for {geoid}')
        url = urlsplit(entry['url'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError(f'Invalid municipal portal for {geoid}')
        place['official'] = entry['url']
        place['directorySource'] = entry.get('source', f'{ROSTER}#page={page}')


def home_map_card(base, api):
    """Render the municipality picker and linked county map as static homepage markup."""
    from html import escape

    diagram = json.loads((api / 'home-map.json').read_text())
    places = json.loads((api / 'places.json').read_text())
    geography_url = base + '/map/'
    shapes = []
    groups = []
    for county in diagram['counties']:
        code, name = county['code'], escape(county['name'])
        x, y = county['label']
        shapes.append(
            f'<a href="{geography_url}?county={code}" aria-label="{name} County">'
            f'<title>{name} County</title><path class="county-area" d="{county["boundary"]}"/>'
            f'<path class="municipal-area" d="{county["cities"]}"/>'
            f'<text x="{x}" y="{y}">{name}</text></a>'
        )
        members = [p for p in places if p['kind']=='city' and p['county']==code]
        names = [(('Ventura (San Buenaventura)' if p['name']=='San Buenaventura' else p['name']), p['id']) for p in members]
        options = ''.join(f'<option value="{geoid}">{escape(title)}</option>' for title,geoid in sorted(names))
        groups.append(f'<optgroup label="{name} County">{options}</optgroup>')
    return (
        '<section class="home-column home-map"><h2>Municipalities</h2>'
        f'<svg viewBox="{diagram["viewBox"]}" role="group" aria-label="Browse seven counties. Dark green shows incorporated cities.">'
        + ''.join(shapes) + '</svg>'
        '<span class="home-map-key">Incorporated cities</span>'
        f'<form class="home-city-picker" action="{geography_url}" method="get">'
        '<select name="city" required aria-label="Choose a municipality"><option value="">Select city</option>'
        + ''.join(groups) + '</select><button type="submit">Open</button></form>'
        f'<a href="{geography_url}">Browse the municipal standards map →</a></section>'
    )
