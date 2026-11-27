// Vector PDF sign charts from the same native face geometry as the DWG legend.
// Faces are drawn from HATCH, LINE, LWPOLYLINE and SPLINE primitives; hatches fill even-odd so letter holes stay open.
(() => {
  const PAGES = {
    'tabloid-landscape':[17,11], 'tabloid-portrait':[11,17], 'letter-portrait':[8.5,11], 'letter-landscape':[11,8.5],
    'ansi-d':[34,22], 'arch-d':[36,24]
  };
  const SYMBOLS = {'↑':'^','↓':'v','←':'<','→':'>','×':'x','–':'-','—':'-','“':'"','”':'"','‘':"'",'’':"'"};
  const pdfText = s => Array.from(String(s)).map(c => SYMBOLS[c] ?? (c.charCodeAt(0) < 256 ? c : '?')).join('')
    .replace(/[\\()]/g, c => '\\' + c);
  const num = v => (Math.round(v * 1000) / 1000).toString();

  function pairsOf(text) {
    const lines = text.trimEnd().split(/\r?\n/), out = [];
    for (let i = 0; i + 1 < lines.length; i += 2) out.push([Number(lines[i]), lines[i + 1].trim()]);
    return out;
  }
  function entitiesOf(text) {
    const list = [];
    for (const [code, value] of pairsOf(text)) {
      if (code === 0) list.push({type: value, tags: []});
      else if (list.length) list[list.length - 1].tags.push([code, value]);
    }
    return list;
  }
  const arcPoints = (cx, cy, r, a0, a1, ccw, rx = r, ry = r, rot = 0) => {
    let s = a0 * Math.PI / 180, e = a1 * Math.PI / 180;
    if (!ccw) { s = -s; e = -e; }
    if (ccw && e <= s) e += 2 * Math.PI;
    if (!ccw && e >= s) e -= 2 * Math.PI;
    const n = Math.max(8, Math.ceil(Math.abs(e - s) / (Math.PI / 24))), pts = [];
    for (let i = 0; i <= n; i++) {
      const t = s + (e - s) * i / n, x = rx * Math.cos(t), y = ry * Math.sin(t);
      pts.push([cx + x * Math.cos(rot) - y * Math.sin(rot), cy + x * Math.sin(rot) + y * Math.cos(rot)]);
    }
    return pts;
  };
  const bulgePoints = (p, q, b) => {
    if (!b) return [q];
    const theta = 4 * Math.atan(b), dx = q[0] - p[0], dy = q[1] - p[1], chord = Math.hypot(dx, dy);
    if (!chord) return [q];
    const r = chord / (2 * Math.sin(theta / 2)), mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2;
    const h = r * Math.cos(theta / 2), cx = mx - h * dy / chord, cy = my + h * dx / chord;
    const a0 = Math.atan2(p[1] - cy, p[0] - cx), n = Math.max(4, Math.ceil(Math.abs(theta) / (Math.PI / 24))), pts = [];
    for (let i = 1; i <= n; i++) {
      const t = a0 + theta * i / n;
      pts.push([cx + Math.abs(r) * Math.cos(t), cy + Math.abs(r) * Math.sin(t)]);
    }
    pts[pts.length - 1] = q;
    return pts;
  };
  // NURBS evaluation by de Boor for control-point splines; fit-point splines fall back to their fit polyline.
  function nurbs(degree, knots, ctrl, weights) {
    const n = ctrl.length, p = Math.min(degree, n - 1);
    if (n < 2 || knots.length < n + p + 1) return ctrl;
    const w = weights?.length === n ? weights : ctrl.map(() => 1);
    const t0 = knots[p], t1 = knots[n], steps = Math.max(12, n * 8), pts = [];
    for (let i = 0; i <= steps; i++) {
      const t = Math.min(t0 + (t1 - t0) * i / steps, t1 - 1e-12 * (t1 - t0 || 1));
      let k = p; while (k < n - 1 && t >= knots[k + 1]) k++;
      const d = [];
      for (let j = 0; j <= p; j++) { const c = ctrl[j + k - p], wt = w[j + k - p]; d.push([c[0] * wt, c[1] * wt, wt]); }
      for (let r = 1; r <= p; r++) for (let j = p; j >= r; j--) {
        const den = knots[j + 1 + k - r] - knots[j + k - p], a = den ? (t - knots[j + k - p]) / den : 0;
        d[j] = d[j].map((v, m) => (1 - a) * d[j - 1][m] + a * v);
      }
      pts.push([d[p][0] / d[p][2], d[p][1] / d[p][2]]);
    }
    return pts;
  }
  // Returns {fills:[[loop...]], strokes:[polyline...]} in native units.
  function shapes(text) {
    const fills = [], strokes = [];
    for (const {type, tags} of entitiesOf(text)) {
      let i = 0;
      const at = c => { while (i < tags.length && tags[i][0] !== c) i++; return i < tags.length ? Number(tags[i++][1]) : NaN; };
      const peek = () => tags[i]?.[0];
      const take = () => Number(tags[i++][1]);
      if (type === 'LINE') {
        const g = Object.fromEntries(tags.map(([c, v]) => [c, Number(v)]));
        strokes.push([[g[10], g[20]], [g[11], g[21]]]);
      } else if (type === 'LWPOLYLINE') {
        const closed = (Number(tags.find(t => t[0] === 70)?.[1]) & 1) === 1, verts = [];
        for (const [c, v] of tags) {
          if (c === 10) verts.push([Number(v), 0, 0]);
          else if (c === 20 && verts.length) verts[verts.length - 1][1] = Number(v);
          else if (c === 42 && verts.length) verts[verts.length - 1][2] = Number(v);
        }
        if (verts.length < 2) continue;
        const pts = [[verts[0][0], verts[0][1]]];
        for (let j = 1; j < verts.length + (closed ? 1 : 0); j++) pts.push(...bulgePoints(verts[j - 1], verts[j % verts.length], verts[j - 1][2]));
        strokes.push(pts);
      } else if (type === 'SPLINE') {
        const degree = Number(tags.find(t => t[0] === 71)?.[1] || 3), knots = [], weights = [], ctrl = [], fit = [];
        for (const [c, v] of tags) {
          if (c === 40) knots.push(Number(v)); else if (c === 41) weights.push(Number(v));
          else if (c === 10) ctrl.push([Number(v), 0]); else if (c === 20 && ctrl.length) ctrl[ctrl.length - 1][1] = Number(v);
          else if (c === 11) fit.push([Number(v), 0]); else if (c === 21 && fit.length) fit[fit.length - 1][1] = Number(v);
        }
        strokes.push(ctrl.length ? nurbs(degree, knots, ctrl, weights) : fit);
      } else if (type === 'HATCH') {
        const loops = [], count = at(91);
        for (let path = 0; path < count && i < tags.length; path++) {
          const flags = at(92), loop = [];
          if (flags & 2) {
            const bulged = at(72), n = (at(73), at(93)), verts = [];
            for (let v = 0; v < n; v++) { const x = at(10), y = at(20); let b = 0; if (bulged && peek() === 42) b = take(); verts.push([x, y, b]); }
            if (verts.length) loop.push([verts[0][0], verts[0][1]]);
            for (let j = 1; j <= verts.length; j++) loop.push(...bulgePoints(verts[j - 1], verts[j % verts.length], verts[j - 1][2]));
          } else {
            const edges = at(93);
            for (let e = 0; e < edges; e++) {
              const kind = at(72);
              if (kind === 1) { const a = [at(10), at(20)], b = [at(11), at(21)]; if (!loop.length) loop.push(a); loop.push(b); }
              else if (kind === 2) { const cx = at(10), cy = at(20), r = at(40), s = at(50), f = at(51), ccw = at(73); loop.push(...arcPoints(cx, cy, r, s, f, ccw)); }
              else if (kind === 3) {
                const cx = at(10), cy = at(20), mx = at(11), my = at(21), ratio = at(40), s = at(50), f = at(51), ccw = at(73);
                const a = Math.hypot(mx, my); loop.push(...arcPoints(cx, cy, a, s, f, ccw, a, a * ratio, Math.atan2(my, mx)));
              } else if (kind === 4) {
                const degree = at(94), rational = at(73); at(74); const nk = at(95), nc = at(96), knots = [], ctrl = [], weights = [];
                for (let k = 0; k < nk; k++) knots.push(at(40));
                for (let k = 0; k < nc; k++) { ctrl.push([at(10), at(20)]); if (rational && peek() === 42) weights.push(take()); }
                if (peek() === 97) { const nf = take(); for (let k = 0; k < nf; k++) { at(11); at(21); } if (peek() === 12) { at(12); at(22); at(13); at(23); } }
                loop.push(...nurbs(degree, knots, ctrl, weights));
              }
            }
          }
          if (peek() === 97) { const sources = take(); for (let k = 0; k < sources; k++) if (peek() === 330) i++; }
          if (loop.length > 2) loops.push(loop);
        }
        if (loops.length) fills.push(loops);
      }
    }
    return {fills, strokes};
  }

  function pdfBytes(pages, size) {
    const [w, h] = size.map(v => v * 72), objects = [], enc = new TextEncoder();
    const add = body => { objects.push(body); return objects.length; };
    const catalog = add(null), tree = add(null), font = add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>');
    const bold = add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>');
    const kids = [];
    for (const content of pages) {
      const data = fflate.zlibSync(Uint8Array.from(content, c => c.charCodeAt(0) & 255), {level: 6});  // WinAnsi bytes
      const stream = add({head: `<< /Length ${data.length} /Filter /FlateDecode >>`, data});
      kids.push(add(`<< /Type /Page /Parent ${tree} 0 R /MediaBox [0 0 ${num(w)} ${num(h)}] /Resources << /Font << /F1 ${font} 0 R /F2 ${bold} 0 R >> >> /Contents ${stream} 0 R >>`));
    }
    objects[catalog - 1] = `<< /Type /Catalog /Pages ${tree} 0 R >>`;
    objects[tree - 1] = `<< /Type /Pages /Kids [${kids.map(k => k + ' 0 R').join(' ')}] /Count ${kids.length} >>`;
    const parts = [enc.encode('%PDF-1.4\n%âãÏÓ\n')], offsets = [];
    let length = parts[0].length;
    objects.forEach((body, index) => {
      offsets.push(length);
      const chunk = typeof body === 'string' ? [enc.encode(`${index + 1} 0 obj\n${body}\nendobj\n`)]
        : [enc.encode(`${index + 1} 0 obj\n${body.head}\nstream\n`), body.data, enc.encode('\nendstream\nendobj\n')];
      for (const c of chunk) { parts.push(c); length += c.length; }
    });
    const xref = ['xref', `0 ${objects.length + 1}`, '0000000000 65535 f ', ...offsets.map(o => String(o).padStart(10, '0') + ' 00000 n ')].join('\n');
    parts.push(enc.encode(`${xref}\ntrailer\n<< /Size ${objects.length + 1} /Root ${catalog} 0 R >>\nstartxref\n${length}\n%%EOF\n`));
    const out = new Uint8Array(parts.reduce((s, p) => s + p.length, 0)); let o = 0;
    for (const p of parts) { out.set(p, o); o += p.length; }
    return out;
  }

  // Tables flow left to right and onto new sheets; each sheet carries the title and a sheet count.
  function create(records, groups, defs, options = {}) {
    const L = self.SSSLegendDXF, layout = L.layoutOf(options), C = L.CELL;
    const size = PAGES[options.page] || PAGES['tabloid-landscape'];
    let scale = Math.max(0.5, Math.min(3, Number(options.cellScale) || 1));
    const margin = 0.5, header = 0.75, footer = 0.35, gap = 0.4, tableTitle = 0.3;
    const usableW = size[0] - 2 * margin, usableH = size[1] - 2 * margin - header - footer;
    const fitScale = Math.min(usableW / (C.width * layout.columns), (usableH - tableTitle) / (C.height * layout.rows));
    if (scale > fitScale) scale = fitScale;
    const cw = C.width * scale, ch = C.height * scale, tw = cw * layout.columns, th = ch * layout.rows + tableTitle;
    const perRow = Math.max(1, Math.floor((usableW + gap) / (tw + gap))), perCol = Math.max(1, Math.floor((usableH + gap) / (th + gap)));
    const list = L.tables(groups, layout), perPage = perRow * perCol, sheets = Math.max(1, Math.ceil(list.length / perPage));
    const shapeCache = new Map(), pt = v => num(v * 72);
    const title = (layout.title || (groups.length === 1 ? groups[0].label : '') || 'SIGN LEGEND').toUpperCase();
    const count = groups.reduce((s, g) => s + g.records.length, 0), stamp = new Date().toISOString().slice(0, 10);
    const pages = [];
    for (let sheet = 0; sheet < sheets; sheet++) {
      const ops = ['0 g 0 G 1 J 1 j'];
      const text = (str, x, y, sizePt, boldFont, align = 'left') => {
        const est = String(str).length * sizePt * (boldFont ? 0.58 : 0.53) / 72;
        const left = align === 'center' ? x - est / 2 : align === 'right' ? x - est : x;
        ops.push(`BT /${boldFont ? 'F2' : 'F1'} ${num(sizePt)} Tf ${pt(left)} ${pt(y)} Td (${pdfText(str)}) Tj ET`);
      };
      text(title, margin, size[1] - margin - 0.3, 20, true);
      text(`${count} sign placement${count === 1 ? '' : 's'} · ${list.length} table${list.length === 1 ? '' : 's'} · ${layout.columns} x ${layout.rows} cells per table`, margin, size[1] - margin - 0.55, 9, false);
      text(`SHEET ${sheet + 1} OF ${sheets}`, size[0] - margin, size[1] - margin - 0.3, 11, true, 'right');
      ops.push(`0.6 w ${pt(margin)} ${pt(size[1] - margin - header + 0.08)} m ${pt(size[0] - margin)} ${pt(size[1] - margin - header + 0.08)} l S`);
      text(`SoCal Super Standards · sign faces from the published DWG blocks · ${stamp}`, margin, margin - 0.05, 7, false);
      list.slice(sheet * perPage, sheet * perPage + perPage).forEach((table, n) => {
        const left = margin + (n % perRow) * (tw + gap), top = size[1] - margin - header - Math.floor(n / perRow) * (th + gap);
        text(table.title, left + tw / 2, top - tableTitle + 0.1, Math.min(10, (tw * 72) / (table.title.length * 0.6)), true, 'center');
        const gridTop = top - tableTitle, gridBottom = gridTop - ch * layout.rows;
        ops.push('0.5 G 0.5 w');
        for (let x = 0; x <= layout.columns; x++) ops.push(`${pt(left + x * cw)} ${pt(gridBottom)} m ${pt(left + x * cw)} ${pt(gridTop)} l S`);
        for (let y = 0; y <= layout.rows; y++) ops.push(`${pt(left)} ${pt(gridBottom + y * ch)} m ${pt(left + tw)} ${pt(gridBottom + y * ch)} l S`);
        ops.push('0 G');
        table.records.forEach((rec, slot) => {
          const cx = left + cw * (slot % layout.columns), cy = gridTop - ch * (Math.floor(slot / layout.columns) + 1);
          const def = defs.get(rec.id); if (!def) return;
          if (!shapeCache.has(rec.id)) shapeCache.set(rec.id, shapes(def.text));
          const {fills, strokes} = shapeCache.get(rec.id), f = L.fit(def.entry.bounds);
          const X = x => pt(cx + (f.s * x + f.x) * scale), Y = y => pt(cy + (f.s * y + f.y) * scale);
          for (const loops of fills) {
            ops.push(loops.map(loop => loop.map(([x, y], j) => `${X(x)} ${Y(y)} ${j ? 'l' : 'm'}`).join(' ') + ' h').join(' ') + ' f*');
          }
          if (strokes.length) {
            ops.push(`${num(Math.max(0.3, 0.45 * scale))} w`);
            for (const line of strokes) if (line.length > 1) ops.push(line.map(([x, y], j) => `${X(x)} ${Y(y)} ${j ? 'l' : 'm'}`).join(' ') + ' S');
          }
          text(rec.code, cx + C.artX * scale, cy + C.codeY * scale, L.codeHeight(rec.code) * scale * 72 * 1.35, false, 'center');
        });
      });
      pages.push(ops.join('\n'));
    }
    return pdfBytes(pages, size);
  }
  self.SSSLegendPDF = {create, shapes, PAGES};
})();
