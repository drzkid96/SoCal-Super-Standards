"""Review drawing sign evidence from local LibreDWG R2000 DXFs. No drawing geometry is published.

Run from the repository root:
  python pipeline/extract_cad_signs.py --geo <geo.dxf> --pico <pico.dxf> --originals <DWG directory>
A malformed GEODATA mesh in these two source conversions is dropped from the input
stream. This operation affects the georeference object, not block or layout entities.
"""

import argparse
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path, PureWindowsPath

import ezdxf
from ezdxf.dynblkhelper import get_dynamic_block_record_handle
from ezdxf.tools.text import plain_mtext

DEST = Path("data/reference/plan-examples")
BASE = r"(?:OM\d+-\d+|(?:SW|SR|SC|R|W|G|C|M|D|S)\d+[a-z]?(?:-\d+[a-z]{0,3})?|N-1)"
CUSTOM = r'(?:ASSEMBLY\s*"[CD]"|TYPE\s+[NP]|PCMS\s*"[ABDF]"|SIGN\s*"[AB]"|SS[12])'
QUALIFIERS = r"(?:\s*\(\s*(?:CA|MOD(?:\s+[AB])?|LT/RT|LT|RT|L|R|RED|\d{1,4})\s*\))*"
SIGN = re.compile(
    r"(?<![A-Z0-9])(?P<base>" + BASE + "|" + CUSTOM + r")(?P<qual>" + QUALIFIERS + r")(?![A-Z0-9])",
    re.IGNORECASE,
)
# Local abbreviations are reported as the source spells them, without assigning a standard number.
LOCAL = re.compile(
    r"(?<![A-Z0-9])(?:T\.A\.N\.S\.A\.T\.|T\.A\.N\.S\.|T\.A\.N\.P\.|N\.P\.A\.T\.|P\.M\.Z\.|P\.L\.Z\.|C\.L\.Z\.|BUS ZONE|DASH ZONE|E\.V\. CHARGING ONLY|COMMERCIAL LOADING ONLY|PASSENGER LOADING ONLY|TRANSIT BUSES EXEMPT(?:ED)?|ZERO EMISSION VEHICLE)(?![A-Z])",
    re.IGNORECASE,
)
# Complete parking and loading restrictions often use hours or minutes as the only label.
TIME_LIMIT = re.compile(
    r"(?<![A-Z0-9])(?P<duration>\d+)\s*(?P<unit>HRS?|HOURS?|MIN(?:UTE)?S?)\.?\s*(?:PKG\.?|PARKING|LIMIT)(?=\s|$|[,.)])",
    re.IGNORECASE,
)
NO_PARKING = re.compile(r"(?<![A-Z])NO\s+(?:PKG\.?|PARKING)(?=\s|$|[,.)])", re.IGNORECASE)
# Bare code families reviewed against every match in the two source drawings.
BARE = {"G27", "G28", "R41", "R99C", "SW44", "W53", "W74", "W16", "W48"}
SPECIAL = {"G27", "G28", "_R1-5(MOD)", "_R10-15(MOD)", "__R10-15(MOD)"}
GEODATA = re.compile(rb"(?m)^  0\r?\nGEODATA\r?\n(?:(?!^  0\r?$)[\s\S])*")


def label(value):
    value = value.replace("–", "-").replace("−", "-").replace("%%U", "").replace("%%u", "")
    value = plain_mtext(value) if "\\" in value else value
    return value.replace("^J", "\n")


def labels(value, layer, named=False):
    text = label(value)
    for match in SIGN.finditer(text):
        base = match["base"].upper().strip()
        quals = re.findall(r"\(([^)]+)\)", match["qual"].upper())
        # Exclude map grids, DWG and standard plan numbers, and CAD formatting control codes.
        if re.fullmatch(r"(?:SW|SR|SC|R|W|G|C|M|D|S)\d+[A-Z]?", base) and not (quals or base in BARE):
            continue
        needs_context = base.startswith(("TYPE ", "ASSEMBLY")) or base in {"SS1", "SS2"}
        sign_context = "SIGN" in layer or (base in {"SS1", "SS2"} and "TEXT" in layer) or "CA" in quals
        if needs_context and not sign_context:
            continue
        if base.startswith(("ASSEMBLY", "SIGN", "PCMS")):
            base = re.sub(r'\s*"', ' "', base, count=1)
        # A parenthetical (2) is a quantity for these source labels. Legends on speed and weight signs are retained.
        quals = [q.strip() for q in quals if q.strip() != "2"]
        suffix = "".join("(" + q + ")" for q in quals)
        raw = match.group(0).strip()
        display = (
            re.sub(r"(?<=\d)([abcefg])(?=P?$)", lambda x: x[0].lower(), base, flags=re.IGNORECASE)
            if "-" in base and not base.startswith(("D9", "G", "SW"))
            else base
        )
        yield display + suffix, raw, display, quals
    if not named and ("SIGN" in layer or layer == "B-TEXT" or layer == "P-CURB-PAINT"):
        for match in LOCAL.finditer(text):
            yield match.group().upper(), match.group(), None, []
        if "SIGN" in layer:
            for line in text.splitlines():
                if len(line) > 120:
                    continue
                if match := TIME_LIMIT.search(line):
                    unit = "HR" if match["unit"].upper().startswith("H") else "MIN"
                    yield match["duration"] + " " + unit + " PARKING LIMIT", line.strip(), None, []
                if NO_PARKING.match(line.strip()):
                    yield "NO PARKING (UNCODED)", line.strip(), None, []


def content(entity):
    typ = entity.dxftype()
    if typ in ("TEXT", "ATTRIB", "ATTDEF"):
        value = entity.plain_mtext() if getattr(entity, "has_embedded_mtext_entity", False) else entity.dxf.text
        return value
    if typ == "MTEXT":
        return entity.plain_text()
    if typ in ("MLEADER", "MULTILEADER") and entity.context.mtext:
        return entity.context.mtext.default_content
    return ""


def load(path):
    raw = path.read_bytes()
    sanitized, removed = GEODATA.subn(b"", raw)
    return ezdxf.read(io.StringIO(sanitized.decode("cp1252", errors="replace").replace("\r\n", "\n"))), removed


def extract(source, path, original_path):
    drawing, geo_skipped = load(path)
    by_name = {b.name.casefold(): b.name for b in drawing.blocks}
    layouts = {l.block_record_handle: l.name for l in drawing.layouts}
    used_by = defaultdict(set)
    children = defaultdict(list)
    inserted_on_sign_layer = set()
    inherited_children = defaultdict(set)
    dynamic = {}
    for block in drawing.blocks:
        handle = get_dynamic_block_record_handle(block.block_record)
        if handle and handle in drawing.entitydb:
            dynamic[block.name] = drawing.entitydb[handle].dxf.name
        for entity in block:
            target = None
            kind = entity.dxftype()
            if kind == "INSERT":
                target = entity.dxf.name
            elif kind in {"DIMENSION", "ARC_DIMENSION"}:
                target = entity.dxf.get("geometry", "")
            elif kind in {"MLEADER", "MULTILEADER"} and entity.context.block:
                ref = getattr(entity.context.block, "block_record_handle", None)
                if ref and ref in drawing.entitydb:
                    target = drawing.entitydb[ref].dxf.name
            if target and target.casefold() in by_name:
                child = by_name[target.casefold()]
                children[block.name].append(child)
                if kind == "INSERT" and "SIGN" in entity.dxf.layer.upper():
                    inserted_on_sign_layer.add(child)
                elif kind == "INSERT" and entity.dxf.layer == "0":
                    inherited_children[block.name].add(child)
    # Layer 0 inherits the containing insert layer, including across nested blocks.
    remaining = list(inserted_on_sign_layer)
    while remaining:
        name = remaining.pop()
        children_to_visit = inherited_children[name] - inserted_on_sign_layer
        inserted_on_sign_layer.update(children_to_visit)
        remaining.extend(children_to_visit)
    for block in drawing.blocks:
        root = layouts.get(block.block_record_handle)
        if not root:
            continue
        pending = [block.name]
        while pending:
            name = pending.pop()
            if root in used_by[name]:
                continue
            used_by[name].add(root)
            pending.extend(children[name])
    templates = defaultdict(set)
    for name, template in dynamic.items():
        templates[template].update(used_by[name])
    records = {}
    detail_index = json.loads((DEST / "cad-sign-detail-evidence.json").read_text())[source]
    detail_records = {
        entry[0]: entry[1] for entry in json.loads((DEST / "cad.json").read_text())[source]["rows"]
    }
    detail_handles = {}
    for relation in detail_index:
        detail_id, heading, *handles = relation
        title = label(content(drawing.entitydb[heading])).upper()
        if 'DETAIL "' + detail_records[detail_id] + '"' not in title:
            raise ValueError("Detail heading no longer matches " + detail_id + " at " + heading)
        for handle in handles:
            if handle in detail_handles or handle not in drawing.entitydb:
                raise ValueError("Unexpected detail evidence " + handle)
            detail_handles[handle] = (detail_id, heading)
    total = Counter()
    xref = []
    image_uses = defaultdict(list)
    unresolved = []

    def note(value, layer, typ, handle, b, extra=None):
        for name, raw, base, quals in labels(value, layer, typ == "block definition"):
            row = records.setdefault(
                name, {"designation": name, "source": source, "aliases": set(), "evidence": []}
            )
            if base is not None and raw.upper() != name.upper() and "(2)" not in raw:
                row["aliases"].add(raw)
            if quals:
                unchanged = [q for q in quals if q == "CA"]
                parent = base + "".join("(" + q + ")" for q in unchanged)
                if parent != name:
                    row["base"] = parent
                if any(q.startswith("MOD") for q in quals):
                    row["variant"] = "modified"
            if base is None:
                row["kind"] = "uncoded local sign callout"
            loc = layouts.get(b.block_record_handle) if b else None
            space = loc or (b.name if b else "Image dictionary")
            placements = sorted(used_by.get(b.name, set())) if b else []
            state = "layout" if loc else "nested definition" if placements else "unplaced definition"
            entry = {"kind": typ, "handle": handle, "space": space, "use": state, "label": raw}
            if b and not loc:
                entry["definitionHandle"] = b.block_record_handle
                if placements:
                    entry["layouts"] = placements
                if b.name in dynamic:
                    entry["dynamicParent"] = dynamic[b.name]
            if handle in detail_handles:
                detail_id, heading = detail_handles[handle]
                entry.update(detailID=detail_id, headingHandle=heading)
            if b and not placements and templates.get(b.name):
                entry["use"] = "dynamic template"
                entry["layouts"] = sorted(templates[b.name])
            if extra:
                entry.update(extra)
            row["evidence"].append(entry)

    for b in drawing.blocks:
        if b.block.dxf.flags & 4:
            xref.append(b.name)
        if b.name in SPECIAL:
            note(b.name.strip("_"), "SIGN", "block definition", b.block_record_handle, b)
        for e in b:
            typ = e.dxftype()
            total[typ] += 1
            if typ == "IMAGE":
                image_uses[e.dxf.image_def_handle].append((b, e))
            if typ == "INSERT":
                actual = by_name.get(e.dxf.name.casefold(), e.dxf.name)
                effective = dynamic.get(actual, actual)
                if effective in SPECIAL:
                    extra = {"block": actual, "definitionHandle": drawing.blocks[actual].block_record_handle}
                    route_number = next(
                        (a for a in e.attribs if a.dxf.tag == "NO." and a.dxf.text.strip()), None
                    )
                    if route_number:
                        extra.update(
                            legend=route_number.dxf.text.strip(), legendAttributeHandle=route_number.dxf.handle
                        )
                    note(effective.strip("_"), e.dxf.layer.upper(), "block insert", e.dxf.handle, b, extra)
                for a in e.attribs:
                    total["ATTRIB"] += 1
                    note(
                        content(a),
                        e.dxf.layer.upper(),
                        "attribute",
                        a.dxf.handle,
                        b,
                        {"insert": e.dxf.handle, "tag": a.dxf.tag},
                    )
            txt = content(e)
            if txt:
                layer = e.dxf.layer.upper()
                inherited = layer == "0" and b.name in inserted_on_sign_layer
                note(
                    txt,
                    "SIGN" if inherited else layer,
                    typ.lower(),
                    e.dxf.handle,
                    b,
                    {"layer": "0", "inheritedSignLayer": True} if inherited else None,
                )
                clean = label(txt).strip()
                if clean in {"W11-(2)", "(MOD B)(2)"}:
                    unresolved.append(
                        {
                            "text": clean,
                            "handle": e.dxf.handle,
                            "space": layouts.get(b.block_record_handle, b.name),
                        }
                    )
    dictionary = drawing.rootdict.get("ACAD_IMAGE_DICT", {})
    for _, img in dictionary.items():  # noqa: PERF102 -- ezdxf Dictionary exposes items(), not values().
        if not img or img.dxftype() != "IMAGEDEF":
            continue
        basename = PureWindowsPath(img.dxf.filename).stem
        if not basename or "traffic_sign" not in img.dxf.filename.casefold():
            continue
        references = image_uses.get(img.dxf.handle, [])
        for b, e in references:
            note(
                basename, "SIGN", "external image insert", e.dxf.handle, b, {"imageDefinition": img.dxf.handle}
            )
        note(
            basename,
            "SIGN",
            "external image definition",
            img.dxf.handle,
            None,
            {"use": "referenced image definition" if references else "unplaced external image definition"},
        )
    output = []
    for row in records.values():
        row["aliases"] = sorted(row["aliases"])
        if not row["aliases"]:
            row.pop("aliases")
        row["evidence"].sort(key=lambda v: (v["space"], int(v["handle"], 16), v["label"]))
        details = sorted({e["detailID"] for e in row["evidence"] if "detailID" in e})
        if details:
            row["detailIDs"] = details
        output.append(row)
    report = {
        "source": source,
        "file": original_path.name,
        "sha256": hashlib.sha256(original_path.read_bytes()).hexdigest(),
        "dwgVersion": original_path.read_bytes()[:6].decode(),
        "units": drawing.header.get("$INSUNITS", 0),
        "decoder": "LibreDWG R2000 DXF",
        "geodataObjectsOmitted": geo_skipped,
        "layouts": list(layouts.values()),
        "blockRecords": len(drawing.blocks),
        "anonymousBlockRecords": sum(
            b.name.startswith("*") and b.block_record_handle not in layouts for b in drawing.blocks
        ),
        "dynamicParentLinks": len(dynamic),
        "xrefDefinitions": len(xref),
        "entities": dict(sorted(total.items())),
        "namedImageReferences": sum(1 for _, img in dictionary.items() if img and img.dxf.filename),
        "externalSignImageDefinitions": sum(
            1 for _, img in dictionary.items() if img and "traffic_sign" in img.dxf.filename.casefold()
        ),
        "sourceLimitations": [
            "An external image definition is identified only by its source name when its bitmap is absent.",
            "Paper-space evidence can occur outside plot extents. Model-space evidence includes earlier working geometry.",
            "Counts identify source entities and definitions. Separate entities can refer to the same physical sign.",
        ],
        "unresolvedLabels": unresolved,
        "linkedDetails": len({v[0] for v in detail_handles.values()}),
        "detailCallouts": len(detail_handles),
        "sourceDesignations": len(output),
        "evidenceRecords": sum(len(e["evidence"]) for e in output),
    }
    # Audit only after extraction; dictionary-link repair must not alter original evidence handles.
    audit = drawing.audit()
    report["structuralAudit"] = {
        "errors": len(audit.errors),
        "fixesByKind": dict(Counter(issue.code.name for issue in audit.fixes)),
    }
    if audit.errors:
        raise ValueError(f"{source}: unresolved DXF structural errors")
    return sorted(output, key=lambda r: r["designation"]), report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("geo", "pico", "originals"):
        parser.add_argument("--" + key, required=True, type=Path)
    opt = parser.parse_args()
    rows = []
    reports = []
    for source in ("geo", "pico"):
        original = next(p for p in opt.originals.glob("*.dwg") if source.upper() in p.name.upper())
        records, report = extract(source, getattr(opt, source), original)
        rows.extend(records)
        reports.append(report)
    for name, data in [("cad-signs.json", rows), ("cad-signs-audit.json", reports)]:
        (DEST / name).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    print([(r["source"], r["sourceDesignations"], r["evidenceRecords"]) for r in reports])


if __name__ == "__main__":
    main()
