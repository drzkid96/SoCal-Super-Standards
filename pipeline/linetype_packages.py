"""Line type packages for SoCal Super Standards, extracted from LA plan drawings (Westwood signing and striping,
TS-1 and topographic survey). Their line type tables were read into data/reference/plan-linetypes.json
(ODA File Converter to DXF, then ezdxf). This writes the three .lin packages to public/downloads/cad-tools and
checks that every pattern parses.

  python3 pipeline/linetype_packages.py
"""
import json, math, os, re, ezdxf
L = json.load(open('data/reference/plan-linetypes.json'))

def fmt(v):
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s

def shape_name(rec):
    d = rec['desc'].lower()
    return 'BOX' if 'square' in d else 'CIRC1'

def body(rec):
    out = []
    for e in rec['els']:
        ln = e['len']
        flags = e.get('flags', 0)
        if flags and (e.get('text') is not None or e.get('shape')):
            rot = e.get('rot', 0.0)
            r = ('A=' if flags & 1 else 'R=') + fmt(rot)
            tail = f",S={fmt(e.get('scale', 1))},{r},X={fmt(e.get('x', 0))},Y={fmt(e.get('y', 0))}"
            if flags & 2 or 'ltypeshp' not in str(e.get('font')):
                if not flags & 2: e = dict(e, text='X')
                out.append(fmt(ln))
                out.append(f'["{e["text"]}",STANDARD{tail}]')
            else:
                out.append(fmt(ln))
                out.append(f'[{shape_name(rec)},ltypeshp.shx{tail}]')
        else:
            out.append(fmt(ln))
    return 'A,' + ','.join(out)

PACKS = {
 'SSS-STRIPING-PLAN.lin': ('Striping line types from LA plan sets (Westwood signing and striping, 2025). Units: feet, true length. '
                           'LTSCALE 1 and PSLTSCALE 0 so stripe and gap lengths read true in model space.',
   [('LANELN', 'Lane line 7 ft stripe 17 ft gap'),
    ('2WLTL', 'TWLTL and 45 mph line 12 ft stripe 36 ft gap'),
    ('BIKELN', 'Bike lane line 4 ft stripe 8 ft gap'),
    ('CATTRK', 'Cat track 2 ft stripe 8 ft gap'),
    ('ELETRK', 'Dotted extension 3 ft stripe 12 ft gap'),
    ('R-SOLID', 'Remove solid striping'),
    ('R-LANELN', 'Remove broken lane line'), ('R-2WLTL', 'Remove two-way left-turn lane line'),
    ('R-BIKELN', 'Remove bike lane line'), ('R-CATTRK', 'Remove cat track'), ('R-ELETRK', 'Remove elephant track')]),
 'SSS-SIGNAL-PLAN.lin': ('Signal and electrical line types from LA plan sets (Westwood TS-1, 2025). Units: feet, true length. '
                         'LTSCALE 1 and PSLTSCALE 0, as on the source sheet.',
   [('SIGCOND', 'Existing signal conduit'), ('R-SIGCOND', 'Remove signal conduit'), ('R-SIGEQ', 'Remove signal equipment'),
    ('SUBSTR', 'Substructure'), ('ABANDON', 'Abandon ---- A ----'), ('R-PEDPHASE', 'Remove pedestrian phase'),
    ('MMDASH', 'Match and limit dash')]),
 'SSS-SURVEY-UTILITY.lin': ('Survey and utility line types from the Westwood topographic survey and plan base (2025). '
                            'Units: plotted inches, PSLTSCALE 1 and MSLTSCALE 1. Text elements use the STANDARD style.',
   [('ELECTRIC LINE', ''), ('ELECTRIC PAINTED', ''), ('OVERHEAD LINE', ''), ('OVERHEAD ELECTRIC', ''), ('GAS LINE', ''),
    ('GAS PAINTED', ''), ('WATER LINE', ''), ('WATER PAINTED', ''), ('TELCO LINE', ''), ('TELCO PAINTED', ''),
    ('FIBER OPTIC', ''), ('STORM DRAIN', ''), ('STORM DRAIN PAINTED', ''), ('SANITARY SEWER PAINTED', ''),
    ('UNKNOWN PAINTED', ''), ('TOS', 'Top of slope'), ('TOE', 'Toe of slope'), ('Flowline', 'Flow line'), ('EP', 'Edge of pavement'),
    ('CL', 'Survey center line'), ('FENCE', 'Fence, x'), ('FENCELINE1', 'Fence, circle'), ('FENCELINE2', 'Fence, square'),
    ('CHAIN LINIK FENCE', 'Chain link fence'), ('BARBEDWIRE', 'Barbed wire'), ('DEACT', 'Deactivated underground conductor')]),
}
ALIAS = {'R-SOLID': 'R-Solid'}
os.makedirs('public/downloads/cad-tools', exist_ok=True)
report = {}
for fn, (head, items) in PACKS.items():
    lines = [f';; {fn[:-4]}', f';; {head}', ';; SoCal Super Standards. Load with LINETYPE > Load > File.', '']
    doc = ezdxf.new('R2018'); ok = 0
    for name, desc in items:
        rec = L[ALIAS.get(name, name)]
        out_name = name.upper().replace(' ', '-').replace('LINIK', 'LINK')
        d = (desc or rec['desc'] or out_name.title()).replace(',', ' -').strip()
        d = re.sub(r'\s+', ' ', d)[:47].rstrip(' ·(')
        b = body(rec)
        lines += [f'*{out_name},{d}', b]
        pat = re.sub(r'\[(BOX|CIRC1),ltypeshp\.shx', lambda m: '[' + ('132' if m[1]=='BOX' else '133') + ',ltypeshp.shx', b[2:])
        total = sum(abs(e['len']) for e in rec['els'])
        doc.linetypes.add(out_name, pattern=pat if '[' in pat else [total] + [e['len'] for e in rec['els']], description=d, length=total)
        ok += 1
    open(f'public/downloads/cad-tools/{fn}', 'w', newline='\r\n').write('\n'.join(lines) + '\n')
    report[fn] = ok
print(report)
