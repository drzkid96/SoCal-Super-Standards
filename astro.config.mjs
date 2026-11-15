// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import fs from 'node:fs';

const chapters = JSON.parse(fs.readFileSync('./data/ca-mutcd/chapters.json', 'utf8'));
const PARTS = {
  '1': 'Part 1 · General', '2': 'Part 2 · Signs', '3': 'Part 3 · Markings',
  '4': 'Part 4 · Highway Traffic Signals', '5': 'Part 5 · Automated Vehicles',
  '6': 'Part 6 · Temporary Traffic Control', '7': 'Part 7 · School Areas',
  '8': 'Part 8 · Railroad and LRT Grade Crossings', '9': 'Part 9 · Bicycle Facilities',
  'A': 'Appendices',
};
const caParts = Object.entries(PARTS).map(([k, label]) => ({
  label,
  collapsed: true,
  items: chapters
    .filter((c) => c.code[0] === k)
    .map((c) => ({ label: `${c.code} ${c.title}`, link: `/ca-mutcd/${c.code.toLowerCase()}/` })),
})).filter((g) => g.items.length);

export default defineConfig({
  site: 'https://drzkid96.github.io',
  base: '/SoCal-Super-Standards',
  trailingSlash: 'always',
  integrations: [
    starlight({
      title: 'SoCal Super Standards',
      description: 'Searchable traffic engineering standards for Southern California: CA MUTCD 2026, federal MUTCD, LADOT, FHWA, ADA, and more.',
      customCss: [
        '@fontsource/albert-sans/400.css',
        '@fontsource/albert-sans/500.css',
        '@fontsource/albert-sans/600.css',
        '@fontsource/albert-sans/700.css',
        '@fontsource/albert-sans/400-italic.css',
        '@fontsource/albert-sans/700-italic.css',
        './src/styles/site.css',
      ],
      social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/drzkid96/SoCal-Super-Standards' }],
      lastUpdated: false,
      pagination: true,
      tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 2 },
      sidebar: [
        { label: 'Start here', items: [
          { label: 'Home', link: '/' },
          { label: 'How to use this site', link: '/guide/' },
          { label: 'Sources and versions', link: '/sources/' },
        ] },
        { label: 'CA MUTCD 2026', items: [{ label: 'About this manual', link: '/ca-mutcd/' }, ...caParts] },
      ],
    }),
  ],
});
