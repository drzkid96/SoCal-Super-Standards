"""Restore reviewed sign-face selections and masks used by the CAD block builder.

The archive contains source entity handles and isolated sign-face assets; the
seven original project DWGs are supplied independently by the operator.
"""
import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

DATA = Path(__file__).resolve().parents[1] / "data/reference/plan-examples/3346-face-selections.zip"
IMAGE_KEYS = ("sourceImage", "mask")
MANIFESTS = ("3346-title.json", "3346-title-legacy.json", "3346-legend.json", "3346-named.json")

def pack(directory, archive):
    included = {}
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as target:
        for name in MANIFESTS:
            rows = json.loads((directory / name).read_text())
            for face in rows:
                for key in IMAGE_KEYS:
                    if face.get(key):
                        image = Path(face[key])
                        destination = "assets/" + image.name
                        data = image.read_bytes()
                        if destination in included and included[destination] != data:
                            raise ValueError("Asset name collision: " + image.name)
                        included[destination] = data
                        face[key] = destination
            target.writestr(name, json.dumps(rows, ensure_ascii=False, separators=(",",":")))
        for file, contents in sorted(included.items()):
            target.writestr(file, contents)

def restore(archive, output):
    assets = output.parent / "3346-face-assets"
    output.mkdir(parents=True, exist_ok=True)
    assets.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive) as source:
        for name in MANIFESTS:
            rows = json.loads(source.read(name))
            for face in rows:
                for key in IMAGE_KEYS:
                    path = face.get(key)
                    if not path:
                        continue
                    if path != "assets/" + Path(path).name:
                        raise ValueError("Invalid image path: " + path)
                    dest = assets / Path(path).name
                    dest.write_bytes(source.read(path))
                    face[key] = str(dest.resolve())
            (output/name).write_text(json.dumps(rows, ensure_ascii=False, separators=(",",":"))+"\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("pack", "restore"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--archive", type=Path, default=DATA)
    args=parser.parse_args()
    if args.action=="pack":
        pack(args.directory,args.archive)
    else:
        restore(args.archive,args.directory)
