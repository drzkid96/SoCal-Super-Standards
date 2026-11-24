import { readFileSync } from 'node:fs';
import katex from 'katex';

// These are words and units in the City's TeX, not products of italic variables.
const typeset = source => source.replaceAll('\u00a0', ' ').replace(
  /Left-turn vehicles per hr\.|Cycles\/hr\.|cycles\/15min\.|\bor (?=cycles)|\bVol\.|\bft\.|tan angle AYW|total(?=\\right)/g,
  words => '\\text{' + words + '}'
);
const expressions = JSON.parse(readFileSync(0, 'utf8'));
const output = expressions.map(source => katex.renderToString(typeset(source), {
  output: 'mathml', throwOnError: true, trust: false, strict: 'error',
}));
process.stdout.write(JSON.stringify(output));
