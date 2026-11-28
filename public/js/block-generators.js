// SSS block editor generators: simple parametric marking blocks, written as AutoCAD 2000 DXF entity
// group codes (no handles), plus outlines for an SVG preview. Units are feet, travel runs +Y, and the
// base point (0,0) follows the SSS placement rules. Shared by the editor (page) and the library worker.
(() => {
  const n = v => (Math.round(v * 1e6) / 1e6).toString();
  const GREEN = 74;                       // index fallback of FHWA IA-14 green (RGB 60,144,2)
  const LADOT_DOTS = 10;                  // DOTS pattern scale used on LADOT plans (Westwood S&S), feet drawings
  const tag = (...pairs) => pairs.map(String).join('\n') + '\n';
  function rectPts(x, y, w, h, angle = 0) {
    const c = Math.cos(angle), s = Math.sin(angle);
    return [[0, 0], [w, 0], [w, h], [0, h]].map(([px, py]) => [x + px * c - py * s, y + px * s + py * c]);
  }
  function hatch(points, {color = 0, dots = 0} = {}) {
    const path = points.flatMap(([x, y]) => [10, n(x), 20, n(y)]);
    const head = [0, 'HATCH', 100, 'AcDbEntity', 8, '0', ...(color ? [62, color] : []), 100, 'AcDbHatch',
      10, 0, 20, 0, 30, 0, 210, 0, 220, 0, 230, 1];
    const pattern = dots
      ? [2, 'DOTS', 70, 0, 71, 0, 91, 1, 92, 3, 72, 0, 73, 1, 93, points.length, ...path, 97, 0, 75, 1, 76, 1,
         52, 0, 41, n(dots), 77, 0, 78, 1, 53, 0, 43, 0, 44, 0, 45, n(0.03125 * dots), 46, n(0.0625 * dots), 79, 2, 49, 0, 49, n(-0.0625 * dots), 98, 0]
      : [2, 'SOLID', 70, 1, 71, 0, 91, 1, 92, 3, 72, 0, 73, 1, 93, points.length, ...path, 97, 0, 75, 0, 76, 1, 98, 0];
    return tag(...head, ...pattern);
  }
  function pline(points, {layer = '0', closed = true, width = 0} = {}) {
    return tag(0, 'LWPOLYLINE', 100, 'AcDbEntity', 8, layer, 100, 'AcDbPolyline', 90, points.length, 70, closed ? 1 : 0,
      ...(width ? [43, n(width)] : []), ...points.flatMap(([x, y]) => [10, n(x), 20, n(y)]));
  }
  // A white marking: filled area plus its outline, both ByLayer on layer 0.
  const solid = pts => hatch(pts) + pline(pts);
  // A colored field: hatch in the field color, frame on NOPLOT.
  const field = (pts, dots) => hatch(pts, {color: GREEN, dots}) + pline(pts, {layer: 'NOPLOT'});

  const families = {
    crosswalk: {
      label: 'Crosswalk',
      fields: [
        ['style', 'Type', 'select', 'continental', ['continental', 'ladder', 'transverse']],
        ['length', 'Crossing length (curb to curb), ft', 'number', 40, [4, 200, 1]],
        ['depth', 'Crosswalk width, ft', 'number', 10, [6, 30, 0.5]],
        ['bar', 'Bar width, ft', 'number', 2, [0.5, 4, 0.25]],
        ['gap', 'Space between bars, ft', 'number', 3, [0.5, 8, 0.25]],
        ['line', 'Side line width, ft', 'number', 1, [0.5, 2, 0.25]],
        ['skew', 'Skew, degrees', 'number', 0, [-45, 45, 1]],
      ],
      note: 'Base at the curb corner on the near crosswalk line.',
      build(p) {
        const a = p.skew * Math.PI / 180, out = [], shapes = [];
        const sideLines = p.style !== 'continental';
        const inner = sideLines ? p.line : 0;
        if (p.style !== 'transverse') {
          for (let x = (p.gap) / 2; x + p.bar <= p.length - p.gap / 2 + 1e-9; x += p.bar + p.gap) {
            const pts = rectPts(x, inner, p.bar, p.depth - 2 * inner, 0).map(([px, py]) => [px + py * Math.tan(a), py]);
            out.push(solid(pts)); shapes.push(pts);
          }
        }
        if (sideLines) for (const y of [0, p.depth - p.line]) {
          const pts = rectPts(0, y, p.length, p.line).map(([px, py]) => [px + py * Math.tan(a), py]);
          out.push(solid(pts)); shapes.push(pts);
        }
        return {text: out.join(''), shapes, name: `PM-CROSSWALK-${p.style.toUpperCase()}-${p.length}X${p.depth}`};
      },
    },
    bikecrossing: {
      label: 'Green bike crossing',
      fields: [
        ['width', 'Bike lane width, ft', 'number', 6, [4, 10, 0.5]],
        ['dash', 'Dash length, ft', 'number', 2, [1, 10, 0.5]],
        ['gap', 'Gap, ft', 'number', 6, [1, 20, 0.5]],
        ['count', 'Number of dashes', 'number', 8, [1, 40, 1]],
        ['edge', 'Edge line width, ft', 'number', 0.5, [0, 1, 0.0833]],
        ['fill', 'Green fill', 'select', 'solid', ['solid', 'LADOT dots', 'none']],
      ],
      note: 'Base at the upstream corner on the bike lane line; dashes repeat along +Y.',
      build(p) {
        const out = [], shapes = [], dots = p.fill === 'LADOT dots' ? LADOT_DOTS : 0;
        for (let i = 0; i < p.count; i++) {
          const y = i * (p.dash + p.gap), pts = rectPts(0, y, p.width, p.dash);
          if (p.fill !== 'none') { out.push(field(pts, dots)); shapes.push({pts, green: true}); }
          if (p.edge > 0) for (const x of [0, p.width - p.edge]) {
            const e = rectPts(x, y, p.edge, p.dash); out.push(solid(e)); shapes.push(e);
          }
        }
        return {text: out.join(''), shapes, name: `PM-BIKE-XING-${n(p.width).replace('.', 'P')}FT-${p.count}`};
      },
    },
    limitline: {
      label: 'Limit line',
      fields: [
        ['length', 'Length, ft', 'number', 22, [4, 120, 1]],
        ['width', 'Line width, ft', 'number', 1, [0.5, 2, 0.5]],
      ],
      note: 'Base at the curb end, upstream edge; the line runs across the approach along +X.',
      build(p) {
        const pts = rectPts(0, 0, p.length, p.width);
        return {text: solid(pts), shapes: [pts], name: `PM-LIMIT-LINE-${p.length}X${n(p.width * 12)}IN`};
      },
    },
    greenpanel: {
      label: 'Green bike lane panel',
      fields: [
        ['width', 'Bike lane width, ft', 'number', 5, [4, 10, 0.5]],
        ['length', 'Panel length, ft', 'number', 24, [4, 200, 1]],
        ['fill', 'Green fill', 'select', 'solid', ['solid', 'LADOT dots']],
      ],
      note: 'Base at the upstream corner on the bike lane line.',
      build(p) {
        const pts = rectPts(0, 0, p.width, p.length);
        return {text: field(pts, p.fill === 'LADOT dots' ? LADOT_DOTS : 0), shapes: [{pts, green: true}],
          name: `PM-GREEN-PANEL-${n(p.width).replace('.', 'P')}X${p.length}FT`};
      },
    },
  };
  function defaults(kind) {
    return Object.fromEntries(families[kind].fields.map(([k, , , d]) => [k, d]));
  }
  function clean(kind, params) {
    const out = defaults(kind);
    for (const [k, , type, , range] of families[kind].fields) {
      const v = params?.[k];
      if (type === 'number') {
        const x = Number(v);
        if (Number.isFinite(x)) out[k] = Math.max(range[0], Math.min(range[1], x));
      } else if (range.includes(v)) out[k] = v;
    }
    return out;
  }
  function make(kind, params) {
    const p = clean(kind, params), built = families[kind].build(p);
    const xs = [], ys = [];
    for (const s of built.shapes) for (const [x, y] of (s.pts || s)) { xs.push(x); ys.push(y); }
    return {...built, params: p, kind, bounds: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)],
      label: families[kind].label, note: families[kind].note};
  }
  function svg(made) {
    const [x0, y0, x1, y1] = made.bounds, pad = 0.08 * Math.max(x1 - x0, y1 - y0, 1);
    const vb = [x0 - pad, -(y1 + pad), x1 - x0 + 2 * pad, y1 - y0 + 2 * pad].map(v => n(v)).join(' ');
    const poly = (pts, fill) => `<polygon points="${pts.map(([x, y]) => n(x) + ',' + n(-y)).join(' ')}" fill="${fill}"/>`;
    const body = made.shapes.map(s => s.pts ? poly(s.pts, '#3c9002') : poly(s, '#111')).join('');
    const r = 0.03 * Math.max(x1 - x0, y1 - y0, 1);
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}" role="img" aria-label="${made.label} preview">${body}` +
      `<circle cx="0" cy="0" r="${n(r)}" fill="none" stroke="#7d3c6b" stroke-width="${n(r / 3)}"/></svg>`;
  }
  // Swap solid green fields in any block for the LADOT dots hatch at plan scale.
  function dotsFor(text) {
    const lines = text.replace(/\n$/, '').split('\n'), out = [];
    const pattern = [52, 0, 41, LADOT_DOTS, 77, 0, 78, 1, 53, 0, 43, 0, 44, 0, 45, n(0.03125 * LADOT_DOTS),
      46, n(0.0625 * LADOT_DOTS), 79, 2, 49, 0, 49, n(-0.0625 * LADOT_DOTS)].map(String);
    let i = 0;
    while (i < lines.length) {          // one entity at a time, by group code pairs
      let j = i + 2;
      while (j < lines.length && !(lines[j].trim() === '0' && j % 2 === 0)) j += 2;
      const ent = lines.slice(i, j);
      const pairs = [];
      for (let k = 0; k < ent.length; k += 2) pairs.push([ent[k].trim(), ent[k + 1]]);
      const green = pairs[0][1] === 'HATCH' && pairs.some(([c, v]) => c === '62' && ['74', '76', '3'].includes(v.trim()))
        && pairs.some(([c, v]) => c === '2' && v.trim() === 'SOLID');
      if (green) {
        for (const pr of pairs) {
          if (pr[0] === '2') pr[1] = 'DOTS';
          else if (pr[0] === '70') pr[1] = '0';
        }
        const at = pairs.findIndex(([c], k) => c === '76' && pairs[k + 1]?.[0] === '98');
        const extra = [];
        for (let k = 0; k < pattern.length; k += 2) extra.push([pattern[k], pattern[k + 1]]);
        pairs.splice(at + 1, 0, ...extra);
      }
      for (const [c, v] of pairs) out.push(c, v);
      i = j;
    }
    return out.join('\n') + '\n';
  }
  self.SSSBlockGenerators = {families, defaults, clean, make, svg, dotsFor};
})();
