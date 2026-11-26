"""Compile the small inline home map from the same boundaries as the geographic index."""
import json
import math
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import unary_union

from sources import OUTPUT

# Equirectangular projection for a small regional map centered around 34° N.
ANGLE = math.cos(math.radians(34))
LABELS = {
    '025': (-115.4, 33.05), '037': (-118.12, 34.49), '059': (-117.72, 33.69),
    '065': (-115.76, 33.71), '071': (-116.15, 34.76), '073': (-116.75, 33.03),
    '111': (-119.18, 34.55),
}


def compile_home_map():
    def load(path):
        return json.loads(path.read_text())

    def polygon(feature):
        geometry = shape(feature['geometry'])
        return geometry if geometry.is_valid else geometry.buffer(0)

    land = polygon(load(Path('public/js/atlas/land.geojson')))
    counties = load(OUTPUT / 'counties.geojson')['features']
    cities = load(OUTPUT / 'municipalities.geojson')['features']
    codes = {p['id']:p['county'] for p in load(OUTPUT / 'places.json') if p['kind']=='city'}
    county_shapes = {f['properties']['county']:polygon(f).intersection(land) for f in counties}
    west, south, east, north = unary_union(list(county_shapes.values())).bounds
    scale = 356 / ((east - west) * ANGLE)

    def project(lon, lat):
        return round(2 + (lon - west) * ANGLE * scale), round(2 + (north - lat) * scale)

    def path(geometry):
        rings = []
        def add_polygons(part):
            if part.is_empty:
                return
            if part.geom_type in ('MultiPolygon', 'GeometryCollection'):
                for item in part.geoms:
                    add_polygons(item)
                return
            if part.geom_type != 'Polygon' or part.area * scale**2 * ANGLE < 0.6:
                return
            for ring in [part.exterior, *part.interiors]:
                points = []
                for lon, lat in ring.coords:
                    point = project(lon, lat)
                    if not points or points[-1] != point:
                        points.append(point)
                if points and points[-1] == points[0]:
                    points.pop()
                if len(points) > 2:
                    rings.append('M' + ' '.join(f'{x},{y}' for x,y in points) + 'Z')
        add_polygons(geometry.simplify(0.005, preserve_topology=True))
        return ''.join(rings)

    result = {'viewBox': f'0 0 360 {project(east, south)[1]+2}', 'counties': []}
    for f in counties:
        code = f['properties']['county']
        selected = [polygon(c) for c in cities if codes[c['properties']['id']] == code]
        result['counties'].append({
            'code': code, 'name': f['properties']['name'], 'label': project(*LABELS[code]),
            'boundary': path(county_shapes[code]),
            'cities': path(unary_union(selected).intersection(county_shapes[code])),
        })
    (OUTPUT / 'home-map.json').write_text(json.dumps(result, separators=(',', ':')) + '\n')
    return result


if __name__ == '__main__':
    compile_home_map()
