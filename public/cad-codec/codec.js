// SPDX-License-Identifier: GPL-3.0-or-later
// Browser module for local native DWG conversion. Original caller buffers are preserved.
let worker;
let sequence = 0;
const pending = new Map();

function run(bytes, encode) {
  if (!worker) {
    worker = new Worker(new URL('./codec-worker.js', import.meta.url), {type:'module'});
    worker.onmessage = ({data}) => {
      const job = pending.get(data.id);
      if (!job) return;
      pending.delete(data.id);
      if (data.error) job.reject(new Error(data.error));
      else job.resolve(data.bytes);
    };
    worker.onerror = event => {
      worker.terminate();
      worker = undefined;
      for (const job of pending.values()) job.reject(new Error(event.message || 'The drawing converter failed to start.'));
      pending.clear();
    };
  }
  const copy = typeof bytes === 'string' ? new TextEncoder().encode(bytes) : new Uint8Array(bytes).slice();
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, {resolve, reject});
    worker.postMessage({id, encode, bytes:copy}, [copy.buffer]);
  });
}

export function encodeDwg(dxf) {
  return run(dxf, true);
}

export function decodeDwg(dwg) {
  return run(dwg, false);
}
