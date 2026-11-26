"""Index sign evidence across the three 3346 CAD drawings and their non-plot definitions.

Run with --dxf-dir containing the three decoded R2000 .dxf files (named with the
source IDs below), --original-dir for the original .dwg files and --face-dir for
reviewed 3346*.json face selections. Reviewed selections specify exact handles and
may describe an uncoded face in the drawing's own words.
"""
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf
from ezdxf.dynblkhelper import get_dynamic_block_record_handle
from ezdxf.entities.acad_table import read_acad_table_content
from ezdxf.tools.text import plain_mtext

from extract_cad_signs import content

SOURCES = {
    "3346-signs-1-13": "3346-SIGNS_1-13.dwg",
    "3346-signs-14-15": "3346-SIGNS_14-15.dwg",
    "3346-title-details": "3346-SS-TITLE_DETAILS.dwg",
}
CODE = re.compile(
    r"""(?<![a-z0-9-])(?P<base>T-[KN]|R-1|N-1|(?:OM|SW|SR|[WRDMS])\d+[a-z]?(?:-\d+[a-z]{0,3})?)(?![a-z\d-])"""
    r"""(?P<qual>(?:\s*\(\s*(?:CA|M[O0]D(?:\s+(?:\d+|"OVER 3 TONS"))?|LT|RT|L/R|L|R|S|WHITE ON GREEN|[←↑→]+|"[^"()]{1,45}"|\d{1,3})\s*\))*)""",
    flags=re.I,
)
# These exact uncoded sign or marker labels occur in project CAD callouts. Compound
# callouts can mix coded and uncoded faces, with soft line breaks inside a name.
UNNUMBERED = (
    "City Dockless Mobility Ride Safety Sign", "City Dockless Mobility Parking Sign",
    "Harper Avenue Historic District Sign", "Parking Restrictions Warning Sign",
    "Turn Wheels City Custom Sign", "Custom Turn Wheels City Sign", "Turn Wheels Custom Sign",
    "Vehicle Speed Feedback Sign", "Neighborhood Watch Sign", "Parking Permit Sign",
    "Watch Opposing Traffic Sign", "Cityline Bus Sign", "Spaulding Square Sign",
    "Courtyard District Sign", "Custom Wayfinding Sign", "Custom City Dog Sign",
    "Plummer Park Parking Sign", "On Sidewalk Sign", "CUSTOM CITYWIDE NO PARKING SIGN",
    "TYPE Q OBJECT MARKER", "TYPE G MARKER",
)
UNCODED = re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, UNNUMBERED)) + r")(?:S(?=\b))?(?![a-z])", re.I)
SINGLE_BASE = re.compile(r"(?:OM|SW|SR|[WRDMS])\d+[a-z]?", re.I)
SPACE = re.compile(r"\s+")
CODEPOINT = re.compile(r"\\U\+([\da-f]{4})", re.I)
CLEAN_QTY = {"R9-3 (2)": "R9-3"}

def clean(value):
    # DXF embeds Unicode escapes on arrows and inline formatting in leader calls.
    value = CODEPOINT.sub(lambda m: chr(int(m[1], 16)), value)
    return SPACE.sub(" ", plain_mtext(value).replace("^J", " ")).strip()

def matches(value):
    value = clean(value)
    for match in CODE.finditer(value):
        base, quals = match["base"], match["qual"]
        if not quals and SINGLE_BASE.fullmatch(base):
            continue
        label = match.group().strip()
        yield CLEAN_QTY.get(label, label), label
    for match in UNCODED.finditer(value):
        yield match[1], match.group()

def collect(source, drawing, faces, original):
    layouts = {layout.block_record_handle: layout.name for layout in drawing.layouts}
    by_name = {block.name.casefold(): block for block in drawing.blocks}
    refs = defaultdict(set)
    direct = defaultdict(set)
    dynamic = {}
    for block in drawing.blocks:
        parent = get_dynamic_block_record_handle(block.block_record)
        if parent and (record := drawing.entitydb.get(parent)):
            dynamic[block.name] = record.dxf.name
        for entry in block.query("INSERT"):
            if target := by_name.get(entry.dxf.name.casefold()):
                direct[block.name].add(target.name)
    for block in drawing.blocks:
        if location := layouts.get(block.block_record_handle):
            pending = [block.name]
            while pending:
                name = pending.pop()
                if location in refs[name]:
                    continue
                refs[name].add(location)
                pending.extend(direct[name])
    records = {}
    seen = set()
    templates = {}
    face_handles = set()
    counts = Counter()
    table_entities = []

    def record(designation, raw, block, handle, kind, extra=None):
        key = designation.casefold()
        loc = layouts.get(block.block_record_handle)
        observation = (key, handle, kind, (extra or {}).get("cell"))
        if observation in seen:
            return
        seen.add(observation)
        item = records.setdefault(key, {"source": source, "designation": designation, "evidence": []})
        if raw != item["designation"] and raw != "R9-3 (2)":
            item.setdefault("aliases", set()).add(raw)
        evidence = {
            "kind": kind, "handle": handle, "space": loc or block.name, "label": raw,
            "use": "layout" if loc else "nested definition" if refs[block.name] else "unplaced definition",
        }
        if not loc:
            evidence["definitionHandle"] = block.block_record_handle
            if refs[block.name]:
                evidence["layouts"] = sorted(refs[block.name])
            if block.name in dynamic:
                evidence["dynamicParent"] = dynamic[block.name]
        if extra:
            evidence.update(extra)
        item["evidence"].append(evidence)

    # A reviewed caption or named drawing is the preferred display spelling for
    # the same case-insensitive CAD key. Keep distinct directional and MOD suffixes.
    for face in faces:
        name = face["code"]
        block = by_name[face["block"].casefold()]
        kind = "block definition" if face["sourceKind"] == "block" else "reviewed sign face"
        evidence = {"block": block.name, "definitionHandle": block.block_record_handle}
        if face.get("imageHandle"):
            evidence["imageHandle"] = face["imageHandle"]
        if face.get("sizeInches"):
            evidence.update(sizeInches=face["sizeInches"], sizeEvidence=face.get("sizeEvidence"))
        if face.get("note") or face.get("notes"):
            evidence["note"] = face.get("note") or face["notes"]
        if face.get("referenceURL"):
            evidence["referenceURL"] = face["referenceURL"]
        record(name, name, block, face["handle"], kind, evidence)
        face_handles.add(face["handle"])
        if kind == "block definition":
            templates[block.name.casefold()] = name

    def check(value, block, handle, kind, extra=None):
        for name, raw in matches(value):
            m = re.search(re.escape(raw) + r'\s*\((\d+)\s*"\s*[X×]\s*(\d+)\s*"\)', clean(value), re.I)
            attributes = dict(extra or {})
            if m:
                attributes.update(sizeInches=[int(m[1]),int(m[2])], sizeEvidence={"kind":"drawing dimension note","handle":handle,"text":m.group()})
            record(name, raw, block, handle, kind, attributes)

    for block in drawing.blocks:
        for entity in block:
            typ = entity.dxftype()
            counts[typ] += 1
            handle = entity.dxf.handle
            if typ == "INSERT":
                target = entity.dxf.name.casefold()
                if target in templates:
                    name = templates[target]
                    record(name, name, block, handle, "block insertion", {"block": by_name[target].name})
                for attr in entity.attribs:
                    counts["ATTRIB"] += 1
                    check(content(attr), block, attr.dxf.handle, "attribute",
                          {"insert": handle, "tag": attr.dxf.tag})
            elif typ == "ACAD_TABLE":
                table = read_acad_table_content(entity)
                table_entities.append({"handle": handle, "space": layouts.get(block.block_record_handle, block.name),
                                       "rows": len(table)})
                for i, cells in enumerate(table):
                    for j, value in enumerate(cells):
                        check(value, block, handle, "table cell", {"cell": f"{i+1},{j+1}"})
            if handle not in face_handles and (value := content(entity)):
                check(value, block, handle, typ.lower())
    for item in records.values():
        name = item["designation"]
        base = re.split(r"\s*\(", name)[0]
        if "(MOD" in name.upper() or "-MOD" in name.upper():
            item["variant"] = "modified"
        if base != name:
            base += "(CA)" if "(CA)" in name.upper() else ""
            if name != base:
                item["base"] = base
        if not re.match(r"^(?:[A-Z]{1,2}-?\d|T-[NK])",name, re.I):
            item["kind"] = "uncoded local sign or marker"
        if "aliases" in item:
            item["aliases"] = sorted(item["aliases"])
        item["evidence"].sort(key=lambda e: (e["space"], int(e["handle"],16), e["kind"]))
    rows = sorted(records.values(), key=lambda i: i["designation"].casefold())
    audit = {
        "source": source, "file": original.name, "sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
        "dwgVersion": original.read_bytes()[:6].decode("ascii"), "units": drawing.header.get("$INSUNITS",0),
        "layouts": sorted(layouts.values()), "blockRecords": len(drawing.blocks),
        "anonymousBlockRecords": sum(b.name.startswith(("*","A$")) and b.block_record_handle not in layouts
                                     for b in drawing.blocks),
        "dynamicParentLinks": len(dynamic), "xrefDefinitions": sum(bool(b.block.dxf.flags & 4) for b in drawing.blocks),
        "tables": table_entities, "entities": dict(sorted(counts.items())),
        "sourceDesignations": len(rows), "reviewedFaceObservations": len(faces),
        "evidenceRecords": sum(len(r["evidence"]) for r in rows),
        "sourceLimitations": [
            "Plan labels, definition names and face captions can refer to the same physical sign.",
            "The source includes working legends beyond plot limits and unplaced definitions. Their status is recorded.",
            "Uncoded sign and marker callouts retain their source wording. Symbols for a sign location or post are not artwork of its face.",
        ],
    }
    if source == "3346-signs-14-15":
        audit["sourceLimitations"].append("The supplied file contains Model and SS-14. There is no separate SS-15 layout.")
    if source == "3346-signs-1-13":
        audit["withheldFaceObservations"] = [
            {"handle": "10980D1", "label": "R2-1(25)", "reason": "The drawn legend reads 30. The supplied corrected 25 MPH face uses the independent SDDCTEA sign illustration."},
            {"handle": "1098602", "label": "R2-1(30)", "reason": "The ATTDEF default at 109868B reads 55. The separate face 109879A depicts 30."},
            {"handle": "1098289", "label": "D11-1", "reason": "Detached caption and size."},
            {"handle": "10A0FA4", "label": "R9-3a", "reason": "Detached caption beside no-plot construction graphics."},
            {"handle": "10A1076", "label": "R10-12", "reason": "Detached caption beside no-plot construction graphics."},
        ]
    return rows, audit

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for opt in ("dxf-dir","original-dir","face-dir"):
        parser.add_argument("--"+opt, type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1]/"data/reference/plan-examples")
    args = parser.parse_args()
    selections = defaultdict(list)
    for file in sorted(args.face_dir.glob("3346*.json")):
        for face in json.loads(file.read_text()):
            selections[face["drawing"]].append(face)
    rows, audits = [], []
    for source, filename in SOURCES.items():
        drawing = ezdxf.readfile(args.dxf_dir/(source+".dxf"))
        found, audit = collect(source, drawing, selections[source], args.original_dir/filename)
        rows.extend(found)
        audits.append(audit)
    args.out.mkdir(parents=True,exist_ok=True)
    for name, result in (("3346-sign-records",rows),("3346-sign-audit",audits)):
        (args.out/(name+".json")).write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"))+"\n")
    print([(a["source"], a["sourceDesignations"], a["evidenceRecords"], a["reviewedFaceObservations"]) for a in audits])

if __name__ == "__main__":
    main()
