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


def placement(code, group):
    """(rule key, dx-target, y-target, one-line description) for a marking block, or None to keep.

    x target: ('center', value) puts the geometry center at x = value; ('min', value) puts the left
    edge there; ('shaft', value) moves x = 0 (the arrow shaft) to value.
    y target: ('top', value) puts the downstream edge at y = value; ('bottom', value) the upstream edge.
    """
    lane_mid = LANE / 2
    if code.startswith('CT-DET'):
        return None
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
    if group == 'Crosswalks':
        return (('min', 0.0), ('bottom', 0.0), 'Base at the curb corner on the near crosswalk line')
    return None
