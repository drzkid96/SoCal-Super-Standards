// SPDX-License-Identifier: GPL-3.0-or-later
import {convertDrawing} from './engine.js';
self.onmessage = async ({data}) => {
  try {
    const bytes = await convertDrawing(data.bytes, data.encode);
    self.postMessage({id:data.id, bytes}, [bytes.buffer]);
  } catch (error) {
    self.postMessage({id:data.id, error:String(error?.message || error)});
  }
};
