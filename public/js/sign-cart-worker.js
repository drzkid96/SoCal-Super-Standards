'use strict';
importScripts('../vendor/atlas/fflate.js','sign-legend-dxf.js','sign-legend-pdf.js');

const directory = new URL('../downloads/sign-blocks/', self.location.href);
const hashHex = bytes => Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('');
const alphabetical = (a, b) => a.file < b.file ? -1 : a.file > b.file ? 1 : 0;

function orderedGroups(records, sheets) {
  const byId = new Map(records.map(record=>[record.id,record]));
  if (!sheets?.length || byId.size !== records.length) throw Error('The sign selection could not be read.');
  return sheets.filter(sheet=>sheet.ids?.length).map(sheet=>({label:sheet.label || 'SIGN LEGEND',records:sheet.ids.map(id=>{
    if (!byId.has(id)) throw Error('The sign legend contains a missing selection.');
    return byId.get(id);
  })}));
}

async function selectedChart(records, sheets, layout) {
  const groups = orderedGroups(records, sheets);
  const defs = await self.SSSLegendDXF.loadGeometry(records);
  return self.SSSLegendPDF.create(records, groups, defs, layout);
}

async function selectedArchive(records, sheets, layout) {
  const byId = new Map(records.map(record=>[record.id,record]));
  if (!sheets?.length || byId.size !== records.length) throw Error('The sign selection could not be read.');
  const used = new Set();
  const groups = sheets.filter(sheet=>sheet.ids?.length).map(sheet=>{
    const group = sheet.ids.map(id=>{
      if (!byId.has(id)) throw Error('The sign legend contains a missing selection.');
      used.add(id);
      return byId.get(id);
    });
    return {label:sheet.label || 'SIGN LEGEND',records:group};
  });
  if (used.size !== byId.size) throw Error('A selected sign is missing from its sheet.');
  const names = new Set();
  for (const record of records) {
    const parts = record.file?.split('/') || [];
    if (parts[0] !== 'individual' || parts.some(p => !p || p === '.' || p === '..' || /[\\\x00-\x1f]/.test(p)) ||
        !/\.dwg$/i.test(record.file) || !Number.isSafeInteger(record.bytes) || record.bytes < 6 ||
        !/^[\da-f]{64}$/i.test(record.sha256) || names.has(record.file.toLowerCase())) {
      throw new Error('A selected drawing has an invalid catalog entry. Refresh the page and try again.');
    }
    names.add(record.file.toLowerCase());
  }
  const speeds = new Map();
  for (const record of records) {
    if (/^R2-1\(\d{1,2}\)$/.test(record.code)) speeds.set(record.code, (speeds.get(record.code) || 0) + 1);
  }
  for (const record of records) {
    if (speeds.get(record.code) === 1) record.legendName = record.code;
  }
  records.sort(alphabetical);
  const files = new Array(records.length);
  let next = 0;
  let completed = 0;
  async function download() {
    while (next < records.length) {
      const index = next++;
      const record = records[index];
      const path = record.file.split('/').map(encodeURIComponent).join('/');
      const response = await fetch(new URL(path, directory));
      if (!response.ok) throw new Error('Could not download '+record.code+'. Try again.');
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (bytes.length !== record.bytes || String.fromCharCode(...bytes.subarray(0, 6)) !== 'AC1015' ||
          hashHex(await crypto.subtle.digest('SHA-256', bytes)) !== record.sha256.toLowerCase()) {
        throw new Error(record.code+' has changed. Refresh the sign chart and try again.');
      }
      files[index] = bytes;
      self.postMessage({completed:++completed, total:records.length});
    }
  }
  await Promise.all(Array.from({length:Math.min(records.length, 4)}, download));
  const entries = Object.fromEntries(records.map((record, i) => [record.legendName ? `individual/${record.legendName}.dwg` : record.file, files[i]]));
  const dxf = await self.SSSLegendDXF.create(records,groups,layout);
  const {encodeDwg} = await import('../cad-codec/codec.js');
  const native = await encodeDwg(dxf);
  if (String.fromCharCode(...native.subarray(0,6)) !== 'AC1015') throw Error('The sign legend could not be exported as a native drawing.');
  entries['LADOT-SIGN-LEGENDS.dwg'] = native;
  entries['LADOT-SIGN-LEGENDS.dxf'] = new TextEncoder().encode(dxf);
  return fflate.zipSync(entries, {level:3, mtime:new Date(1980, 0, 1)});
}

self.onmessage = async ({data}) => {
  try {
    const archive = data.kind === 'pdf' ? await selectedChart(data.records,data.sheets,data.layout) : await selectedArchive(data.records,data.sheets,data.layout);
    self.postMessage({buffer:archive.buffer}, [archive.buffer]);
  } catch (error) {
    self.postMessage({error:error.message || 'The selected drawings could not be downloaded.'});
  }
};
