// The chart and sign pages only load the ZIP library after a download request.
(() => {
  const workerURL = new URL('sign-cart-worker.js', document.currentScript.src);
  // kind 'dwg' returns the legend ZIP; kind 'pdf' returns the vector sign chart.
  window.SSSBuildSignZip = (records, onProgress, groups, layout = {}, kind = 'dwg') => new Promise((resolve, reject) => {
    if (!Array.isArray(records) || !records.length) {
      reject(new Error('Select at least one sign.'));
      return;
    }
    const worker = new Worker(workerURL);
    const fail = message => { worker.terminate(); reject(new Error(message)); };
    worker.onerror = () => fail('The download could not be prepared. Please try again.');
    worker.onmessage = ({data}) => {
      if (data.error) { fail(data.error); return; }
      if (data.buffer) {
        worker.terminate();
        resolve(new Blob([data.buffer], {type:kind === 'pdf' ? 'application/pdf' : 'application/zip'}));
      } else {
        onProgress?.(data.completed, data.total);
      }
    };
    const selected = records.map(({id, code, blockName, file, bytes, sha256}) => ({id, code, blockName, file, bytes, sha256}));
    const sheets = (groups || [{label:'SIGN LEGEND', records}]).map(group => ({
      label:group.label, ids:group.records.map(record => typeof record === 'string' ? record : record.id),
    }));
    worker.postMessage({records:selected, sheets, layout, kind});
  });
})();
