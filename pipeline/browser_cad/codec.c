/* SPDX-License-Identifier: GPL-3.0-or-later
 * Browser DWG/DXF conversion using GNU LibreDWG commit cd50d4c0798d924d1756f6ba6f417b7d3c898b0f.
 * The embedding allocates a separate in-memory WASI filesystem per conversion.
 */
#include "config.h"
#include <stdio.h>
#include <string.h>
#include "dwg.h"
#include "common.h"
#include "bits.h"
#include "out_dxf.h"

int convert(int encode) {
  Dwg_Data drawing;
  memset(&drawing, 0, sizeof(drawing));
  if (encode) drawing.header.version = R_2000;
  int status = encode ? dxf_read_file("input", &drawing)
                      : dwg_read_file("input", &drawing);
  if (status >= DWG_ERR_CRITICAL) return status;

  if (encode) {
    drawing.header.version = R_2000;
    if (drawing.header.from_version == R_INVALID)
      drawing.header.from_version = drawing.header.version;
    status = dwg_write_file("output", &drawing);
  } else {
    Bit_Chain dxf = {0};
    dxf.version = drawing.header.version;
    dxf.from_version = drawing.header.from_version;
    dxf.fh = fopen("output", "wb");
    if (!dxf.fh) return DWG_ERR_IOERROR;
    status = dwg_write_dxf(&dxf, &drawing);
    if (fclose(dxf.fh)) return DWG_ERR_IOERROR;
  }
  /* The browser releases the entire single-use WASI instance after copying
   * its output. LibreDWG's nonfatal warnings still yield supported geometry. */
  return status >= DWG_ERR_CRITICAL ? status : 0;
}
