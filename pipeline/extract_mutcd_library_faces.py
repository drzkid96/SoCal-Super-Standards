"""Extract individual faces from the exploded MUTCD-StandardSigns.dwg library.

The TSV binds the printed code handle to the reviewed face entities in modelspace.
Its compact hexadecimal ranges are inclusive. Handles were identified by joining
touching primitives, enclosing disconnected lettering inside its board, then
checking label placement, native draw order and multi-panel assemblies. Using the
reviewed handles prevents adjacent plaques and modelspace labels from bleeding
into individual blocks. Any leftover modelspace entity causes an audit failure.
"""

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

import ezdxf
from ezdxf import bbox

DRAWING = "mutcd-standard-signs"
TABLE = Path(__file__).with_name("mutcd_library_face_handles.tsv")

# Every exclusion is a reviewed entity in this particular drawing. The repeated
# circled P and the empty circles sit outside the R10-series panel boundaries.
EXCLUSIONS = {
    "sheet border": "12969-12972,12A3D",
    "drawing path annotation": "12D4E",
    "separate circular equipment symbol outside panel": (
        "10E52-10E53,10E5F-10E60,10E86-10E87,10E8D-10E8E,10EA5-10EA6,"
        "10EBA-10EBB,10ECC-10ECD,10EE4-10EE5,10EF8-10EF9,10F29-10F2A,"
        "10F59-10F5A,10FE2,10FEE,10FF7,121E6-121E7"
    ),
    "isolated point or zero-length polyline": "104F8,10EF7,10F28",
    "zero-sweep ARC in FTP-911": "FFA2-FFA3",
}


def expand(ranges):
    for interval in ranges.split(","):
        start, _, end = interval.partition("-")
        for n in range(int(start, 16), int(end or start, 16) + 1):
            yield f"{n:X}"


def coords(extents):
    if not extents.has_data:
        raise ValueError("Face has no visible extent")
    return [
        extents.extmin.x, extents.extmin.y, extents.extmax.x, extents.extmax.y,
    ]


def written_text(e):
    return e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text


def reading_order(text_entities):
    """Read a legend top to bottom, including words authored in separate entities."""
    positioned = []
    for entity in text_entities:
        ext = bbox.extents([entity])
        if ext.has_data:
            positioned.append((ext.center.y, ext.extmin.x, ext.size.y, entity))
    lines = []
    for y, x, height, entity in sorted(positioned, key=lambda item: (-item[0], item[1])):
        if not lines or abs(lines[-1][0] - y) > .36 * height:
            lines.append((y, []))
        lines[-1][1].append((x, entity))
    return [entity for _, line in lines for x, entity in sorted(line, key=lambda item: item[0])]


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def extract(source, table=TABLE):
    doc = ezdxf.readfile(source)
    model = doc.modelspace()
    native = {e.dxf.handle: e for e in model}
    used = set()
    rows = []
    label_audit = []
    exclusions = []

    def take(handle):
        if handle in used:
            raise ValueError(f"Entity #{handle} used twice")
        used.add(handle)
        return native[handle]

    for reason, ranges in EXCLUSIONS.items():
        for handle in expand(ranges):
            e = take(handle)
            item = dict(handle=handle, type=e.dxftype(), reason=reason)
            if e.dxftype() == "ARC":
                if e.dxf.start_angle != e.dxf.end_angle:
                    raise ValueError(f"Expected a zero-sweep arc at #{handle}")
                item.update(center=list(e.dxf.center)[:2], radius=e.dxf.radius,
                            startAngle=e.dxf.start_angle, endAngle=e.dxf.end_angle)
            if e.dxftype() == "TEXT" and reason != "drawing path annotation":
                item["text"] = written_text(e)
            exclusions.append(item)

    with table.open() as stream:
        for entry in csv.DictReader(stream, delimiter="\t"):
            literal, label = entry["literal"], entry["label"]
            handles = list(expand(entry["geometry"]))
            selected = [take(h) for h in handles]
            anchor = label or handles[0]
            code = literal if label else "UNNUMBERED " + literal
            asset_id = f"mutcd-sheet-{re.sub('[^a-z0-9]+', '-', code.lower()).strip('-')}-{anchor.lower()}"
            # Native curves and borders determine the board envelope. Text metrics
            # depend on available CAD fonts. Keep text for rendering, out of sizing.
            lines = [e for e in selected if e.dxftype() not in ("MTEXT", "TEXT")]
            face_bounds = coords(bbox.extents(lines))
            all_text = [e for e in selected if e.dxftype() in ("TEXT", "MTEXT")]
            inserts = [e for e in selected if e.dxftype() == "INSERT"]
            for ins in inserts:
                # Both inserts in this specific library are direct named blocks.
                all_text.extend(e for e in doc.blocks[ins.dxf.name]
                                if e.dxftype() in ("TEXT", "MTEXT"))
            word_evidence = [dict(handle=e.dxf.handle, text=written_text(e))
                             for e in reading_order(all_text)]
            rec = dict(
                id=asset_id, drawing=DRAWING, code=code, block=model.block_record.dxf.name,
                entities=handles, physicalBounds=face_bounds, handle=anchor,
                recordHandle=model.block_record.dxf.handle,
                blockHandle=doc.blocks[model.block_record.dxf.name].block.dxf.handle, space="Model",
                sourceKind="source-window", use="placed", text=[v["text"] for v in word_evidence],
            )
            evidence = dict(id=asset_id, code=code, geometryCount=len(selected),
                            anchor=anchor, faceText=word_evidence)
            if label:
                e = take(label)
                if e.dxftype() != "TEXT" or written_text(e) != literal or e.dxf.layer != "TEXT":
                    raise ValueError(f"Source label #{label} no longer reads {literal!r}")
                x, y, _ = bbox.extents([e]).center
                x0, y0, x1, y1 = face_bounds
                gap = math.hypot(max(x0-x, x-x1, 0), max(y0-y, y-y1, 0))
                if gap > 1.8:
                    raise ValueError(f"Source label #{label} is {gap:.3f} units from {code}")
                rec["labelHandle"] = label
                evidence.update(printedLabel=literal, labelHandle=label, labelXY=[x, y])
            else:
                parent = entry["companion_to"]
                rec.update(companionTo=parent, sourceKind="unnumbered plaque",
                           note=f"Separate plaque beneath {parent}. The source gives the legend “{literal}” without a designation.")
                evidence.update(printedLegend=literal, companionTo=parent)
            for ins in inserts:
                rec.update(insertHandle=ins.dxf.handle, definition=ins.dxf.name)
                evidence.update(insertHandle=ins.dxf.handle, definition=ins.dxf.name)
            if asset_id.startswith("mutcd-sheet-ftp-911-"):
                rec.update(
                    boundsBasis="visible artwork only",
                    note="The source shows a hurricane symbol and EVACUATION ROUTE lettering. Two circular border arcs have zero sweep. The source supplies no complete panel perimeter.",
                )
            if literal == "M1-1":
                rec["note"] = ("This source specimen shows the INTERSTATE legend on a blank shield."
                               if label == "11F61" else
                               "The source labels this BUSINESS 75 shield M1-1.")
            if label in ("11182", "11183"):
                # The source's six lines trace a complete concave chevron, almost
                # as tall/wide as its panel. Frame-size heuristics can discard it.
                ordered = list(expand("12347-1234C" if label=="11182" else "128BB-128C0"))
                contour = [native[h] for h in ordered]
                if not all(a.dxf.end.isclose(b.dxf.start)
                           for a,b in zip(contour, contour[1:] + contour[:1])):
                    raise ValueError(f"Open source chevron at {label}")
                rec["solidContours"] = [{
                    "sourceHandles":ordered, "fill":"black",
                    "vertices":[list(line.dxf.start)[:2] for line in contour],
                }]
            rows.append(rec)
            label_audit.append(evidence)

    if used != set(native):
        raise ValueError(f"Unreviewed modelspace handles: {sorted(set(native) - used)}")
    label_counts = Counter(row["code"] for row in rows if row.get("labelHandle"))
    audit = dict(
        drawing=DRAWING, sourceFile="MUTCD-StandardSigns.dwg",
        dxfSha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        insunits=doc.units, modelspaceHandle=model.block_record.dxf.handle,
        unitsNote="Modelspace has no declared insertion units. Source extents are in drawing units.",
        modelspaceEntities=len(native), selectedGeometryEntities=sum(len(r["entities"]) for r in rows),
        externalLabels=sum(label_counts.values()), distinctPrintedDesignations=len(label_counts),
        duplicatePrintedDesignations={s: n for s, n in label_counts.items() if n > 1},
        unnumberedPanels=sum(not r.get("labelHandle") for r in rows),
        excludedEntities=len(exclusions), labelsAndPanels=label_audit, exclusions=exclusions,
    )
    return rows, audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path(__file__).resolve().parents[2] / "cad-working")
    args = parser.parse_args()
    records, report = extract(args.work / "all-sources" / f"{DRAWING}.dxf")
    write_json(args.work / "block-inputs" / "mutcd-library.json", records)
    write_json(args.work / "mutcd-library-audit.json", report)
    print(f"{len(records)} faces, {report['externalLabels']} printed labels, "
          f"{report['modelspaceEntities']} modelspace entities accounted for")
