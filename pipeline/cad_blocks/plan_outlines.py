"""Marking outlines traced from Caltrans Standard Plan sheets (vector PDF).

Each figure on a marking sheet sits on its own fine grid (0.12 pt lines) with a "<n> GRID" note.
A figure is the set of outline strokes inside one grid region. Strokes are chained into loops,
small gaps (up to one grid cell) are closed, and coordinates are scaled by the region's grid
spacing and its stated grid size, so the output is true size in feet.

Caltrans marking sheets are rotated 270 degrees, so the visual up direction is +x of the
unrotated frame. figures() returns points turned to the visual frame (x right, y up).
"""
import collections
import math
import re

import pymupdf as fitz

GRID_WIDTH = 0.12


def _bezier(p0, c1, c2, p3, n=10):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        out.append((a * p0.x + b * c1.x + c * c2.x + e * p3.x, a * p0.y + b * c1.y + c * c2.y + e * p3.y))
    return out


def segments(drawing):
    """Polylines (lists of points) for one PyMuPDF drawing."""
    out = []
    for it in drawing['items']:
        k = it[0]
        if k == 'l':
            out.append([(it[1].x, it[1].y), (it[2].x, it[2].y)])
        elif k == 'c':
            out.append(_bezier(*it[1:5]))
        elif k == 're':
            r = it[1]
            out.append([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)])
        elif k == 'qu':
            q = it[1]
            out.append([(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y), (q.ul.x, q.ul.y)])
    return out


def chain(segs, tol):
    """Join polylines end to end at their nearest free ends."""
    pending = [list(s) for s in segs if len(s) > 1]
    dist = lambda a, b: math.hypot(a[0] - b[0], a[1] - b[1])
    loops = []
    while pending:
        cur = pending.pop()
        while True:
            best = None
            for i, s in enumerate(pending):
                for d, kind in ((dist(cur[-1], s[0]), 0), (dist(cur[-1], s[-1]), 1), (dist(cur[0], s[-1]), 2), (dist(cur[0], s[0]), 3)):
                    if d < tol and (best is None or d < best[0]):
                        best = (d, i, kind)
            if not best:
                break
            _, i, kind = best
            s = pending.pop(i)
            cur = cur + s[1:] if kind == 0 else cur + s[::-1][1:] if kind == 1 else s + cur[1:] if kind == 2 else s[::-1] + cur[1:]
        loops.append(cur)
    return loops


def _gap(a, b):
    dx = max(b.x0 - a.x1, a.x0 - b.x1, 0)
    dy = max(b.y0 - a.y1, a.y0 - b.y1, 0)
    return math.hypot(dx, dy)


def _union_find(boxes, tol):
    parent = list(range(len(boxes)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    order = sorted(range(len(boxes)), key=lambda i: boxes[i].x0)
    for n, i in enumerate(order):
        a = boxes[i]
        for j in order[n + 1:]:
            b = boxes[j]
            if b.x0 > a.x1 + tol:
                break
            if b.y0 <= a.y1 + tol and a.y0 <= b.y1 + tol:
                parent[find(i)] = find(j)
    groups = collections.defaultdict(list)
    for i in range(len(boxes)):
        groups[find(i)].append(i)
    return list(groups.values())


def grid_value(text):
    """'4"' -> 0.3333 ft, '1'-0"' -> 1.0 ft."""
    t = text.replace('′', "'").replace('″', '"')
    m = re.fullmatch(r"(?:(\d+)')?-?(?:(\d+)\")?", t)
    if not m or not (m.group(1) or m.group(2)):
        return None
    return int(m.group(1) or 0) + int(m.group(2) or 0) / 12


def feet_text(values):
    """Dimension strings such as 8'-0" or 3'-6" near a figure, in feet."""
    out = []
    for v in values:
        t = v.replace('′', "'").replace('″', '"')
        m = re.fullmatch(r"(\d+)'-(\d+)(½)?\"?", t)
        if m:
            out.append(int(m.group(1)) + (int(m.group(2)) + (0.5 if m.group(3) else 0)) / 12)
    return out


def _grid_step(grid_segs, box):
    """Median spacing of the grid lines that cross a figure's box."""
    xs, ys = set(), set()
    for a, b in grid_segs:
        if not (box.x0 - 2 <= max(a[0], b[0]) and min(a[0], b[0]) <= box.x1 + 2 and box.y0 - 2 <= max(a[1], b[1]) and min(a[1], b[1]) <= box.y1 + 2):
            continue
        if abs(a[0] - b[0]) < 0.05 and abs(a[1] - b[1]) > 2:
            xs.add(round(a[0], 2))
        if abs(a[1] - b[1]) < 0.05 and abs(a[0] - b[0]) > 2:
            ys.add(round(a[1], 2))
    diffs = sorted(d for v in (sorted(xs), sorted(ys)) for d in (b - a for a, b in zip(v, v[1:])) if d > 0.5)
    return diffs[len(diffs) // 2] if diffs else None


def figures(pdf, page_no, outline_width, join=8.0):
    """One record per figure: loops in feet (visual frame), size, grid size and nearby text.

    Outline strokes whose boxes come within `join` points are one figure, so the letters
    of a word stay together while separate figures stay apart."""
    page = fitz.open(pdf)[page_no]
    page.set_rotation(0)
    drawings = page.get_drawings()
    words = page.get_text('words')
    grid_segs = [(a, b) for d in drawings if round(d.get('width') or 0, 2) == GRID_WIDTH
                 for s in segments(d) for a, b in zip(s, s[1:])]
    notes = []
    for j, w in enumerate(words):
        if w[4].upper() == 'GRID' and j:
            value = grid_value(words[j - 1][4])
            if value:
                notes.append((fitz.Rect(words[j - 1][:4]) | fitz.Rect(w[:4]), value))
    outline = [d for d in drawings if round(d.get('width') or 0, 2) == outline_width]
    boxes = [fitz.Rect(d['rect']) for d in outline]
    out = []
    for group in _union_find(boxes, join):
        box = fitz.Rect(boxes[group[0]])
        for i in group[1:]:
            box |= boxes[i]
        if box.width < 6 or box.height < 6:
            continue
        step = _grid_step(grid_segs, box)
        near = [n for n in sorted(notes, key=lambda n: _gap(n[0], box)) if _gap(n[0], box) <= 90]
        if not step or not near:
            continue
        # Pick the grid note whose scale makes the figure agree with the dimensions printed beside it;
        # with no dimensions nearby, the nearest note wins.
        dims = feet_text([w[4] for w in words if _gap(fitz.Rect(w[:4]), box) < 45])
        width_pt, height_pt = box.height, box.width  # visual width runs along unrotated y

        def score(note):
            u = note[1] / step
            if not dims:
                return _gap(note[0], box)
            return min(abs(width_pt * u - d) for d in dims) + min(abs(height_pt * u - d) for d in dims)
        grid_ft = min(near, key=score)[1]
        unit = grid_ft / step  # feet per point
        loops = []
        for loop in chain([sg for i in group for sg in segments(outline[i])], tol=0.6):
            gap = math.hypot(loop[0][0] - loop[-1][0], loop[0][1] - loop[-1][1]) * unit
            closed = len(loop) > 3 and gap <= max(grid_ft, 1.0) + 0.02
            loops.append((loop, closed, round(gap, 3)))
        pts = [p for loop, _, _ in loops for p in loop]
        x0, x1 = min(p[1] for p in pts), max(p[1] for p in pts)
        y0, y1 = min(p[0] for p in pts), max(p[0] for p in pts)
        feet = [([((p[1] - x0) * unit, (p[0] - y0) * unit) for p in loop], closed, gap) for loop, closed, gap in loops]
        text = [w[4] for w in words if _gap(fitz.Rect(w[:4]), box) < 45]
        out.append({'box': [round(v, 1) for v in box], 'grid_ft': grid_ft, 'unit': unit,
                    'size': (round((x1 - x0) * unit, 3), round((y1 - y0) * unit, 3)), 'loops': feet, 'text': text})
    # visual reading order: top to bottom (visual y is unrotated x), then left to right
    out.sort(key=lambda f: (-round(f['box'][2] / 60), f['box'][1]))
    return out
