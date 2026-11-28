"""Library sign faces rebuilt from the site's sign chart artwork.

A library block whose designation has a chart image (public/signs/*.svg, from FHWA Standard Highway
Signs and the California sign specifications) is redrawn from that artwork when the two are the same
sign: the same words, the same proportions and a close match in shape (the chart face or its mirror
image, for left and right versions). Numbers that vary by installation (speeds, hours, distances) keep
the block's own values, set in the chart's numeral series. In a mirrored face the arrows and symbols
turn and the words keep reading left to right.
"""
from functools import lru_cache
from pathlib import Path
import json
import re
import sys

import contourpy
import ezdxf
import numpy as np
from ezdxf.math import Matrix44
from matplotlib.path import Path as VectorPath
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).parent))
from build_issued_block_faces import render_pixels, monochrome, isolate_issued_panel  # noqa: E402
import center_sign_legends as C  # noqa: E402
import reletter_signs as R  # noqa: E402
from sign_cells import parse_fragment  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@lru_cache(None)
def chart():
    out = {}
    for s in json.loads((ROOT / 'data/signs/signs.json').read_text()):
        if s.get('svg') and (ROOT / ('public' + s['svg'])).is_file():
            out[s['code'].upper()] = s
    return out


def candidates(code):
    """Chart designations a library code may stand for."""
    c = re.sub(r'\s*\[.*?\]', '', code).strip().upper()
    c = re.sub(r'\s+', '', c)
    forms = [c]
    forms.append(re.sub(r'\(MOD[^)]*\)', '', c))
    for f in list(forms):
        forms += [re.sub(r'\(\d+\)$', '', f), re.sub(r'-\d{2,}$', '', f)]
        forms.append(re.sub(r'(\((L|R|LT|RT|LEFT|RIGHT)\)|-(L|R|LT|RT)|(?<=\d)(L|R))$', '', f))
        m = re.fullmatch(r'(R2-1)(\d{2})', f)
        if m:
            forms.append(m.group(1))
    for f in list(forms):
        forms.append(re.sub(r'(\((L|R|LT|RT|LEFT|RIGHT)\)|-(L|R|LT|RT)|(?<=\d)(L|R))$', '', f))
    forms += [f + 'P' for f in list(forms)]                          # plaques: R9-3B -> R9-3BP
    seen, out = set(), []
    for f in forms:
        if f and f not in seen and f in chart():
            seen.add(f)
            out.append(f)
    return out


@lru_cache(None)
def chart_ink(code, size=1000):
    s = chart()[code]
    pixels = render_pixels(ROOT / ('public' + s['svg']), size)
    ink, panel = isolate_issued_panel(pixels, monochrome(pixels), code)
    y, x = np.where(panel if panel is not None else ink)
    return ink[y.min():y.max() + 1, x.min():x.max() + 1]


def face_doc(ink, bounds):
    """Chart ink traced to filled hatches spanning the block's face bounds."""
    x0, y0, x1, y1 = bounds
    w, h = x1 - x0, y1 - y0
    height, width = ink.shape
    doc = ezdxf.new('R2000')
    msp = doc.modelspace()
    curves = contourpy.contour_generator(z=np.pad(ink.astype(float), 1), fill_type='OuterOffset')
    polys, cuts = curves.filled(.5, 2)
    for poly, offsets in zip(polys, cuts):
        hatch = msp.add_hatch(color=7)
        for i, (a, b) in enumerate(zip(offsets, offsets[1:])):
            pts = [(x0 + (px - .5) * w / width, y1 - (py - .5) * h / height) for px, py in poly[a:b]]
            path = VectorPath(pts)
            path.simplify_threshold = min(w / width, h / height) * .5
            loop = path.cleaned(simplify=True).vertices[:-1]
            if len(loop) > 3:
                hatch.paths.add_polyline_path([tuple(p) for p in loop[:-1]], is_closed=True, flags=int(i == 0))
        if not hatch.paths:
            msp.delete_entity(hatch)
    return doc


def similarity(a, b):
    """Shape agreement of the legends and symbols of two faces: dilated ink inside the border band,
    intersection over union at a common size."""
    n = 96
    A = np.array(Image.fromarray(a.astype(np.uint8) * 255).resize((n, n), Image.BILINEAR)) > 60
    B = np.array(Image.fromarray(b.astype(np.uint8) * 255).resize((n, n), Image.BILINEAR)) > 60
    m = int(n * 0.14)
    A, B = A[m:-m, m:-m], B[m:-m, m:-m]
    A, B = ndimage.binary_dilation(A, iterations=2), ndimage.binary_dilation(B, iterations=2)
    return (A & B).sum() / max((A | B).sum(), 1)


def face_text(ink):
    """Words and numbers that two whole-face readings agree on (sparse text mode, plain and thickened)."""
    import subprocess, tempfile, os
    found = []
    for v in range(2):
        im = ndimage.binary_dilation(ink, iterations=1) if v else ink
        img = Image.fromarray(~im).convert('L')
        f = 1000 / max(img.size)
        img = img.resize((max(1, int(img.width * f)), max(1, int(img.height * f))), Image.LANCZOS)
        with tempfile.NamedTemporaryFile(suffix='.png') as t:
            img.save(t.name)
            r = subprocess.run(['tesseract', t.name, '-', '--psm', '11', '-c',
                                'tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'],
                               capture_output=True, text=True, env=dict(os.environ, OMP_THREAD_LIMIT='1'))
        toks = re.findall(r'[A-Z]{2,}|\d+', r.stdout)
        found.append(toks)
    a, b = found
    common = [t for t in a if t in b]
    return sorted(t for t in common if not t.isdigit()), sorted(t for t in common if t.isdigit())


def face_tokens(ink):
    """Every real word and every number any reading of the whole face finds."""
    import subprocess, tempfile, os
    import sign_spelling
    words, nums = set(), set()
    for v in range(3):
        im = ndimage.binary_dilation(ink, iterations=v) if v else ink
        img = Image.fromarray(~im).convert('L')
        f = 1000 / max(img.size)
        img = img.resize((max(1, int(img.width * f)), max(1, int(img.height * f))), Image.LANCZOS)
        with tempfile.NamedTemporaryFile(suffix='.png') as t:
            img.save(t.name)
            r = subprocess.run(['tesseract', t.name, '-', '--psm', ('11', '11', '6')[v], '-c',
                                'tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'],
                               capture_output=True, text=True, env=dict(os.environ, OMP_THREAD_LIMIT='1'))
        for t in re.findall(r'[A-Z]{3,}', r.stdout):
            t = sign_spelling.correct_word(t)
            if sign_spelling.is_word(t):
                words.add(t)
        nums |= set(re.findall(r'\d+', r.stdout))
    return words, nums


def direction(a):
    """The parts of a face that are not left-right symmetric (arrows, a lane that ends)."""
    n = 96
    A = np.array(Image.fromarray(a.astype(np.uint8) * 255).resize((n, n), Image.BILINEAR)) > 60
    return A & ~A[:, ::-1]


def reads(doc, bounds):
    """Agreed readings of the text groups on a face, top to bottom, with their entities and boxes."""
    groups, _, _ = R.text_groups(doc, bounds)
    out = []
    for ents, box in groups:
        gh = box[3] - box[1]
        ink = R.raster_entities(ents, box, R.PX / gh)
        if len(R.pieces(ink)) < 1:
            continue
        rs = [R.normalize(R.ocr(ink, v)) for v in range(5)]
        votes = {}
        for r in rs:
            if r:
                votes[r] = votes.get(r, 0) + 1
        best = max(votes.items(), key=lambda kv: kv[1], default=(None, 0))
        if best[1] >= 2 and R.plausible(best[0]):
            out.append((best[0], ents, box))
    out.sort(key=lambda g: -g[2][3])
    return out


def words(rs):
    return [re.sub(r'\d', '#', w) for r, _, _ in rs for w in r.split()]


def match(key, text, bounds, code):
    """Chart-built fragment for a library face, or None with the reason."""
    lib = parse_fragment(text)
    lib_ink = R.raster_entities(list(lib.modelspace()), bounds, 600 / max(bounds[2] - bounds[0], bounds[3] - bounds[1]), pad=0)
    ys, xs = np.where(lib_ink)
    if not len(xs):
        return None, 'empty'
    lib_ink = lib_ink[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    import sign_spelling
    lib_reads = None
    lib_words, lib_nums = face_text(lib_ink)
    lib_words = sorted(sign_spelling.correct_word(w) for w in lib_words)
    lib_any = None
    for cand in candidates(code):
        ink = chart_ink(cand)
        aspect = (ink.shape[1] / ink.shape[0]) / ((bounds[2] - bounds[0]) / (bounds[3] - bounds[1]))
        if not 0.94 < aspect < 1.06:
            continue
        straight, mirrored = similarity(lib_ink, ink), similarity(lib_ink, ink[:, ::-1])
        dl, do = direction(lib_ink), direction(ink)
        same = (dl & do).sum() / max((dl | do).sum(), 1)
        flipped = (dl & do[:, ::-1]).sum() / max((dl | do[:, ::-1]).sum(), 1)
        flip = bool(flipped > same + 0.05)
        if abs(flipped - same) <= 0.05 and dl.sum() > 0.02 * dl.size:
            continue                      # cannot tell which way it points
        sim = float(mirrored if flip else straight)
        if sim < 0.45:
            continue
        off_words, off_nums = face_text(ink)
        if off_words != lib_words:
            continue                      # different words: a different design under the same code
        ow, on = face_tokens(ink)
        if lib_any is None:
            lib_any = face_tokens(lib_ink)
        lw, ln = lib_any
        if not (lw <= ow | set(off_words) and ow <= lw | set(lib_words)):
            continue                      # a word on one face that the other does not carry
        if flip and (ow or lw or off_words or lib_words or ink.mean() > 0.3
                     or face_tokens(~ink)[0] or face_tokens(~lib_ink)[0]):
            continue                      # a face with words (dark or knocked out) is never mirrored
        doc = face_doc(ink, bounds)
        off = reads(doc, bounds)
        if lib_reads is None:
            lib_reads = reads(lib, bounds)
        if words(off) != words(lib_reads):
            continue
        if flip and off_words and not off:
            continue                      # text that cannot be separated would be mirrored
        if off_nums != lib_nums and len(off) != len(lib_reads):
            continue
        # numbers that vary by installation keep the block's values
        pairs = [(o[0], l[0]) for o, l in zip(off, lib_reads) if o[0] != l[0]]
        if any(re.sub(r'\d', '#', a) != re.sub(r'\d', '#', b) for a, b in pairs):
            continue                      # only numbers may differ
        force = dict(pairs)
        if flip:
            cx = (bounds[0] + bounds[2]) / 2
            text_ids = {id(e) for _, ents, _ in off for e in ents}
            mirror = Matrix44.translate(-cx, 0, 0) @ Matrix44.scale(-1, 1, 1) @ Matrix44.translate(cx, 0, 0)
            for e in list(doc.modelspace()):
                if id(e) not in text_ids:
                    e.transform(mirror)
            for _, ents, box in off:
                dx = 2 * (cx - (box[0] + box[2]) / 2)
                for e in ents:
                    e.translate(dx, 0, 0)
        frag = C.fragment(doc)
        if force:
            new, rows = R.reletter(key, frag, bounds, force=force, only_forced=True)
            if new is None or any(r['result'] != 'relettered' for r in rows):
                continue
            frag = new
        # the finished face must read like the block: same words, same numbers
        done = parse_fragment(frag)
        dink = R.raster_entities(list(done.modelspace()), bounds, 600 / max(bounds[2] - bounds[0], bounds[3] - bounds[1]), pad=0)
        d_words, d_nums = face_text(dink)
        dw, dn = face_tokens(dink)
        if d_words != lib_words or d_nums != lib_nums or dn != lib_any[1]:
            continue                      # every number any reading finds must be the block's
        return frag, dict(chart=cand, similarity=round(sim, 3), mirrored=flip, values=force,
                          legend=' / '.join(r for r, _, _ in off))
    return None, 'no chart match'


def side(code):
    """'L' or 'R' when a library code names a direction."""
    c = re.sub(r'\s*\[.*?\]', '', code).strip().upper().replace(' ', '')
    m = re.search(r'(\((L|LT|LEFT)\)|-(L|LT)|(?<=\d)L)$', c)
    if m:
        return 'L'
    m = re.search(r'(\((R|RT|RIGHT)\)|-(R|RT)|(?<=\d)R)$', c)
    return 'R' if m else None


def consistent(matches, codes):
    """Drop left and right versions of one chart face that came out in the same orientation."""
    groups = {}
    for key, info in matches.items():
        sd = side(codes[key])
        if sd:
            groups.setdefault(info['chart'], {}).setdefault(sd, set()).add(info['mirrored'])
    bad = {c for c, g in groups.items() if 'L' in g and 'R' in g and (g['L'] & g['R'] or len(g['L']) > 1 or len(g['R']) > 1)}
    return {k: v for k, v in matches.items() if not (side(codes[k]) and v['chart'] in bad)}
