# CAD blocks: how they are built

Signs, pavement markings and signals. Every published DWG is AutoCAD 2000 (AC1015), opens as
block references (never loose geometry), and is read back by LibreDWG and LibreCAD libdxfrw
before it is published.

## Tools (local builds)

- LibreDWG `dxf2dwg` / `dwg2dxf` and LibreCAD `libdxfrw` `dwg2dxf`, pinned in the dxf-to-dwg skill.
- `ezdxf`, `shapely`, `pymupdf`.
- AutoCAD itself for dynamic blocks (`public/downloads/cad-tools/SSS-CAD-TOOLS.lsp`).

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
- `SSS-PMARK-LIBRARY.dwg` collects every block for the Blocks palette Libraries tab.

## Dynamic blocks

LibreDWG cannot write dynamic block data reliably, so AutoCAD writes it. Load
`SSS-CAD-TOOLS.lsp`, run `SSSDYNEXPORT` in the drawing that holds the dynamic blocks, and publish
the `-SSS-DYNAMIC.dwg` and `.csv` it writes byte for byte. Never re-encode them.

## Lessons

- Header references must resolve. ezdxf names dimension style ISO-25 without defining it;
  `r2000_document()` sets Standard. A dangling style became a null handle in every DWG.
- Fail the build on any `dxf2dwg` warning.
- Caltrans marking sheets are rotated 270 degrees: visual up is +x of the unrotated page.
  Outline stroke width differs by sheet (0.48 or 0.72 pt); grids are 0.12 pt with a `<n> GRID` note.
- Roman numerals on those sheets use a symbol font: `Î` = I, `Ï` = V.
- Printed areas run 4 to 9 percent above the traced outline area; size must match within 0.06 ft.
- Wind hatch rings by nesting depth (outer counterclockwise, holes clockwise) so counters and
  wheel rings stay open in every renderer.
- Plan-set blocks are often drawn at display scale and placed at a fraction of it (words at 1/3,
  bike symbols stretched). Bake the placed scale in.
- Caltrans and LA-area CAD symbol libraries are MicroStation DGN v8 and .cel. Converting them
  needs a DGN reader (ODA, cadkit, Aspose or AutoCAD DGNIMPORT).

## Still open

- A24A bike lane arrow and Type V, A24B Type II (L), A24C bike symbol without person, A24D LEFT,
  A24C numerals and ISA: their traced outlines do not match the printed sizes yet.
- Striping patterns, crosswalks (A20, A24F) and signal symbols (ES sheets, Caltrans cell library).
