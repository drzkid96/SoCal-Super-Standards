"""SSS CAD standard: colors, layers and placement (base point) rules shared by every block builder.

Colors
- Green-colored pavement (bike facilities): FHWA Interim Approval IA-14 (April 15, 2011) daytime
  chromaticity box (0.230, 0.754) (0.266, 0.500) (0.367, 0.500) (0.444, 0.555), luminance factor 7 to 35.
  Screen and CAD value: the box centroid at luminance 21, converted to sRGB = RGB 60, 144, 2 (#3C9002);
  nearest AutoCAD index color 74.
- Red-colored pavement (transit lanes): FHWA Interim Approval IA-22 (December 4, 2019) daytime box
  (0.420, 0.330) (0.450, 0.380) (0.560, 0.370) (0.540, 0.320); IA-22 sets no luminance factor, 12 is used.
  RGB 157, 71, 58 (#9D473A); nearest index color 13.
- White markings: index 7 through the layer (prints black with a monochrome plot style).

Layers
- Block geometry on layer 0, color, linetype and lineweight ByLayer, so the insert layer controls it.
- Non-plotting frames and helpers on NOPLOT (plot off). A colored field hatch always has a NOPLOT frame.
- Inserts on the family layer (P-PMARK, P-SIGNAL, P-SIGN, E-SITE).

Placement (markings): travel runs +Y. The base point is on the reference line (limit line, stop line,
crosswalk line or panel start) at the lane's left line, so a block snaps to two lines already drawn.
"""
GREEN = (60, 144, 2)
GREEN_ACI = 74
RED = (157, 71, 58)
RED_ACI = 13
NOPLOT = 'NOPLOT'
LANE = 11.0          # ft, default travel lane width for lane-centered markings
BIKE_LANE = 5.0      # ft
STALL = 9.0          # ft, parking stall width
SHARROW_FROM_CURB = 11.0   # ft, CA MUTCD 9E.09 minimum center distance with parking

SOURCES = {
    'S-517': 'LADOT MPP 531 S-517.0 Typical Pavement Marking Installations',
    '3B.20': 'CA MUTCD 2026 Section 3B.20',
    '9E.09': 'CA MUTCD 2026 Section 9E.09',
    '9E.04': 'CA MUTCD 2026 Section 9E.04',
}


BAR_CROSSWALK_GAP = {'CT-A24F-CONTINENTAL': 1.0, 'CT-A24F-TRIPLE-FOUR': 2.0}   # ft, first gap at the curb
# Point symbols that stand on a pole, post or standard: the base point is the pole circle's center
POLE_SYMBOL = ('STANDARD', 'POLE', 'POST', 'PEDESTAL')


def placement(code, group):
    """(rule key, dx-target, y-target, one-line description) for a marking block, or None to keep.

    x target: ('center', value) puts the geometry center at x = value; ('min', value) puts the left
    edge there; ('shaft', value) moves x = 0 (the arrow shaft) to value.
    y target: ('top', value) puts the downstream edge at y = value; ('bottom', value) the upstream edge.
    """
    lane_mid = LANE / 2
    if code.startswith('CT-DET'):
        return None
    if code.startswith('PM-LEFT-TURN-CALMING'):
        return (('center', 0.0), ('bottom', 0.0),
                'Base at the upstream end, centered on the element; snap to the centerline or the left turn path')
    if group == 'Arrows':
        return (('shaft', lane_mid), ('top', -20.0),
                'Base on the limit line at the lane line; arrow point 20 ft before the line, centered in an 11 ft lane (CA MUTCD 3B.20)')
    if code in ('CT-A24D-STOP', 'PM-WAIT-HERE'):
        return (('center', lane_mid), ('top', -8.0),
                'Base on the limit line at the lane line; legend 8 ft before the line, centered in an 11 ft lane (LADOT S-517.0)')
    if code in ('PM-KEEP-CLEAR', 'PM-BUS-ONLY'):
        return (('center', lane_mid), ('bottom', 8.0),
                'Base on the crosswalk or limit line at the lane line; legend starts 8 ft past the line, centered in an 11 ft lane')
    if group in ('Words', 'Numerals') or code in ('CT-A24B-RXR', 'CT-A24C-DIAMOND'):
        return (('center', lane_mid), ('top', 0.0),
                'Base on the lane line at the word\'s near edge; centered in an 11 ft lane, move back to the setback')
    if code == 'CT-A24C-SHARROW':
        return (('center', -SHARROW_FROM_CURB), ('bottom', 0.0),
                'Base on the curb face; symbol center 11 ft from the curb (CA MUTCD 9E.09, with parking)')
    if code == 'CT-A24C-ISA':
        return (('center', STALL / 2), ('bottom', 0.0),
                'Base at the stall line corner at the stall end; centered in a 9 ft stall')
    if code.startswith('PM-BIKE-XING-GREEN') or code == 'PM-BIKE-LANE-SYMBOL-GREEN':
        return (('min', 0.0), ('bottom', 0.0),
                'Base at the upstream corner on the bike lane line; the width grows toward the curb')
    if group == 'Bicycle markings':
        return (('center', BIKE_LANE / 2), ('bottom', 0.0),
                'Base on the bike lane line at the symbol\'s upstream edge; centered in a 5 ft bike lane (CA MUTCD 9E.04)')
    if code == 'PM-YIELD-LINE-TRIANGLE':
        return (('min', 0.0), ('top', 0.0), 'Base on the yield line at the lane line; first triangle starts at the lane line')
    if code in BAR_CROSSWALK_GAP:
        g = BAR_CROSSWALK_GAP[code]
        return (('min', g), ('bottom', 0.0),
                f'Base at the curb corner on the near crosswalk edge; the pattern starts with a {g:g} ft gap at the curb, then a bar')
    if group == 'Crosswalks':
        return (('min', 0.0), ('bottom', 0.0), 'Base at the curb corner on the near crosswalk line')
    return None


def zoom(doc, margin=0.15):
    """Open every drawing zoomed to its content: the active model space view and the header extents
    fit the drawn geometry (block inserts included) with a small margin."""
    from ezdxf import bbox
    ext = bbox.extents(doc.modelspace(), fast=False)
    if not ext.has_data:
        return False
    w, h = ext.size.x, ext.size.y
    pad = margin * max(w, h, 1e-3)
    height = max(h + 2 * pad, (w + 2 * pad) / 1.6)   # a 16:10 window shows the full width too
    doc.set_modelspace_vport(height, center=(ext.center.x, ext.center.y))
    doc.header['$EXTMIN'] = (ext.extmin.x, ext.extmin.y, 0)
    doc.header['$EXTMAX'] = (ext.extmax.x, ext.extmax.y, 0)
    doc.header['$LIMMIN'] = (ext.extmin.x - pad, ext.extmin.y - pad)
    doc.header['$LIMMAX'] = (ext.extmax.x + pad, ext.extmax.y + pad)
    return True


def axis_angle(entities, share=0.6):
    """Rotation (degrees) that brings a block drawn at an angle back square to X and Y, or 0.
    Measured from straight edges: when one direction off both axes carries most of the edge length
    and almost none runs along X or Y, the block was drawn rotated in its source plan."""
    import math
    from collections import Counter
    h = Counter()
    for e in entities:
        t = e.dxftype()
        if t == 'LWPOLYLINE':
            p = list(e.get_points('xy'))
            segs = zip(p, p[1:] + (p[:1] if e.closed else []))
        elif t == 'LINE':
            segs = [(tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2])]
        else:
            continue
        for a, b in segs:
            length = math.dist(a, b)
            if length > 0.05:
                h[round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180)] += length
    total = sum(h.values())
    if not total:
        return 0.0
    on_axis = sum(v for k, v in h.items() if k % 90 in (0, 1, 89))
    top, length = h.most_common(1)[0]
    if on_axis / total > 0.05 or length / total < share or top % 90 in (44, 45, 46):
        return 0.0   # 45 degrees is a drawn shape (Type D loop diamond, crossbuck), not a rotated block
    return 90.0 - top        # the long direction runs along +Y, the travel direction


def pole_center(code, entities):
    """(x, y) of the pole circle a pole, post or standard symbol should insert at, or None when the
    base point already sits on a circle center or the symbol is not a pole type. Existing symbols draw
    the pole as dashed arcs, so arcs that share a center and radius count as one circle."""
    import math
    from collections import defaultdict
    if not any(k in code.upper() for k in POLE_SYMBOL):
        return None
    sweep = defaultdict(float)
    for e in entities:
        if e.dxf.get('layer') == NOPLOT or e.dxftype() not in ('CIRCLE', 'ARC'):
            continue
        key = (round(e.dxf.center.x, 4), round(e.dxf.center.y, 4), round(e.dxf.radius, 4))
        sweep[key] += 360.0 if e.dxftype() == 'CIRCLE' else (e.dxf.end_angle - e.dxf.start_angle) % 360
    circles = [k for k, v in sweep.items() if v >= 180]
    if not circles or any(math.hypot(x, y) < 1e-3 for x, y, _ in circles):
        return None
    x, y, _ = min(circles, key=lambda c: c[2])   # the pole: heads and faces are larger
    return x, y
