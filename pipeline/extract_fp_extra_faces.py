"""Extract the FP library's uncoded sign faces, companion panels and corrected native windows."""
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

import ezdxf
from ezdxf import bbox

from extract_mutcd_library_faces import coords, expand, reading_order, write_json, written_text

TABLE = Path(__file__).with_name("fp_extra_face_handles.tsv")
DRAWING = "fp-signs"

# ATTRDEF defaults sit alongside the face in these chart cells. A code can occur
# more than once with different sizes, so map the individual source handles.
SIZE_LABELS = {
    "FBB7":"109", "100CA":"D1", "100F7":"D2", "101FB":"EE", "10200":"ED",
    "1020D":"D8", "10229":"E6", "10245":"DF", "10278":"E0", "102A6":"D9",
    "102F0":"102", "10319":"FB", "10320":"F4", "1075D":"117", "10788":"110",
}


def source_sizes(doc, work):
    chart = json.loads((work / "block-inputs" / "fp-grid.json").read_text())
    by_label = {r["labelHandle"]: r for r in chart}
    sizes = []
    for attribute, label in SIZE_LABELS.items():
        e = doc.entitydb[attribute]
        if e.dxftype() != "ATTDEF" or e.dxf.tag != "SIZE":
            raise ValueError(f"Expected a SIZE attribute at {attribute}")
        r = by_label[label]
        x1, y1, x2, y2 = r["physicalBounds"]
        w, h = x2-x1, y2-y1
        raw = e.dxf.text
        a, b = map(float, raw.lower().split("x"))
        # Three raw tags list their dimensions short side first on horizontal
        # panels. Preserve the exact source text as well as the drawing orientation.
        width, height = min(((a,b), (b,a)), key=lambda wh: abs(math.log((wh[0]/wh[1]) / (w/h))))
        sizes.append(dict(id=r["id"], code=r["code"], labelHandle=label,
                          attributeHandle=attribute, attributeTag=e.dxf.tag,
                          literal=raw, width=width, height=height,
                          drawingWidth=w, drawingHeight=h,
                          rawOrder="height x width" if width!=a else "width x height",
                          basis="FP modelspace SIZE attribute default in the printed specimen cell"))
    return sizes


def extract(work):
    dxf = work / "all-sources" / f"{DRAWING}.dxf"
    doc = ezdxf.readfile(dxf)
    model = doc.modelspace()
    model_name = model.block_record.dxf.name
    entities = {e.dxf.handle: e for e in model}
    faces, repairs, audit, repeats = [], [], [], {}
    with TABLE.open() as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            role = row["treatment"]
            code = row["identity"]
            handles = list(expand(row["geometry"]))
            native = [entities[h] for h in handles]
            label_handle = row["external_label"]
            if label_handle and entities[label_handle].dxftype() not in ("TEXT", "MTEXT"):
                raise ValueError(f"Invalid external label handle {label_handle}")
            note = row["note"]
            text = reading_order([e for e in native if e.dxftype() in ("TEXT", "MTEXT")])
            anchor = handles[0]
            provenance = dict(treatment=role, description=code, sourceHandle=anchor,
                              entities=handles)
            if label_handle:
                provenance.update(labelHandle=label_handle, printedLabel=written_text(entities[label_handle]))
            if note:
                provenance["note"] = note
            audit.append(provenance)
            if role == "reviewed":
                continue
            if role == "duplicate":
                repeats.setdefault(code, []).append(anchor)
                continue
            board = [e for e in native if e.dxftype() not in ("TEXT", "MTEXT")]
            box = coords(bbox.extents(board))
            row_id = "fp-signs-" + (label_handle.lower() if role == "repair" else f"extra-{anchor.lower()}")
            rec = dict(id=row_id, drawing=DRAWING, code=code, block=model_name,
                       handle=label_handle or anchor, recordHandle=model.block_record_handle,
                       blockHandle=doc.blocks[model_name].block.dxf.handle, space="Model",
                       use="placed", sourceKind="source-window", entities=handles,
                       physicalBounds=box, bbox=coords(bbox.extents(native)),
                       text=[written_text(e) for e in text])
            if label_handle:
                rec["labelHandle"] = label_handle
            if note:
                rec["note"] = note
            if role == "repair":
                repairs.append(rec)
            elif role == "face":
                faces.append(rec)
            else:
                raise ValueError(f"Unknown treatment {role}")
    for row in faces:
        if row["code"] in repeats:
            row["duplicatePlacements"] = repeats.pop(row["code"])
    if repeats:
        raise ValueError(f"Missing primary for duplicate face {list(repeats)}")
    if len({row["id"] for row in faces}) != len(faces):
        raise ValueError("Repeated FP asset ID")
    report = dict(drawing=DRAWING, units=doc.units,
                  note="Supplemental modelspace review after the named definitions and printed chart. Underlying dimensions are in native, undeclared drawing units.",
                  totals=dict(Counter(p["treatment"] for p in audit)), objects=audit)
    return faces, repairs, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path(__file__).resolve().parents[2] / "cad-working")
    work = parser.parse_args().work
    faces, repairs, report = extract(work)
    write_json(work / "block-inputs" / "fp-uncoded.json", faces)
    write_json(work / "fp-parent-repairs.json", repairs)
    write_json(work / "fp-unlabelled-audit.json", report)
    drawing = ezdxf.readfile(work / "all-sources" / f"{DRAWING}.dxf")
    write_json(work / "fp-source-size-attributes.json", source_sizes(drawing, work))
    print(json.dumps(report["totals"]))
