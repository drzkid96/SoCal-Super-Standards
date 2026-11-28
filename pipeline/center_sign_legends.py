"""Center sign legend lines on their face.

Library sign faces were drawn with their text lines slightly off the face center line. A line is a
horizontal band of legend geometry; it is moved only when the band reads as text (several letters of even
height, no arrow or symbol beside it), is not set inside an arrow or panel, sits clear of the border,
and is off center by more than 2% of the face.

  python pipeline/center_sign_legends.py [--write]   (rewrites data/reference/cad-sign-entities.zip.*)
"""
import argparse
import gzip
import hashlib
import io
import json
import sys
from pathlib import Path

import ezdxf
from ezdxf import bbox, path as epath
from ezdxf.lldxf.tagwriter import TagWriter

sys.path.insert(0, str(Path(__file__).parent))
from sign_cells import parse_fragment  # noqa: E402

TOL = 0.02      # share of face width that counts as off center
EDGE = 0.06     # share of face width a centered line keeps clear of the face edge
SKIP = {'W14-3'}  # pennant: its legend is set in the wide end, not on the shape's center
GAP = 0.6       # a horizontal gap wider than this share of the line height splits a line


def boxes(doc):
    out = []
    for e in doc.modelspace():
        b = bbox.extents([e], fast=True)
        if b.has_data:
            out.append((e, b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y))
    return out


def components(row):
    """Overlapping boxes merged: one box per letter or symbol part."""
    comps = []
    for b in sorted(row, key=lambda b: b[1]):
        for c in comps:
            if b[1] <= c[2] and b[3] >= c[0] and b[2] <= c[3] and b[4] >= c[1]:
                c[0], c[1], c[2], c[3] = min(c[0], b[1]), min(c[1], b[2]), max(c[2], b[3]), max(c[3], b[4])
                c[4].append(b)
                break
        else:
            comps.append([b[1], b[2], b[3], b[4], [b]])
    changed = True
    while changed:
        changed = False
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                c, d = comps[i], comps[j]
                if c[0] <= d[2] and c[2] >= d[0] and c[1] <= d[3] and c[3] >= d[1]:
                    c[0], c[1], c[2], c[3] = min(c[0], d[0]), min(c[1], d[1]), max(c[2], d[2]), max(c[3], d[3])
                    c[4] += d[4]
                    del comps[j]
                    changed = True
                    break
            if changed:
                break
    return comps


def is_text(comps, h):
    """Several letter-sized parts of even height: a line of text, not a symbol or arrow."""
    if len(comps) < 2:
        return False
    hs = sorted(c[3] - c[1] for c in comps)
    med = hs[len(hs) // 2]
    even = sum(1 for x in hs if abs(x - med) <= 0.2 * med) / len(hs)
    narrow = all((c[2] - c[0]) <= 1.6 * med for c in comps)
    return even >= 0.75 and narrow and med >= 0.8 * h


def plan(doc, bounds):
    """Lines to move: list of (entities, dx)."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    cx = (x0 + x1) / 2
    every = boxes(doc)
    frame = lambda b: (b[3] - b[1]) > 0.6 * W and (b[4] - b[2]) > 0.6 * H
    edge = lambda b: (b[3] < x0 + EDGE * W or b[1] > x1 - EDGE * W
                      or b[4] < y0 + 0.04 * H or b[2] > y1 - 0.04 * H)
    border = lambda b: (b[3] - b[1]) > 0.6 * W or (b[4] - b[2]) > 0.6 * H or edge(b)
    items = sorted((b for b in every if not frame(b) and not border(b)), key=lambda b: b[2])
    rows, cur, top = [], [], None
    for b in items:
        if cur and b[2] > top + 0.01 * H:
            rows.append(cur)
            cur, top = [], None
        cur.append(b)
        top = b[4] if top is None else max(top, b[4])
    if cur:
        rows.append(cur)
    holes = []                            # shaped openings in a dark field, such as the white arrow of ONE WAY
    for b in every:
        if b[0].dxftype() == 'HATCH' and frame(b):
            for path in epath.from_hatch(b[0]):
                pts = list(path.flattening(0.01 * W))
                if len(pts) < 3:
                    continue
                px0, px1 = min(v.x for v in pts), max(v.x for v in pts)
                py0, py1 = min(v.y for v in pts), max(v.y for v in pts)
                if px1 - px0 >= 0.97 * (b[3] - b[1]):
                    continue                  # the outline of the field itself
                area = abs(sum(a.x * q.y - q.x * a.y for a, q in zip(pts, pts[1:] + pts[:1]))) / 2
                square = area / max((px1 - px0) * (py1 - py0), 1e-12)
                panel = px1 - px0 > 0.85 * (b[3] - b[1]) and py1 - py0 > 0.7 * (b[4] - b[2]) and square > 0.9
                if not panel:
                    holes.append((px0, py0, px1, py1))
    ink = {}
    for b in every:
        try:
            paths = list(epath.from_hatch(b[0])) if b[0].dxftype() == 'HATCH' else [epath.make_path(b[0])]
        except Exception:
            paths = []
        pts, step = [], 0.004 * W
        for q in paths:
            vs = list(q.flattening(step))
            for u, v in zip(vs, vs[1:]):
                n = max(1, int(((v.x - u.x) ** 2 + (v.y - u.y) ** 2) ** 0.5 / step))
                pts += [(u.x + (v.x - u.x) * t / n, u.y + (v.y - u.y) * t / n) for t in range(n)]
            pts += [(v.x, v.y) for v in vs[-1:]]
        ink[id(b[0])] = pts

    def clear(row, a, c, d, e, strict):
        """No line work of other shapes inside the box (shrunk by 1% of the face); None when unknown."""
        m = 0.01 * W
        mine = {id(b[0]) for b in row}
        for b in every:
            if id(b[0]) in mine:
                continue
            if any(a + m < x < d - m and c + m < y < e - m for x, y in ink[id(b[0])]):
                return False
        return True

    moves = []
    for row in rows:
        lx, ly = min(b[1] for b in row), min(b[2] for b in row)
        rx, ry = max(b[3] for b in row), max(b[4] for b in row)
        h = ry - ly
        comps = components(row)
        if not is_text(comps, h):
            continue
        comps.sort(key=lambda c: c[0])
        if any(d[0] - c[2] > GAP * h for c, d in zip(comps, comps[1:])):
            continue                      # two groups on one line (text beside an arrow or a time range)
        mid_x = (lx + rx) / 2
        if lx - x0 < EDGE * W or x1 - rx < EDGE * W:
            continue
        inside = [b for b in every if b not in row and not ((b[3] - b[1]) > 0.9 * W and (b[4] - b[2]) > 0.9 * H)
                  and b[1] <= lx and b[3] >= rx and b[2] <= ly and b[4] >= ry]
        if inside:
            continue                      # text set inside an arrow or a panel keeps its place
        if any(b not in row and not frame(b) and not edge(b) and (b[3] - b[1]) < 0.9 * W and b[1] < rx and b[3] > lx and b[2] < ry and b[4] > ly
               for b in every):
            continue                      # text that wraps around or touches a symbol keeps its place
        mid = (ly + ry) / 2
        if any(b not in row and not frame(b) and (b[3] - b[1]) > 0.5 * W and b[2] < mid < b[4] for b in every):
            continue                      # text on an arrow shaft or a panel made of several parts
        if any(hx0 < mid_x < hx1 and hy0 < (ly + ry) / 2 < hy1 for hx0, hy0, hx1, hy1 in holes):
            continue                      # text in a shaped cut-out of a dark field (an arrow)
        dx = cx - (lx + rx) / 2
        if any(b not in row and not frame(b) and not edge(b) and (b[3] - b[1]) < 0.9 * W
               and b[1] < rx + dx and b[3] > lx + dx and b[2] < ry and b[4] > ly for b in every):
            continue                      # the centered line would land on another shape
        if abs(dx) > TOL * W and (clear(row, lx, ly, rx, ry, 0) is False or not clear(row, lx + dx, ly, rx + dx, ry, 1)):
            continue                      # line work of a border, divider or panel inside the line's box
        if abs(dx) > TOL * W:
            moves.append(([b[0] for b in row], dx, (lx + rx) / 2, id(row)))
    # a line centered on another off-center group (a column beside an arrow or a word) stays with it
    anchors = []
    for row in rows:
        if any(m[3] == id(row) for m in moves):
            continue
        h = max(b[4] for b in row) - min(b[2] for b in row)
        groups, cur = [], []
        for b in sorted(row, key=lambda b: b[1]):
            if cur and b[1] - max(x[3] for x in cur) > GAP * h:
                groups.append(cur)
                cur = []
            cur.append(b)
        if cur:
            groups.append(cur)
        for g in groups:
            gx = (min(b[1] for b in g) + max(b[3] for b in g)) / 2
            if abs(gx - cx) > TOL * W:
                anchors.append(gx)
    return [(e, dx) for e, dx, mx, _ in moves if not any(abs(mx - a) < TOL * W for a in anchors)]


def fragment(doc):
    """Entities back to the handle-free fragment text."""
    s = io.StringIO()
    w = TagWriter(s, dxfversion='AC1015')
    for e in doc.modelspace():
        e.export_dxf(w)
    pairs = s.getvalue().strip('\n').split('\n')
    out, i, skip = [], 0, 0
    while i < len(pairs) - 1:
        code, val = pairs[i].strip(), pairs[i + 1]
        if code == '102':
            skip = 1 if val.startswith('{') else 0
        elif not skip and code not in ('5', '330'):
            out += [code, val.strip()]
        i += 2
    return '\n'.join(out) + '\n'


def run(write=False):
    """Center the legend lines in the browser CAD geometry archive; returns {id: [shift share of width]}."""
    from cad_blocks.web_entities import SOURCE, open_archive, write_member, write_parts
    import zipfile
    with open_archive(SOURCE) as bundle:
        index = json.loads(bundle.read('index.json'))
        members = {n: bundle.read(n) for n in bundle.namelist()}
    changed = {}
    for key, entry in index.items():
        if entry.get('name', '').split(' ')[0] in SKIP:
            continue
        doc = parse_fragment(gzip.decompress(members[key + '.dxf.gz']).decode())
        moves = plan(doc, entry['bounds'])
        if not moves:
            continue
        for ents, dx in moves:
            for e in ents:
                e.translate(dx, 0, 0)
        changed[key] = [round(dx / (entry['bounds'][2] - entry['bounds'][0]), 3) for _, dx in moves]
        data = gzip.compress(fragment(doc).encode(), compresslevel=8, mtime=0)
        members[key + '.dxf.gz'] = data
        entry.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    if write and changed:
        temp = SOURCE.with_suffix('.tmp')
        with zipfile.ZipFile(temp, 'w') as out:
            for key in index:
                write_member(out, key + '.dxf.gz', members[key + '.dxf.gz'], zipfile.ZIP_STORED)
            data = json.dumps(index, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
            write_member(out, 'index.json', data, zipfile.ZIP_DEFLATED)
        write_parts(temp, SOURCE)
        temp.unlink()
    return changed


def render(doc, bounds, size):
    """Black on white picture of a face, even-odd fills, drawn at 4x and reduced to the preview size."""
    from PIL import Image, ImageChops, ImageDraw
    x0, y0, x1, y1 = bounds
    w, h = size
    k = 4
    pad = 4 * k
    s = min((w * k - 2 * pad) / (x1 - x0), (h * k - 2 * pad) / (y1 - y0))
    ox = (w * k - (x1 - x0) * s) / 2
    oy = (h * k - (y1 - y0) * s) / 2
    tf = lambda q: (ox + (q.x - x0) * s, h * k - oy - (q.y - y0) * s)
    ink = Image.new('1', (w * k, h * k), 0)
    for e in doc.modelspace():
        if e.dxftype() == 'HATCH':
            m = Image.new('1', ink.size, 0)
            for q in epath.from_hatch(e):
                pts = [tf(v) for v in q.flattening(0.5 / s)]
                if len(pts) > 2:
                    t = Image.new('1', ink.size, 0)
                    ImageDraw.Draw(t).polygon(pts, fill=1)
                    m = ImageChops.logical_xor(m, t)
            ink = ImageChops.logical_or(ink, m)
        else:
            try:
                pts = [tf(v) for v in epath.make_path(e).flattening(0.5 / s)]
            except Exception:
                continue
            if len(pts) > 1:
                ImageDraw.Draw(ink).line(pts, fill=1, width=k)
    img = Image.new('L', ink.size, 255)
    img.paste(0, mask=ink)
    return img.resize((w, h), Image.LANCZOS).convert('RGB')


def refresh_previews(ids):
    """Redraw the previews of the given faces in the family archives and repin manifest and release."""
    import zipfile
    from PIL import Image
    import speed_faces
    from cad_block_package import SOURCE, INDEX, preview_path, family_of, member, pin, sha
    from cad_blocks.web_entities import SOURCE as GEOMETRY, open_archive
    release = json.loads((SOURCE / 'release.json').read_text())
    manifest = json.loads((SOURCE / INDEX).read_text())
    with open_archive(GEOMETRY) as bundle:
        index = json.loads(bundle.read('index.json'))
        frags = {k: bundle.read(k + '.dxf.gz') for k in ids}
    recs = {r['id']: r for r in manifest['records'] if r['id'] in ids and r.get('preview') and not speed_faces.value(r)}
    by_family = {}
    for r in recs.values():
        by_family.setdefault(family_of(r), []).append(r)
    for part in release['families']:
        todo = by_family.get(part['family'])
        if not todo:
            continue
        path = SOURCE / part['file']
        with zipfile.ZipFile(path) as old:
            members = [(i.filename, old.read(i.filename)) for i in old.infolist()]
        new = {}
        for r in todo:
            name = preview_path(r)[1]
            old_img = Image.open(io.BytesIO(dict(members)[name]))
            doc = parse_fragment(gzip.decompress(frags[r['id']]).decode())
            buf = io.BytesIO()
            render(doc, index[r['id']]['bounds'], old_img.size).save(buf, 'WEBP', quality=90, method=6)
            new[name] = buf.getvalue()
            r.update(previewBytes=len(new[name]), previewSha256=sha(new[name]))
        temp = path.with_suffix('.tmp')
        with zipfile.ZipFile(temp, 'w') as out:
            for name, data in members:
                member(out, name, new.get(name, data))
        temp.replace(path)
        part.update(pin(path))
    (SOURCE / INDEX).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    if 'manifest' in release:
        release['manifest'].update(pin(SOURCE / INDEX))
    (SOURCE / 'release.json').write_text(json.dumps(release, ensure_ascii=False, indent=2) + '\n')
    return len(recs)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    c = run(a.write)
    print(json.dumps(c))
    print(len(c), 'faces with lines moved,', sum(len(v) for v in c.values()), 'lines', file=sys.stderr)
