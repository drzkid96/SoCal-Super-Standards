import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

const catalog = JSON.parse(readFileSync('public/data/agency-modes.json', 'utf8'));
export const agencyCatalogScript = `window.__agencyCatalog=${JSON.stringify(catalog)};\n`;
export const agencyCatalogVersion = createHash('sha256').update(agencyCatalogScript).digest('hex').slice(0, 12);
