# California and federal sign size reference

The downloadable `sign-standards.json` and the repository's `sign-standards.json.gz` contain the same UTF-8 JSON. Dimensions and outline coordinates are in inches. The crosswalk covers 1,511 adopted Caltrans rows in 32 tables and 1,099 federal rows in 15 tables. The CAD observation set includes plan notes and named and unnamed specimens whose designations have no published match.

## Look up a sign

Unzip the download and run the following from the directory containing `lookup.py`. It uses the Python standard library.

```python
from lookup import read_index, resolve

index = read_index()
sign = resolve("W11-2", index["records"])
print(sign["size"], sign["nominalBounds"], sign["sizeNote"])
for row_id in sign["sizeRows"]:
    row = index["tableRows"][row_id]
    print(row["publisher"], row["application"], row["columns"], row["url"])
```

| Field | Meaning |
| --- | --- |
| `size`, `condition`, `sizeProvenance` | Numeric nominal dimensions for the selected California row and roadway application. `published-exact` identifies an exact code match. `published-variable-face` identifies a speed or handed panel backed by the authority in `panelAuthorization`. |
| `sizeRows`, `tableRows` | All indexed source alternatives, including separate federal and California editions, freeway, expressway, oversize, minimum, school, bicycle and temporary-control rows. `url` opens the row's PDF page. `tableEndUrl` opens the final sheet of that table. |
| `reviewedPanelOptions`, `archivalSizeOptions` | Individually checked face-size choices retain their roadway, mounting or legend conditions. Historical California values retain the superseded source and never establish a current California default. |
| `sizeNote` | Reviewed qualifications for the selected numeric cell, with the source and its printed marker. Other cell annotations are retained in the original dimension string. |
| `sizeBasis`, `nominalBounds`, `panelGeometry` | Measurement convention, ideal upright width and height, and optional closed panel vertices. Coordinates use positive X to the right and positive Y up. A diamond measures along a side. A triangle retains the published three side lengths. |
| `referenceFace`, `familyReference` | Issued face, California manual illustration crop, or publisher's dimensioned layout for the code. `familyReference` provides a separate parent-face comparison for an authorized legend variant. `asset` identifies an existing site asset. `source` links the publisher's page. |
| `cadDimensionEvidence` | Sizes printed on a project drawing or encoded in an individual source block. Entries retain original handles and text. An FP SIZE attribute applies only to the named specimen. |
| `status`, `notes` | Includes cases requiring a project choice, withdrawn California signs, federal-only sizes, a MOD design or unresolved designation. A missing standard size is represented by JSON null. |

The single-lane California W11-2 row gives a 30-inch diamond, or 42.4264 inches across the ideal corners. The same table gives a 36-inch minimum for diamond warnings facing multilane conventional traffic. R1-2 has three 36-inch sides and a 36 × 31.1769-inch ideal downward triangle. W14-3 has two 48-inch sloping sides and a 36-inch vertical side, forming a 44.4972 × 36-inch right-pointing pennant. The dimensioned artwork supplies the stock corner radii. A null bound identifies a shape that still needs its outline checked.

California Table 7B-1(CA) gives dimensions for school assemblies. For SW24-2(CA) it gives 36 × 54, and for SW24-3(CA) it gives 36 × 36. The individual [SW24-2](https://dot.ca.gov/-/media/dot-media/programs/safety-programs/documents/signs/sw/f0019434-sw24-2-a11y.pdf) and [SW24-3](https://dot.ca.gov/-/media/dot-media/programs/safety-programs/documents/signs/sw/f0019435-sw24-3-a11y.pdf) dimensioned face drawings each list 30 × 42, 36 × 48 and 48 × 60. Those two records leave the automatic physical face size empty. Use `faceSizeOptions` for the panel and `assemblySizeRows` for the installed assembly.

Project-specific signs retain their own evidence. Two FP specimens named Cal-itra have separate SIZE attributes of 30 × 36 and 12 × 18 inches. Both handles stay in the index. A MOD designation receives a published size only after an exact verified source record for that design is added. Otherwise its individual drawing dimensions and traced proportions remain separate.

## Sources

- [California MUTCD 2026](https://dot.ca.gov/-/media/dot-media/programs/safety-programs/documents/ca-mutcd/2026/camutcd-2026-all.pdf). The extraction excludes California's blue struck-out federal text and the editorial example in Chapter 1A.
- [FHWA MUTCD 11th Edition with Revision 1](https://mutcd.fhwa.dot.gov/kno_11th_Editionr1.htm). The federal rows retain their original edition and roadway classes.
- [Caltrans Sign Specifications](https://dot.ca.gov/programs/safety-programs/sign-specs). Exact designation links include restriction codes, activated blank-outs and shared sheets and retain their full qualifier.
- [FHWA 2024 Standard Highway Signs](https://mutcd.fhwa.dot.gov/kno-shs_2024-release-status/index.htm). The crosswalk includes sign layouts from the applicable releases. PDF page fragments are one-based.
- [YIELD layout](https://mutcd.fhwa.dot.gov/kno-shs_2024-release-status/pdf/2024_SHS_Releases_1-4-Regulatory_Warning_TTC_School_Signs.pdf#page=23), [pedestrian warning layout](https://mutcd.fhwa.dot.gov/kno-shs_2024-release-status/pdf/2024_SHS_Releases_1-4-Regulatory_Warning_TTC_School_Signs.pdf#page=592), [NO PASSING ZONE layout](https://mutcd.fhwa.dot.gov/kno-shs_2024-release-status/pdf/2024_SHS_Releases_1-4-Regulatory_Warning_TTC_School_Signs.pdf#page=636).

## Rebuild in the standards site repository

`build.py` reads the compact snapshots in `sources/` and the site's existing sign catalog, drawing references, retired-sign list and face assets. Python dependencies are PyMuPDF, NumPy, SciPy and Pillow. A reproducible rebuild with the pinned observations needs no publisher request or original DWG.

```sh
python data/reference/cad-standards/build.py
python data/reference/cad-standards/verify.py
```

To refresh the size tables from the original downloaded documents, supply the full Caltrans PDF and a directory of the individual federal chapter and part PDFs listed in `sources/retrieval.json`. To refresh the California specification links, supply the saved official index HTML. The importers verify the pinned SHA-256 digests.

```sh
python data/reference/cad-standards/extract_tables.py --california CAMUTCD-2026.pdf --federal-dir fhwa-11-r1
python data/reference/cad-standards/extract_specifications.py caltrans-specifications.html
python data/reference/cad-standards/build.py --cad-dir /path/to/cad-working
python data/reference/cad-standards/verify.py
```
