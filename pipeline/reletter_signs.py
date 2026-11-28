"""Re-letter library sign faces in the FHWA Standard Alphabets.

Sign faces taken from CAD libraries were lettered in whatever font the library used (Arial-like
faces, stroke fonts). Each text group on a face is read, checked letter by letter against the original
shapes, and redrawn in place with FHWA Series B, C, D, E, E Modified or F glyph outlines: the series whose
set width best matches the original, the same cap height, baseline and center. A group is left as it was
when the reading is not certain (piece count, letter widths or heights disagree, a character the
alphabets lack, a letter with a descender), when the new letters would touch other line work, or when the
letters are cut out of a dark field.

  python pipeline/reletter_signs.py [--write] [--only ID ...]   (rewrites data/reference/cad-sign-entities.zip.*)
"""
import argparse
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).parent))
import center_sign_legends as C  # noqa: E402
import fhwa_alphabets as F  # noqa: E402
from ezdxf import path as epath  # noqa: E402
from sign_cells import parse_fragment  # noqa: E402

PX = 90                     # raster pixels per group height
WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789&-./:()$!?,'%;"
DIGITS = str.maketrans({'T': '7', 'I': '1', 'l': '1', 'O': '0', 'o': '0', 'S': '5', 'Z': '2', 'B': '8'})


def normalize(read):
    """Readings of times and numbers: letters a stroke font makes look like digits become digits."""
    fix = lambda m: m.group(1).translate(DIGITS) + (m.group(2) or '').translate(DIGITS)
    read = re.sub(r'(?<![A-Za-z0-9])([0-9TIlOoSZB]{1,2})(:[0-9OoS]{2})?(?=\s?(?:AM|PM|A\.M\.|P\.M\.)(?![A-Za-z]))', fix, read)
    read = re.sub(r'(?<![A-Za-z])([0-9OoIl]*[0-9][0-9OoIl]*)(?![A-Za-z])', lambda m: m.group(1).translate(DIGITS), read)
    return re.sub(r'(?<![A-Za-z0-9])1-(?=[0-9])', 'I-', read)          # interstate routes: I-5, I-405


def plausible(read):
    """Mostly letters and digits, and any times are real times: a line of text, not a misread."""
    core = read.replace(' ', '')
    alnum = sum(c.isalnum() for c in core)
    if alnum < 2 or alnum < 0.66 * len(core):
        return False
    if re.search(r'[a-z]', re.sub(r'\bMc', '', read)):
        return False                        # sign legends are capitals (names such as McCOY aside)
    if read.count('(') != read.count(')'):
        return False
    if re.search(r'(^|\s)&', read) and not re.search(r'[A-Z0-9]\s?&', read):
        return False                        # an ampersand only joins words: '& BUS' is a logo
    for tok in read.split():
        if re.search(r'[0-9][A-Z]{3,}', tok) and not re.search(r'[0-9]MPH$', tok):
            return False                    # a number run into a word: 91GRADE is 9% GRADE misread
        if re.search(r'[A-Z][0-9]', tok) and not re.fullmatch(r'[A-Z]{1,2}-?[0-9]+[A-Z]?', tok):
            return False                    # a letter run into a digit inside a word: Q1GRADE, O0W
    times = re.findall(r'(?<![A-Za-z0-9])(\d{1,2})(?::(\d{2}))?\s?(?:AM|PM)(?![A-Za-z])', read)
    for h, m in times:
        if not 1 <= int(h) <= 12 or (m and int(m) > 59):
            return False
    if (times or '-' in read) and re.search(r'(?<![A-Za-z0-9])[A-Z]{1,2}(?:AM|PM)(?![A-Za-z])', read):
        return False
    return True


LOOKALIKE = ['17ITLJ', '0OQD69CG', '5S6', '8B3', '2Z', 'MN', 'UV']


def glyph_shape(series, ch, n=24):
    _, cs = F.glyph(series, ch)
    xs = [p[0] for c in cs for p in c]
    ys = [p[1] for c in cs for p in c]
    x0, y0, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    m = Image.new('1', (n, n), 0)
    for c in cs:
        t = Image.new('1', (n, n), 0)
        ImageDraw.Draw(t).polygon([((x - x0) / max(w, 1e-6) * (n - 1), (n - 1) - (y - y0) / max(h, 1e-6) * (n - 1)) for x, y in c], fill=1)
        m = ImageChops.logical_xor(m, t)
    return ndimage.binary_dilation(np.array(m, dtype=bool), iterations=2)


def best_lookalikes(read, series, orig_ink, orig):
    """Each letter replaced by the look-alike whose FHWA shape matches the original piece clearly best."""
    chars = [c for c in read if c != ' ']
    if len(chars) != len(orig):
        return read
    out, i = [], 0
    tokens = read.split(' ')
    owner = [t for t in tokens for _ in t] if False else None
    pos = 0
    word_of = []
    for t in tokens:
        word_of += [t] * len(t)
        word_of.append('')
    for j, c in enumerate(read):
        if c == ' ':
            out.append(c)
            continue
        piece = norm_piece(orig_ink, orig[i])
        i += 1
        group = next((g for g in LOOKALIKE if c in g), None)
        if not group:
            out.append(c)
            continue
        word = word_of[j]
        numeric = any(ch.isdigit() for ch in word.replace(c, '', 1)) or re.search(r'(AM|PM)$', word)
        if c.isdigit():
            allowed = lambda ch: ch.isdigit()
        else:
            allowed = lambda ch: ch == c or (numeric and ch.isdigit())   # no letter-for-letter swaps
        score = lambda ch: (piece & glyph_shape(series, ch)).sum() / max((piece | glyph_shape(series, ch)).sum(), 1)
        cands = [ch for ch in group if F.supported(ch, series) and allowed(ch)] or [c]
        best = max(cands, key=score)
        out.append(best if score(best) > score(c) + 0.06 else c)
    return ''.join(out)
SKIP = {'W14-3'}


def raster_entities(ents, box, s, pad=12):
    """Binary picture (True = ink) of entities in box at s pixels per unit."""
    x0, y0, x1, y1 = box
    w, h = int((x1 - x0) * s) + 2 * pad, int((y1 - y0) * s) + 2 * pad
    tf = lambda q: (pad + (q.x - x0) * s, h - pad - (q.y - y0) * s)
    ink = Image.new('1', (w, h), 0)
    for e in ents:
        if e.dxftype() == 'HATCH':
            m = Image.new('1', ink.size, 0)
            for q in epath.from_hatch(e):
                pts = [tf(v) for v in q.flattening(0.3 / s)]
                if len(pts) > 2:
                    t = Image.new('1', ink.size, 0)
                    ImageDraw.Draw(t).polygon(pts, fill=1)
                    m = ImageChops.logical_xor(m, t)
            ink = ImageChops.logical_or(ink, m)
        else:
            try:
                pts = [tf(v) for v in epath.make_path(e).flattening(0.3 / s)]
            except Exception:
                continue
            if len(pts) > 1:
                ImageDraw.Draw(ink).line(pts, fill=1, width=max(1, round(s * 0.012 * (y1 - y0))))
    return np.array(ink, dtype=bool)


def raster_glyphs(glyphs, box, s, pad=12):
    x0, y0, x1, y1 = box
    w, h = int((x1 - x0) * s) + 2 * pad, int((y1 - y0) * s) + 2 * pad
    ink = Image.new('1', (w, h), 0)
    for _, cs in glyphs:
        m = Image.new('1', ink.size, 0)
        for c in cs:
            t = Image.new('1', ink.size, 0)
            ImageDraw.Draw(t).polygon([(pad + (x - x0) * s, h - pad - (y - y0) * s) for x, y in c], fill=1)
            m = ImageChops.logical_xor(m, t)
        ink = ImageChops.logical_or(ink, m)
    return np.array(ink, dtype=bool)


def pieces(ink):
    """Connected ink pieces as (x0, y0, x1, y1) boxes, left to right, small specks dropped."""
    lab, n = ndimage.label(ink, structure=np.ones((3, 3)))
    boxes = []
    for sl in ndimage.find_objects(lab):
        if sl is None:
            continue
        ys, xs = sl
        boxes.append((xs.start, ys.start, xs.stop, ys.stop))
    if not boxes:
        return []
    big = max(b[3] - b[1] for b in boxes)
    keep = [b for b in boxes if (b[3] - b[1]) > 0.08 * big or (b[2] - b[0]) > 0.08 * big]
    # pieces stacked over each other (the dots of i, j, !, ?, :) count as one column
    keep.sort(key=lambda b: b[0])
    merged = []
    for b in keep:
        if merged and b[0] < merged[-1][2] - 0.3 * (b[2] - b[0]) and b[2] > merged[-1][0]:
            m = merged[-1]
            merged[-1] = (min(m[0], b[0]), min(m[1], b[1]), max(m[2], b[2]), max(m[3], b[3]))
        else:
            merged.append(b)
    return merged


def ocr(ink, variant=0):
    """Read a line. Variants for a second try: thickened strokes, a larger picture, other page modes."""
    psm = {0: '7', 1: '7', 2: '7', 3: '8', 4: '13'}[variant]
    if variant == 1:
        ink = ndimage.binary_dilation(ink, iterations=2)
    img = Image.fromarray(~ink).convert('L')
    f = 3 if variant == 2 else 2
    img = img.resize((img.width * f, img.height * f), Image.LANCZOS)
    with tempfile.NamedTemporaryFile(suffix='.png') as f:
        img.save(f.name)
        r = subprocess.run(['tesseract', f.name, '-', '--psm', psm, '-c', 'tessedit_char_whitelist=' + WHITELIST + ' '],
                           capture_output=True, text=True, env=dict(os.environ, OMP_THREAD_LIMIT='1'))
    return ' '.join(r.stdout.split())


def norm_piece(ink, b, n=24):
    """A piece cut out and scaled to n x n, thickened so stroke and filled letters compare."""
    x0, y0, x1, y1 = b
    im = Image.fromarray(ink[y0:y1, x0:x1].astype(np.uint8) * 255).resize((n, n), Image.BILINEAR)
    arr = np.array(im) > 60
    return ndimage.binary_dilation(arr, iterations=2)


def agree(orig_ink, orig, new_ink, new, chars=''):
    """Original and new letters line up: pieces matched by position (touching letters may share a piece),
    matched groups of similar width and height, and similar shapes where one piece matches one letter."""
    if not orig or not new:
        return 'empty'
    if len(orig) > len(new):
        return 'extra marks'                # something in the original the reading does not account for
    ox0, ox1 = orig[0][0], max(b[2] for b in orig)
    nx0, nx1 = new[0][0], max(b[2] for b in new)
    oh = max(b[3] - b[1] for b in orig)
    nh = max(b[3] - b[1] for b in new)
    on = [((b[0] - ox0) / (ox1 - ox0), (b[2] - ox0) / (ox1 - ox0)) for b in orig]
    nn = [((b[0] - nx0) / (nx1 - nx0), (b[2] - nx0) / (nx1 - nx0)) for b in new]
    parent = list(range(len(on) + len(nn)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    if len(on) == len(nn):
        for i in range(len(on)):
            parent[find(i)] = find(len(on) + i)
    else:
        for i, (a0, a1) in enumerate(on):
            for j, (b0, b1) in enumerate(nn):
                ov = min(a1, b1) - max(a0, b0)
                if ov > 0.35 * min(a1 - a0, b1 - b0):
                    parent[find(i)] = find(len(on) + j)
        # a piece that overlaps nothing joins the nearest piece of the other set
        centers = [(a0 + a1) / 2 for a0, a1 in on] + [(b0 + b1) / 2 for b0, b1 in nn]
        for i in range(len(on) + len(nn)):
            same = [j for j in range(len(on) + len(nn)) if find(j) == find(i)]
            if all(j < len(on) for j in same) or all(j >= len(on) for j in same):
                other = range(len(on), len(on) + len(nn)) if i < len(on) else range(len(on))
                j = min(other, key=lambda j: abs(centers[j] - centers[i]))
                parent[find(i)] = find(j)
    groups = {}
    for i in range(len(on) + len(nn)):
        groups.setdefault(find(i), []).append(i)
    for members in groups.values():
        o = [i for i in members if i < len(on)]
        n = [i - len(on) for i in members if i >= len(on)]
        if not o or not n:
            return 'unmatched'
        ow = on[max(o)][1] - on[min(o)][0]
        nw = nn[max(n)][1] - nn[min(n)][0]
        bare = len(n) == 1 and len(chars) == len(nn) and chars[n[0]] in '1Il'
        lo, hi = (0.3, 4.0) if bare or min(ow, nw) < 0.08 else (0.55, 1.8)   # FHWA 1 and I are bare strokes
        if not lo < ow / max(nw, 1e-6) < hi:
            return 'width %.2f' % (ow / max(nw, 1e-6))
        oth = max(orig[i][3] - orig[i][1] for i in o) / oh
        nth = max(new[i][3] - new[i][1] for i in n) / nh
        if abs(oth - nth) > 0.22:
            return 'height %.2f/%.2f' % (oth, nth)
        if len(o) == 1 and len(n) == 1:
            p, q = norm_piece(orig_ink, orig[o[0]]), norm_piece(new_ink, new[n[0]])
            iou = (p & q).sum() / max((p | q).sum(), 1)
            a, b = orig[o[0]], new[n[0]]
            da = orig_ink[a[1]:a[3], a[0]:a[2]].mean()
            db = new_ink[b[1]:b[3], b[0]:b[2]].mean()
            if abs(da - db) > 0.3 and not bare:
                return 'density %.2f/%.2f' % (da, db)
            if iou < 0.5:
                return 'shape %.2f' % iou
    return True


def overlay(orig_ink, orig, new_ink, new):
    """Ink overlap of the whole line once the new lettering is stretched to the original's extent."""
    a = orig_ink[min(b[1] for b in orig):max(b[3] for b in orig), min(b[0] for b in orig):max(b[2] for b in orig)]
    b = new_ink[min(q[1] for q in new):max(q[3] for q in new), min(q[0] for q in new):max(q[2] for q in new)]
    n = (64, 64 * max(1, round(a.shape[1] / max(a.shape[0], 1))))
    A = np.array(Image.fromarray(a.astype(np.uint8) * 255).resize((n[1], n[0]), Image.BILINEAR)) > 60
    B = np.array(Image.fromarray(b.astype(np.uint8) * 255).resize((n[1], n[0]), Image.BILINEAR)) > 60
    A, B = ndimage.binary_dilation(A, iterations=3), ndimage.binary_dilation(B, iterations=3)
    return (A & B).sum() / max((A | B).sum(), 1)


def partial(read, wide):
    """True when the wider reading joins a word of the line into a longer common word (B+UMPS = BUMPS,
    EXEM+PT = EXEMPT): the line is then only part of a word. Border strokes read as stray letters do not
    make a word, so they do not count."""
    import sign_spelling
    from wordfreq import zipf_frequency
    whole = re.sub(r'[^A-Z]', '', read.upper())
    for t in re.findall(r'[A-Za-z]{2,}', wide):
        t = t.upper()
        if t in whole:
            continue
        for w in re.findall(r'[A-Z]{2,}', read.upper()):
            if w in t and t != w and (t in sign_spelling.vocabulary() or zipf_frequency(t.lower(), 'en') >= 3.0):
                return True
    return False


def text_groups(doc, bounds):
    """Groups of letters on one line, as (entities, box)."""
    x0, y0, x1, y1 = bounds
    W, H = x1 - x0, y1 - y0
    every = C.boxes(doc)
    frame = lambda b: (b[3] - b[1]) > 0.6 * W and (b[4] - b[2]) > 0.6 * H
    edge = lambda b: (b[3] < x0 + C.EDGE * W or b[1] > x1 - C.EDGE * W or b[4] < y0 + 0.04 * H or b[2] > y1 - 0.04 * H)
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
    out = []
    for row in rows:
        h = max(b[4] for b in row) - min(b[2] for b in row)
        comps = sorted(C.components(row), key=lambda c: c[0])
        groups, g = [], [comps[0]]
        for c in comps[1:]:
            if c[0] - g[-1][2] > 0.9 * h:
                groups.append(g)
                g = [c]
            else:
                g.append(c)
        groups.append(g)
        for g in groups:
            gh = max(c[3] for c in g) - min(c[1] for c in g)
            if not C.is_text(g, gh):
                continue
            ents = [b[0] for c in g for b in c[4]]
            box = (min(c[0] for c in g), min(c[1] for c in g), max(c[2] for c in g), max(c[3] for c in g))
            ids = {id(e) for e in ents}
            # a loose piece in the same band right against the line: part of a letter the line lost
            if any(id(b[0]) not in ids and not frame(b) and min(b[4], box[3]) - max(b[2], box[1]) > 0.4 * gh
                   and (0 <= box[0] - b[3] < 0.25 * gh or 0 <= b[1] - box[2] < 0.25 * gh) and (b[3] - b[1]) < 0.5 * W
                   for b in every):
                continue
            # a letter-sized piece within a letter height on the same line: the line is only part of the words
            if any(id(b[0]) not in ids and not frame(b) and 0.5 * gh <= (b[4] - b[2]) <= 1.3 * gh
                   and (b[3] - b[1]) <= 1.2 * gh and min(b[4], box[3]) - max(b[2], box[1]) > 0.5 * gh
                   and (0 <= box[0] - b[3] < 1.0 * gh or 0 <= b[1] - box[2] < 1.0 * gh)
                   for b in every):
                continue
            out.append((ents, box))
    return out, every, frame


def clear_of(every, mine, box, margin):
    a, c, d, e = box
    for b in every:
        if id(b[0]) in mine:
            continue
        if b[1] < d - margin and b[3] > a + margin and b[2] < e - margin and b[4] > c + margin:
            # a frame or panel that encloses the box is fine; anything crossing into it is not
            if not (b[1] <= a and b[3] >= d and b[2] <= c and b[4] >= e):
                return False
    return True


def room(others, bounds, band, cx, margin):
    """Clear half-width around cx inside the band, measured on the drawn ink of everything else."""
    x0, y0, x1, y1 = bounds
    W = x1 - x0
    sc = 600 / W
    lo, hi = band
    ink = raster_entities(others, (x0, lo, x1, hi), sc, pad=0)
    cols = ink.any(axis=0)
    c = int((cx - x0) * sc)
    left = next((i for i in range(min(c, len(cols) - 1), -1, -1) if cols[i]), -1)
    right = next((i for i in range(max(c, 0), len(cols)) if cols[i]), len(cols))
    lim_l = x0 + (left + 1) / sc if left >= 0 else x0 + C.EDGE * W
    lim_r = x0 + right / sc if right < len(cols) else x1 - C.EDGE * W
    return min(cx - lim_l, lim_r - cx) - margin


def word_gaps(orig, words, s):
    """The original gaps between words, in drawing units: the widest gaps between pieces."""
    if words < 2:
        return []
    gaps = [(orig[i + 1][0] - orig[i][2], i) for i in range(len(orig) - 1)]
    pick = sorted(sorted(gaps, reverse=True)[:words - 1], key=lambda g: g[1])
    return [g / s for g, _ in pick]


def layout(text, series, gaps, core, k_cap=None):
    """Glyph contours for text in one series, scaled so the cap height equals core; returns (glyphs, k, minx, width, top)."""
    cap = F.cap_height(series)
    k0 = core / cap
    x, gl, gi = 0.0, [], 0
    for ch in text:
        if ch == ' ':
            x += gaps[gi] / k0 if gi < len(gaps) else 0.75 * cap
            gi += 1
            continue
        adv, cs = F.glyph(series, ch)
        gl.append((ch, [[(px + x, py) for px, py in c] for c in cs]))
        x += adv
    xs = [p[0] for _, cs in gl for c in cs for p in c]
    ys = [p[1] for _, cs in gl for c in cs for p in c]
    k = core / max(ys)
    return gl, k, min(xs), (max(xs) - min(xs)) * k, max(ys)


def reletter(key, text, bounds, force=None, only_forced=False):
    """Re-letter one face. force maps a group's reading to the text to draw instead (official values).
    Returns (new fragment text or None, report rows)."""
    import sign_spelling
    doc = parse_fragment(text)
    groups, every, frame = text_groups(doc, bounds)
    W = bounds[2] - bounds[0]
    report, msp, changed = [], doc.modelspace(), False
    for ents, box in groups:
        gx0, gy0, gx1, gy1 = box
        gh, gw = gy1 - gy0, gx1 - gx0
        s = PX / gh
        ink = raster_entities(ents, box, s)
        orig = pieces(ink)
        if len(orig) < 2:
            continue
        bottoms = sorted(b[3] for b in orig)
        base_px, top_px = bottoms[len(bottoms) // 2], min(b[1] for b in orig)
        baseline = gy0 + (ink.shape[0] - 12 - base_px) / s
        core = (base_px - top_px) / s
        cx = (gx0 + gx1) / 2
        mine = {id(e) for e in ents}
        others = [e for e in msp if id(e) not in mine]
        half = room(others, bounds, (gy0 + 0.1 * gh, gy1 - 0.1 * gh), cx, min(0.4 * gh, 0.05 * W))

        def place(draw, series, gaps):
            gl, k, mx, nw, top = layout(draw, series, gaps, core)
            fit = 1.0
            if nw / 2 > half:
                fit = 2 * half / nw
                if fit < 0.7:
                    return None
                k, nw = k * fit, nw * fit
            nh = top * k
            ny0 = baseline + (core - nh) / 2 if fit < 1 else baseline
            nx0 = cx - nw / 2
            placed = [(ch, [[(nx0 + (x - mx) * k, ny0 + y * k) for x, y in c] for c in cs]) for ch, cs in gl]
            return placed, nw, fit

        def attempt(read, again=False):
            row = {'id': key, 'read': read}
            if not read or not plausible(read) or not F.supported(read):
                return dict(row, result='unread'), None
            gaps = word_gaps(orig, len(read.split()), s)
            series = min(F.SERIES, key=lambda se: abs(layout(read, se, gaps, core)[3] / gw - 1))
            got = place(read, series, gaps)
            if got is None:
                return dict(row, result='no room', series=series), None
            placed, nw, fit = got
            ys = [p[1] for _, cs in placed for c in cs for p in c]
            nbox = (cx - nw / 2, min(ys), cx + nw / 2, max(ys))
            new_ink = raster_glyphs(placed, nbox, s)
            new = pieces(new_ink)
            why = agree(ink, orig, new_ink, new, read.replace(' ', ''))
            if why is not True:
                return dict(row, result='shape', series=series, why=why), None
            ov = overlay(ink, orig, new_ink, new)
            if ov < 0.5:
                return dict(row, result='shape', series=series, why='overlay %.2f' % ov), None
            fixed = normalize(best_lookalikes(read, series, ink, orig))
            if fixed != read and not again:
                return attempt(fixed, True)
            # what is drawn: the official value when one is given, else the reading with its spelling corrected
            draw = (force or {}).get(read)
            draw, made = (draw, [('value', draw)]) if draw else sign_spelling.correct(read)
            if draw != read:
                if not F.supported(draw):
                    return dict(row, result='unread'), None
                got = place(draw, series, word_gaps(orig, len(draw.split()), s))
                if got is None:
                    return dict(row, result='no room', series=series), None
                placed, nw, fit = got
            return dict(row, result='relettered', drawn=draw, corrected=made, series=series,
                        width=round(nw / gw, 3), fit=round(fit, 3)), placed

        # the line read again with a letter height of margin and everything drawn there: a word that
        # continues past the line (B+UMPS, EXEM+PT) means the line is only part of the legend
        ext = (max(bounds[0], gx0 - gh), gy0, min(bounds[2], gx1 + gh), gy1)
        wide = normalize(ocr(raster_entities(list(msp), ext, s), 0))
        if partial(normalize(ocr(ink, 0)), wide):
            report.append({'id': key, 'read': wide, 'result': 'part of a word'})
            continue
        reads = [normalize(ocr(ink, v)) for v in range(5)]
        if only_forced and not any(r in (force or {}) for r in reads):
            continue
        votes = {}
        for r in reads:
            if r:
                votes[r] = votes.get(r, 0) + 1
        agreed = [r for r, n in sorted(votes.items(), key=lambda kv: -kv[1]) if n >= 2]
        row, placed = {'id': key, 'read': ' / '.join(dict.fromkeys(r for r in reads if r)), 'result': 'no agreement'}, None
        for r in agreed:
            row, placed = attempt(r)
            if placed is not None:
                break
        report.append(row)
        if placed is None:
            continue
        layer = ents[0].dxf.layer
        for e in ents:
            msp.delete_entity(e)
        for ch, cs in placed:
            hatch = msp.add_hatch(color=7, dxfattribs={'layer': layer})
            for c in cs:
                hatch.paths.add_polyline_path(c, is_closed=True)
        changed = True
    return (C.fragment(doc) if changed else None), report


def _chart_job(args):
    key, data, bounds, code = args
    import chart_faces
    try:
        frag, info = chart_faces.match(key, gzip.decompress(data).decode(), bounds, code)
    except Exception as ex:
        return key, None, 'error ' + repr(ex)[:120]
    return key, frag, info


def _job(args):
    key, data, bounds = args
    try:
        return key, *reletter(key, gzip.decompress(data).decode(), bounds)
    except Exception as ex:  # a face that cannot be read stays as it was
        return key, None, [{'id': key, 'result': 'error', 'read': repr(ex)[:120]}]


def run(write=False, only=None, workers=8, dump=None):
    """Chart artwork first, then re-lettering for every library face the chart does not cover."""
    from cad_blocks.web_entities import SOURCE, open_archive, write_member, write_parts
    import zipfile
    import chart_faces
    manifest = {r['id']: r for r in json.loads(Path('data/reference/cad-block-downloads/manifest.json').read_text())['records']}
    official = {'current issued artwork', 'historical issued artwork'}
    with open_archive(SOURCE) as bundle:
        index = json.loads(bundle.read('index.json'))
        members = {n: bundle.read(n) for n in bundle.namelist()}
    keys = [k for k, e in index.items() if (not only or k in only) and k in manifest
            and manifest[k].get('geometryStatus') not in official and e.get('name', '').split(' ')[0] not in SKIP]
    codes = {k: manifest[k]['code'] for k in keys}
    chart_jobs = [(k, members[k + '.dxf.gz'], index[k]['bounds'], codes[k]) for k in keys if chart_faces.candidates(codes[k])]
    report, changed, charted = [], {}, {}
    with Pool(workers) as pool:
        found = {k: (f, i) for k, f, i in pool.imap_unordered(_chart_job, chart_jobs, chunksize=2) if f}
    infos = chart_faces.consistent({k: i for k, (f, i) in found.items()}, codes)
    for k in infos:
        charted[k] = found[k][0]
        report.append(dict(id=k, result='chart', **infos[k]))
    jobs = [(k, members[k + '.dxf.gz'], index[k]['bounds']) for k in keys if k not in charted]
    with Pool(workers) as pool:
        for key, frag, rows in pool.imap_unordered(_job, jobs, chunksize=4):
            report += rows
            if frag:
                charted[key] = frag
    for key, frag in charted.items():
        data = gzip.compress(frag.encode(), compresslevel=8, mtime=0)
        members[key + '.dxf.gz'] = data
        index[key].update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        changed[key] = [r for r in report if r['id'] == key and r['result'] in ('chart', 'relettered')]
    if dump:
        dump.write_text(json.dumps(charted))
    if write and changed:
        temp = SOURCE.with_suffix('.tmp')
        with zipfile.ZipFile(temp, 'w') as out:
            for key in index:
                write_member(out, key + '.dxf.gz', members[key + '.dxf.gz'], zipfile.ZIP_STORED)
            data = json.dumps(index, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
            write_member(out, 'index.json', data, zipfile.ZIP_DEFLATED)
        write_parts(temp, SOURCE)
        temp.unlink()
    return changed, report


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--report', type=Path)
    ap.add_argument('--dump', type=Path, help='write the new face fragments here for review')
    a = ap.parse_args()
    changed, report = run(a.write, set(a.only) if a.only else None, dump=a.dump)
    if a.report:
        a.report.write_text(json.dumps({'changed': changed, 'report': report}, indent=0))
    from collections import Counter
    print(len(changed), 'faces re-lettered;', dict(Counter(r['result'] for r in report)), file=sys.stderr)


def run_pack(pack, write=False, use=None):
    """The same pass over a pack of plan-legend faces (geometry, geometry.json and previews in one zip).
    use: fragments from a reviewed run ({id: fragment}) to write as they are, instead of reading again."""
    import zipfile
    import chart_faces
    with zipfile.ZipFile(pack) as z:
        members = {i.filename: z.read(i.filename) for i in z.infolist()}
    geometry = json.loads(members['geometry.json'])
    records = {r['id']: r for r in json.loads(members['records.json'])}
    changed, report = dict(use or {}), []
    for key, entry in ({} if use is not None else geometry).items():
        text = gzip.decompress(members['geometry/' + key + '.dxf.gz']).decode()
        code = records.get(key, {}).get('code', entry.get('name', ''))
        frag = None
        if chart_faces.candidates(code):
            frag, info = chart_faces.match(key, text, entry['bounds'], code)
            if frag:
                report.append(dict(id=key, result='chart', **info))
        if frag is None:
            frag, rows = reletter(key, text, entry['bounds'])
            report += rows
        if frag:
            changed[key] = frag
    if write and changed:
        from PIL import Image
        for key, frag in changed.items():
            data = gzip.compress(frag.encode(), compresslevel=8, mtime=0)
            members['geometry/' + key + '.dxf.gz'] = data
            geometry[key].update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            prev = records.get(key, {}).get('preview')
            if prev and prev[1:] in members:
                old = Image.open(io.BytesIO(members[prev[1:]]))
                buf = io.BytesIO()
                C.render(parse_fragment(frag), geometry[key]['bounds'], old.size).save(buf, 'WEBP', quality=90, method=6)
                members[prev[1:]] = buf.getvalue()
        members['geometry.json'] = json.dumps(geometry).encode()
        temp = Path(str(pack) + '.tmp')
        with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as out:
            for name, data in members.items():
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                out.writestr(info, data)
        temp.replace(pack)
    return changed, report
