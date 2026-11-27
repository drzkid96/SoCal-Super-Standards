"""Size budget for the published site (GitHub Pages serves at most 1 GB).

Prints the size of each top-level section of dist/ and of the download store, writes the table
to the GitHub step summary when available, warns from warnBytes and fails above limitBytes.
"""
import json
import os
from pathlib import Path

LIMIT, WARN = 1_000_000_000, 900_000_000
dist = Path('dist')
sections = {}
for p in dist.rglob('*'):
    if p.is_file():
        top = p.relative_to(dist).parts[0] if len(p.relative_to(dist).parts) > 1 else '(root files)'
        sections[top] = sections.get(top, 0) + p.stat().st_size
total = sum(sections.values())
store = dist / 'data/asset-store.json'
stored = sum(a['bytes'] for a in json.loads(store.read_text())['assets']) if store.is_file() else 0
rows = ['| Section | MB |', '|---|---:|'] + [f'| {k} | {v/1e6:,.1f} |' for k, v in sorted(sections.items(), key=lambda kv: -kv[1])]
rows += [f'| **Pages total** | **{total/1e6:,.1f}** of {LIMIT/1e6:,.0f} |', f'| Download store (release) | {stored/1e6:,.1f} |']
report = '\n'.join(rows)
print(report)
if os.environ.get('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
        f.write('## Site size budget\n\n' + report + '\n')
if total > WARN:
    print(f'::warning::Site is {total/1e6:,.1f} MB of the {LIMIT/1e6:,.0f} MB Pages limit')
assert total <= LIMIT, f'Published site exceeds the 1 GB GitHub Pages limit: {total:,} bytes'
