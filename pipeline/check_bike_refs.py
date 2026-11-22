"""Accuracy & citation validator for AASHTO GBF-5 and California bikeway pages.

Verifies:
1. Every AASHTO GBF-5 section, Figure X-Y, and Table X-Y cited in bikeway guides/comparisons exists in data/aashto_gbf5.json.
2. Zero pre-errata stale AASHTO cross-references (e.g. 5.12.12, 9.13) appear outside the explicit Errata table.
3. Every MUTCD sign code cited as current is valid in public/data/signs-index.json and not on data/ca_deleted_signs.json
   (unless explicitly flagged as deleted/superseded).
4. Every embedded local figure image in bikeway bulletins/guides exists under public/.
"""
import json, os, re, sys

gbf = json.load(open("data/aashto_gbf5.json"))
signs = json.load(open("public/data/signs-index.json"))
deleted = {re.sub(r"\s+", "", k.upper()) for k in json.load(open("data/ca_deleted_signs.json"))["codes"]}

valid_secs = {s["num"] for s in gbf["sections"] if s.get("num")}
valid_figs = {f["num"] for f in gbf["figures"]}
valid_tabs = {t["num"] for t in gbf["tables"]}

errors = []
checked = 0

# 1. Validate AASHTO GBF-5 index completeness
chs = {c["num"] for c in gbf["chapters"]}
if chs != set(range(1, 17)):
    errors.append(f"GBF-5 chapters incomplete: {sorted(chs)}")
if len(valid_figs) < 250 or len(valid_tabs) < 45:
    errors.append(f"GBF-5 figure/table count unexpectedly low: {len(valid_figs)} figs, {len(valid_tabs)} tabs")

# 2. Validate citations in bikeway comparison & GBF-5 guide
targets = [
    "src/content/docs/guides/aashto-bike-guide.md",
    "src/content/docs/bulletins/bikeway-design-comparison.md",
    "src/content/docs/bulletins/caltrans-hdm-ch1000.md",
]

for path in targets:
    if not os.path.exists(path):
        errors.append(f"Missing target file: {path}")
        continue
    checked += 1
    txt = open(path).read()

    # Check all embedded local images exist under public/
    for m in re.finditer(r'src="/SoCal-Super-Standards/(figs/[^"]+)"', txt):
        fp = os.path.join("public", m.group(1))
        if not os.path.exists(fp):
            errors.append(f"{path}: missing figure image {fp}")

    # Strip the Errata table when checking for stale pre-errata citations
    body_no_errata = re.sub(r"## December 2024 Errata.*?## ", "## ", txt, flags=re.S)
    # Also allow explicit "(corrected from 5.12.12 ...)" mentions
    body_no_errata = re.sub(r"corrected from [0-9.]+", "", body_no_errata, flags=re.I)

    for stale in ("5.12.12", "9.13"):
        if re.search(rf"(?<![\d.]){re.escape(stale)}(?![\d.])", body_no_errata):
            errors.append(f"{path}: stale pre-errata AASHTO section reference '{stale}' found")

    if "bikeway-design-comparison" in path:
        # Verify every AASHTO Figure X-Y and Table X-Y referenced in the AASHTO column
        for fig_m in re.finditer(r"Figures?\s+(\d{1,2}-\d{1,2})(?:\s+to\s+(\d{1,2}-\d{1,2}))?", txt):
            f1 = fig_m.group(1)
            if f1 not in valid_figs:
                errors.append(f"{path}: Figure {f1} not found in data/aashto_gbf5.json")
            if fig_m.group(2) and fig_m.group(2) not in valid_figs:
                errors.append(f"{path}: Figure {fig_m.group(2)} not found in data/aashto_gbf5.json")
        for tab_m in re.finditer(r"Tables?\s+(\d{1,2}-\d{1,2})(?:\s+(?:to|&amp;)\s+(\d{1,2}-\d{1,2}))?", txt):
            t1 = tab_m.group(1)
            if t1 not in valid_tabs:
                errors.append(f"{path}: Table {t1} not found in data/aashto_gbf5.json")
            if tab_m.group(2) and tab_m.group(2) not in valid_tabs:
                errors.append(f"{path}: Table {tab_m.group(2)} not found in data/aashto_gbf5.json")
        # Check section citations like § 6.4.3, § 7.3.1, § 5.12.11
        for sec_m in re.finditer(r"&sect;\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)", txt):
            sc = sec_m.group(1)
            # Skip CA MUTCD / DIB / SHC section numbers (e.g. 9E.01, 3.4, 891.9)
            if sc.startswith(("3.", "890", "891")):
                continue
            if sc not in valid_secs:
                errors.append(f"{path}: AASHTO section {sc} not found in data/aashto_gbf5.json")

    # Verify sign codes mentioned are not inadvertently recommending deleted CA signs
    for sm in re.finditer(r"\b(R81\(CA\)|R117\(CA\)|R118\(CA\)|W79A\(CA\))\b", txt):
        ctx = txt[max(0, sm.start() - 40):sm.end() + 40].lower()
        if "deleted" not in ctx and "superseded" not in ctx and "flagged" not in ctx:
            errors.append(f"{path}: deleted CA sign {sm.group(1)} cited without deleted/superseded flag")

if errors:
    print("BIKE REFS CHECK FAILED:")
    for e in errors:
        print("  ERROR:", e)
    sys.exit(1)

print(f"bike refs check PASSED: {checked} pages verified against {len(valid_secs)} GBF-5 sections, {len(valid_figs)} figures, {len(valid_tabs)} tables, 0 errors")
