# CAD blocks: how they are built

Signs, pavement markings and signals. Every published static DWG is AutoCAD 2000 (AC1015), opens
as block references (never loose geometry), and is read back by LibreDWG and LibreCAD libdxfrw
before it is published. Dynamic blocks are AutoCAD 2018 (AC1032), written by ODA File Converter.

## Tools (local builds)

- LibreDWG `dxf2dwg` / `dwg2dxf` and LibreCAD `libdxfrw` `dwg2dxf`, pinned in the dxf-to-dwg skill.
- `ezdxf`, `shapely`, `pymupdf`.
- ODA File Converter 27.10 (`dpkg -i` the .deb; headless with `xvfb-run -a`, needs `libopengl0`):
  DWG and DXF in any version, dynamic block objects kept.
- cadkit (`cargo install cadkit-cli`): reads MicroStation DGN v7 and v8 (`cadkit info`, `cadkit
  convert --dxf-version r2018`; a sheet's figures can sit in its second model, `--model 1` for SVG).

## Signs: `sign_cells.py`

```
python3 pipeline/sign_cells.py build --libredwg <dir> --libdxfrw <libdxfrw dwg2dxf>
```

- One block INSERT at 0,0, the lower-left corner of the 1.025 x 1.2 in LADOT legend cell, plus
  one MTEXT code (ROMANS, bottom center, 0.095 in, shrunk to fit 0.96 in).
- Faces are scaled to fit 0.92 x 0.86 in, centered at (0.5125, 0.745). Units: plotted inches.
- Output: `data/reference/sign-cells.zip`; publishing swaps these in by record id.

## Pavement markings

```
python3 pipeline/marking_blocks.py --pdf <Caltrans 2026 Standard Plans PDF> --libredwg <dir>
python3 pipeline/plan_marking_blocks.py --dxf <plan drawing as DXF> --libredwg <dir>
python3 pipeline/striping_blocks.py --libredwg <dir>
python3 pipeline/marking_library.py --libredwg <dir>
```

- True size in feet. One INSERT per drawing on layer `P-PMARK`; block geometry is a SOLID hatch
  plus its outline on layer 0, ByBlock; green fields keep ACI 3.
- Base point: the middle of an arrow's tail; the bottom center of words and symbols; top center of
  yield line triangles. Arrows point +Y; words read bottom to top for the approaching driver.
- Caltrans figures are matched by the width, height and area printed with them (`SHEETS` in
  `marking_blocks.py`, in each sheet's reading order). Unmatched figures stay out and are listed
  in `data/reference/marking-blocks-report.json`.
- Plan-drawing blocks are flattened at the scale they are placed at in the plan, then checked
  against a stated size (`SHAPES` in `plan_marking_blocks.py`).
- Striping: every Caltrans detail in `striping_db.py` becomes `CT-DET-<n>`, one full repeat along
  +X from the start of the reference line, stripes in marking colors (yellow 2, white 7, black
  contrast 250), 4 in markers; broken lines also go to `SSS-CALTRANS-STRIPING.lin` (feet).
- `SSS-PMARK-LIBRARY.dwg` collects every block for the Blocks palette Libraries tab (striping one
  detail per row). The same script renders `SSS-PMARK-LIBRARY.webp` from the DWG as read back, on
  pavement gray (#2e2e2e, dark enough that ACI 7 draws white).
- Colored fields under a white marking (`FIELDS`, the ISA's blue ACI 5 square) are their own hatch,
  written first so the white marking draws over them.
- `marking_blocks.py` replaces only its own `CT-A24*` catalog rows; striping `CT-DET-*` and plan
  `PM-*` rows stay. After changing `striping_db.py`, also run `python3 pipeline/build_linetypes.py`
  (line type pages and data).

## Dynamic blocks

```
python3 pipeline/dynamic_blocks.py --dwg <plan drawing DWG> --libredwg <dir>
```

- ODA writes the plan as DXF with every dynamic block object (evaluation graph, parameters, grips,
  actions, visibility states) as an ACAD_PROXY_OBJECT that keeps its bytes and the handles it owns.
  The drawing is cut to the chosen definitions (`KEEP`), cleaned, renamed `PM-...-DYN`, and ODA
  writes the DWG in the source version (2018), which restores the proxies as native objects.
- Never change the class table: proxies point at classes by position.
- Clean only what the actions do not depend on: entity layer and color, block names, units, base
  geometry stays where it is. Layers inside: 0 ByBlock, green fields ACI 3, non-plotting geometry
  on Defpoints, existing / remove / proposed states on E-PMARK / R-PMARK / P-PMARK (P-PMARK white).
- Strip plan residue or each file stays near 650 KB: Civil 3D and Map dictionaries (`Root`,
  `Autodesk_MAP`, `PE5.*`, `ESRI_PRJ`, `ADE_`, `ASE_`, GUID keys), page setups, material extension
  records (corrupt XML), named views, the ACDSDATA section, unused dimension and text styles,
  linetypes and application names. Keep anything the dynamic data points at.
- Checks: each kept block's proxies come back with identical class and bytes, LibreDWG decodes
  native evaluation graphs with no proxies, cadkit reads with no warnings, ODA audit is clean.
- Default visibility state is the author's (THRU-LEFT opens on existing); hidden states carry
  AutoCAD's invisible flag, so renderers show the default state.
- `SSS-CAD-TOOLS.lsp` (`SSSDYNEXPORT`) stays for dynamic blocks in other drawings when ODA is not
  at hand.

## Lessons

- Header references must resolve. ezdxf names dimension style ISO-25 without defining it;
  `r2000_document()` sets Standard. A dangling style became a null handle in every DWG.
- Fail the build on any `dxf2dwg` warning.
- Caltrans marking sheets are rotated 270 degrees: visual up is +x of the unrotated page.
  Outline stroke width differs by sheet (0.48 or 0.72 pt); grids are 0.12 pt with a `<n> GRID` note.
- Roman numerals on those sheets use a symbol font: `Î` = I, `Ï` = V.
- Printed areas run 4 to 9 percent above the traced outline area; size must match within 0.06 ft.
- Several grid notes can sit near a figure; pick the one whose scale makes the figure agree with
  the dimensions printed beside it (the bike lane arrow is on a 6 in grid next to 1 ft grids).
- Fill needs two readings: nesting (holes cut only their parent, so a bike frame crossing a wheel
  joins) and even-odd (Type VIII's overlapping heads). Keep the one closer to the printed area,
  and hatch the resulting region, not the raw loops.
- Numerals print in pairs with one area; match digits by size in reading order and check the pair.
- Wind hatch rings by nesting depth (outer counterclockwise, holes clockwise) so counters and
  wheel rings stay open in every renderer.
- Plan-set blocks are often drawn at display scale and placed at a fraction of it (words at 1/3,
  bike symbols stretched). Bake the placed scale in.
- PyMuPDF reports a single straight stroke with a zero-area Rect, and Rect union drops empty
  rects. Build figure boxes from stroke points (LEFT is drawn only with straight lines).
- Dimension and extension lines share the grid stroke weight. A grid needs at least four lines
  each way; dashed centerlines are never grid (Type V's centerline gave a false scale).
- No grid (Type V), or a grid note that disagrees with every printed dimension both ways (ISA:
  drawn on a 4 1/2 in grid, noted 6 in): scale by the figure's own dimensions (text within 30 pt).
  With a grid drawn, pick the dimension that makes the grid a whole half inch; otherwise the
  largest that fits both sides. Then check against further printed dimensions or the area.
- A printed dimension or area can be wrong. Publish on independent evidence and say so in
  `SHEETS`: Type II (L) is 6'-9" (its halves equal Type II (B) and the through head; printed
  7'-0"), the bike symbol without rider is 5.2 ft2 (printed 7, the rider symbol's value), the ISA
  white area is 7.1 ft2 (printed 9; checked on four dimensions instead).
- Caltrans and LA-area CAD symbol libraries are MicroStation DGN v8 and .cel; cadkit reads them.
  ODA File Converter does not read DGN.

## Still open

- Every A24A to A24E figure is published (57 entries). Striping details 36 to 36B are the
  channelizing line only; gore layouts follow the plan.
- Crosswalks: A24F's second DGN model holds the crosswalk figures as geometry; not yet built.
- Signal symbols (ES sheets, Caltrans cell library CTCELLIB.cel), now readable with cadkit.
