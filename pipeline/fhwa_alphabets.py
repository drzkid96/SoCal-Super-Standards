"""FHWA Standard Alphabets (Series B, C, D, E, E Modified, F), as glyph outlines.

The fonts are the Series 2000 Type 1 fonts embedded in FHWA's Standard Alphabets for Traffic Control
Devices (https://mutcd.fhwa.dot.gov/SHSe/Alphabets.pdf), a US government work. Outlines are in font units
(1000 per em); cap height is the height of H.
"""
from functools import lru_cache
from pathlib import Path

from fontTools import t1Lib
from fontTools.pens.recordingPen import RecordingPen

FOLDER = Path(__file__).resolve().parent.parent / 'data/reference/fhwa-alphabets'
SERIES = ('B', 'C', 'D', 'E', 'EM', 'F')
NAMES = {'&': 'ampersand', '*': 'asterisk', '@': 'at', '¢': 'cent', ':': 'colon', ',': 'comma', '$': 'dollar',
         '8': 'eight', '=': 'equal', '!': 'exclam', '5': 'five', '4': 'four', '-': 'hyphen', '9': 'nine',
         '#': 'numbersign', '1': 'one', '(': 'parenleft', ')': 'parenright', '.': 'period', '+': 'plus',
         '?': 'question', '"': 'quotedbl', '7': 'seven', '6': 'six', '/': 'slash', '3': 'three', '2': 'two',
         '0': 'zero'}


@lru_cache(None)
def font(series):
    f = t1Lib.T1Font(str(FOLDER / f'Series{series}-2000.pfa'))
    return f.getGlyphSet()


def glyph_name(ch):
    return NAMES.get(ch, ch if ch.isalpha() and ch.isascii() else None)


def supported(text, series='D'):
    gs = font(series)
    return all(ch == ' ' or ch == "'" or (glyph_name(ch) in gs) for ch in text)


def _flatten(rec, steps=8):
    """Recorded pen operations -> closed polylines."""
    out, cur, start = [], [], None
    for op, args in rec.value:
        if op == 'moveTo':
            if cur:
                out.append(cur)
            cur, start = [args[0]], args[0]
        elif op == 'lineTo':
            cur.append(args[0])
        elif op == 'curveTo':
            p0 = cur[-1]
            pts = (p0,) + tuple(args)
            if len(pts) == 4:
                (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pts
                for i in range(1, steps + 1):
                    t = i / steps
                    mt = 1 - t
                    cur.append((mt**3 * x0 + 3 * mt * mt * t * x1 + 3 * mt * t * t * x2 + t**3 * x3,
                                mt**3 * y0 + 3 * mt * mt * t * y1 + 3 * mt * t * t * y2 + t**3 * y3))
            else:
                cur += list(args)
        elif op == 'qCurveTo':
            cur += list(args)
        elif op in ('closePath', 'endPath'):
            if cur:
                out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [c for c in out if len(c) > 2]


@lru_cache(None)
def glyph(series, ch):
    """(advance width, contours) in font units. The apostrophe is the left mark of the quotation mark."""
    if ch == "'":
        w, cs = glyph(series, '"')
        left = min(cs, key=lambda c: min(p[0] for p in c))
        x0 = min(p[0] for p in left)
        lw = max(p[0] for p in left) - x0
        gap = min(p[0] for p in left) - 0
        return lw + 2 * max(gap, 0), [left]
    gs = font(series)
    g = gs[glyph_name(ch)]
    pen = RecordingPen()
    g.draw(pen)
    return g.width, _flatten(pen)


@lru_cache(None)
def cap_height(series):
    _, cs = glyph(series, 'H')
    return max(y for c in cs for _, y in c)


def space(series):
    """Word space: the width of the letter E in the same series, a common sign-layout rule."""
    return glyph(series, 'E')[0] * 0.9


def layout(text, series):
    """Glyph contours placed along a baseline at y = 0, in font units; returns (contours per glyph, width)."""
    x, out = 0.0, []
    for ch in text:
        if ch == ' ':
            x += space(series)
            continue
        w, cs = glyph(series, ch)
        out.append((ch, [[(px + x, py) for px, py in c] for c in cs]))
        x += w
    return out, x
