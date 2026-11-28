"""Dynamic block plan page and family map.

Reads data/reference/dynamic-plan.json (revision 2: families drawn from the LA plan drawings, example dynamic
blocks kept as masters) and writes
  src/content/docs/cad/dynamic-blocks.md                 the plan, one card per dynamic block
  public/downloads/cad-tools/SSS-DYNAMIC-FAMILY-MAP.csv   block, dynamic block, state, master (drives build and swap)

  python3 pipeline/dynamic_plan.py
"""
import csv, io, json
from html import escape
from pathlib import Path

BASE = '/SoCal-Super-Standards'
PLAN = json.load(open('data/reference/dynamic-plan.json'))
ROUTE = {f.stem: r for r in ('markings', 'signals') for f in Path(f'public/downloads/{r}/cad').glob('*.dwg')}
E = lambda t: escape(str(t), quote=True)


def img(code, cls=''):
    route = ROUTE.get(code)
    if not route or not Path(f'public/block-previews/{route}/cad/{code}.svg').exists(): return ''
    return f'<img{cls} src="{BASE}/block-previews/{route}/cad/{code}.svg" alt="" loading="lazy" decoding="async">'


def card(f):
    kept = f['master'].endswith('-DYN')
    chips = ''.join(f'<li>{img(m["block"])}<span>{E(m["state"])}</span></li>' for m in f['members'])
    acts = ''.join(f'<li>{E(a)}</li>' for a in f['actions'])
    note = f'<p class="dyn-note">{E(f["note"])}</p>' if f['note'] else ''
    return (f'<article class="dyn-fam"><div class="dyn-hero">{img(f["master"])}</div><div class="dyn-meta">'
            f'<h4>{E(f["name"])}</h4><p class="dyn-src{" kept" if kept else ""}">{"Plan library dynamic block, kept as drawn" if kept else "Built from published blocks"}</p>'
            f'<dl><dt>Default</dt><dd>{E(f["default"])}</dd><dt>Base point</dt><dd>{E(f["base"])}</dd><dt>Condition</dt><dd>{E(f["cond"])}</dd></dl>'
            f'<ul class="dyn-acts">{acts}</ul>{note}</div>'
            f'<div class="dyn-from"><p><b>{len(f["members"])}</b> block{"s" if len(f["members"]) != 1 else ""} fold in</p><ul class="dyn-chips">{chips}</ul></div></article>')


def section(lib):
    out, groups = [], []
    fams = [f for f in PLAN['families'] if f['library'] == lib]
    for f in fams:
        if f['group'] not in groups: groups.append(f['group'])
    for g in groups:
        fs = [f for f in fams if f['group'] == g]
        if g == 'Survey kept as authored':
            tiles = ''.join(f'<li>{img(f["master"])}<span>{E(f["name"])}</span></li>' for f in fs)
            out.append(f'<h3>Kept as drawn · {len(fs)}</h3>\n\nEach of these survey blocks carries its own scale, stretch, alignment or rotation actions, so each stays its own block.\n\n<ul class="dyn-chips dyn-kept">{tiles}</ul>')
        else:
            out.append(f'<h3>{E(g)} · {len(fs)}</h3>\n<div class="dyn-list">{"".join(card(f) for f in fs)}</div>')
    return '\n\n'.join(out)


fams = PLAN['families']
count = lambda lib: (sum(1 for f in fams if f['library'] == lib), sum(len(f['members']) for f in fams if f['library'] == lib))
(mf, mn), (sf, sn), (vf, vn) = count('Markings'), count('Signals'), count('Survey')
kept = sum(1 for f in fams if f['master'].endswith('-DYN'))
md = f'''---
title: Dynamic blocks
description: How every pavement marking, signal and survey block folds into dynamic blocks, with masters kept from LA plan drawings, built-in setbacks, defaults, and line types in place of striping blocks.
tableOfContents: false
---

<div class="srcbar">Built from LA plan drawings: a signing and striping plan, a traffic signal plan and a topographic survey. Their dynamic blocks, line types and setbacks were read from the drawings. <a href="{BASE}/downloads/cad-tools/SSS-DYNAMIC-FAMILY-MAP.csv">Family map (CSV)</a></div>

<div class="dyn-figs"><p><b>{mn + sn + vn}</b> blocks</p><p><b>{len(fams)}</b> dynamic blocks</p><p><b>{kept}</b> plan library blocks kept as drawn</p><p><b>{len(PLAN["retired"])}</b> striping blocks now <a href="{BASE}/markings/line-types/#cad-line-types">line types</a></p></div>

- **Plan library blocks are the masters.** Where a plan drawing already has a dynamic block, it stays as drawn, with every state, flip, stretch and array.
- **Setbacks stay in the block.** WAIT HERE and STOP start 8 ft before the line, KEEP CLEAR and BUS ONLY 8 ft past it, and the bike symbol sits 12.9 ft behind the top of its green back.
- **One base point per block.** Blocks merge only when they share a base point and actions, so words before the line, words past the line, lane words, route words and warning words are separate blocks.
- **Defaults from the plans.** The bike lane marking on a green back, the continental crosswalk with 2 ft bars and 3 ft gaps (5 ft on center), and the first type of the Caltrans arrow set.
- **Conditions as the plans draw them.** Markings take proposed, existing or remove from the layer. Signal and survey blocks keep Existing, Proposed, Remove and Abandoned as states.
- **Lines are line types.** Stripes, conduit and utility lines use the [line type packages]({BASE}/markings/line-types/#cad-line-types).

<h2 id="markings">Pavement markings · {mn} blocks into {mf}</h2>

{section('Markings')}

<h2 id="signals">Signals and electrical · {sn} blocks into {sf}</h2>

{section('Signals')}

<h2 id="survey">Survey · {vn} blocks into {vf}</h2>

{section('Survey')}
'''
Path('src/content/docs/cad/dynamic-blocks.md').write_text(md)
buf = io.StringIO(); w = csv.writer(buf, lineterminator='\n')
w.writerow(['block', 'dynamic_block', 'state', 'master'])
for f in fams:
    for m in f['members']: w.writerow([m['block'], f['name'], m['state'], f['master']])
for r in PLAN['retired']: w.writerow([r['block'], 'line type', r['block'], r['replaced_by']])
Path('public/downloads/cad-tools/SSS-DYNAMIC-FAMILY-MAP.csv').write_text(buf.getvalue())
print(len(fams), 'dynamic blocks,', mn + sn + vn, 'blocks')
