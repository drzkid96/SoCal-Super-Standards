"""Exercise whole-file DWG insert, repeated placement and same-code variant naming."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf
from ezdxf import xref


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(native, decoded, decoder):
    subprocess.run([str(decoder), str(native), "-o", str(decoded), "-y"], check=True,
                   capture_output=True, timeout=240)
    return ezdxf.readfile(decoded)


def entity_counts(layout):
    return Counter(entity.dxftype() for entity in layout)


def unique_file_names(records):
    seen = set()
    for row in records:
        name = Path(row["file"]).stem
        if name != row["blockName"] or row["masterBlockName"] != name or name.casefold() in seen:
            raise ValueError(f"Ambiguous or mismatched insert name on {row['id']}: {name}")
        seen.add(name.casefold())


def variants(records):
    by_code = defaultdict(list)
    for row in records:
        by_code[row["code"]].append(row)
    # Prefer matching source codes with genuinely different graphics and retained dimensions.
    for code in ["R4-11", "D11-1", "R81(CA)", *sorted(by_code)]:
        choices = by_code[code]
        if choices:
            first = choices[0]
            for other in choices[1:]:
                if first["geometryFingerprint"] != other["geometryFingerprint"]:
                    return first, other
    return records[0], records[1]


def perform_check(manifest, decoder, encoder, output):
    catalog = json.loads(manifest.read_text())
    records = catalog["records"]
    unique_file_names(records)
    master_path = manifest.parent / catalog["master"]
    master_sha = sha(master_path)
    if master_sha != catalog["masterSha256"]:
        raise ValueError("Master checksum changed")
    with tempfile.TemporaryDirectory(prefix="sign-insert-") as tmp:
        tmp = Path(tmp)
        master = decode(master_path, tmp / "master.dxf", decoder)
        master_inserts = {e.dxf.name.casefold() for e in master.modelspace().query("INSERT")}
        missing = [row["id"] for row in records
                   if row["masterBlockName"] not in master.blocks or
                   row["masterBlockName"].casefold() not in master_inserts]
        if missing:
            raise ValueError(f"Master lacks a populated catalog placement for {missing[:6]}")
        master_counts = {}
        for row in records:
            counts = entity_counts(master.blocks[row["masterBlockName"]])
            if not counts or counts["INSERT"] or counts["HATCH"] != row["solidHatches"]:
                raise ValueError(f"Incorrect master artwork inventory for {row['id']}: {counts}")
            master_counts[row["id"]] = counts
        del master

        drawings = variants(records)
        target = ezdxf.new("R2000", units=1)
        model = target.modelspace()
        details = []
        for i, row in enumerate(drawings):
            source_path = manifest.parent / row["file"]
            if sha(source_path) != row["sha256"]:
                raise ValueError(f"Source bytes inconsistent: {row['id']}")
            source = decode(source_path, tmp / f"source-{i}.dxf", decoder)
            counts = entity_counts(source.modelspace())
            if counts != master_counts[row["id"]] or counts["INSERT"]:
                raise ValueError(f"Individual WBLOCK differs from master block: {row['id']}")
            name = source_path.stem
            block = target.blocks.new(name=name)
            loader = xref.Loader(source, target)
            loader.load_modelspace(target_layout=block)
            loader.execute()
            positions = [(0, 0), (120, 0)] if i == 0 else [(0, 120)]
            for point in positions:
                model.add_blockref(name, point)
            details.append({"code":row["code"], "blockName":name, "dwgSha256":row["sha256"],
                            "directEntities":dict(counts), "insertionPoints":positions})
        assembly_dxf = tmp / "three-sign-inserts.dxf"
        assembly_dwg = tmp / "three-sign-inserts.dwg"
        target.saveas(assembly_dxf)
        subprocess.run([str(encoder),"--as","r2000","-o",str(assembly_dwg),str(assembly_dxf)],
                       check=True, capture_output=True, timeout=90)
        reopened = decode(assembly_dwg, tmp / "result.dxf", decoder)
        expected = Counter((s["blockName"].casefold(),p[0],p[1]) for s in details for p in s["insertionPoints"])
        actual = Counter((e.dxf.name.casefold(),e.dxf.insert.x,e.dxf.insert.y)
                         for e in reopened.modelspace().query("INSERT"))
        if expected != actual:
            raise ValueError(f"Reopened combined drawing lost placements: {actual}")
        for sample in details:
            counts = entity_counts(reopened.blocks[sample["blockName"]])
            if sample["directEntities"] != dict(counts):
                raise ValueError(f"Round-trip import changed geometry of {sample['blockName']}")
    report = {"masterSha256":master_sha,"cataloguedBlocks":len(records),
              "uniqueCaseInsensitiveStandaloneNames":len(records),"masterBlocksAndPlacementsChecked":len(records),
              "reopenedInsertCount":sum(actual.values()),"standaloneUnits":catalog["units"],
              "sameCodeVariantTest":drawings[0]["code"] == drawings[1]["code"],"sample":details,
              "method":"Independently decoded native master and individual sign files. Imported centered modelspace artwork under each standalone filename into an empty drawing, inserted one sign twice and a second design once, encoded a new R2000 DWG, reopened it through libdxfrw and compared block names, entities, solid hatches and insertion points."}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(f"{len(records)} master blocks checked, {sum(actual.values())} placements reopened")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest","decoder","encoder","output"):
        parser.add_argument(name,type=Path)
    args=parser.parse_args()
    perform_check(args.manifest,args.decoder.resolve(),args.encoder.resolve(),args.output)
