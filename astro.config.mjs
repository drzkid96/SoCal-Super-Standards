// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import fs from 'node:fs';

const chapters = JSON.parse(fs.readFileSync('./data/ca-mutcd/chapters.json', 'utf8'));
const fedChapters = JSON.parse(fs.readFileSync('./data/mutcd/chapters.json', 'utf8'));
const PARTS = {
  '1': 'Part 1 · General', '2': 'Part 2 · Signs', '3': 'Part 3 · Markings',
  '4': 'Part 4 · Highway Traffic Signals', '5': 'Part 5 · Automated Vehicles',
  '6': 'Part 6 · Temporary Traffic Control', '7': 'Part 7 · School Areas',
  '8': 'Part 8 · Railroad and LRT Grade Crossings', '9': 'Part 9 · Bicycle Facilities',
  'A': 'Appendices',
};
const groups = (list, dir) => Object.entries(PARTS).map(([k, label]) => ({
  label,
  collapsed: true,
  items: list
    .filter((c) => c.code[0] === k)
    .map((c) => ({ label: `${c.code} ${c.title}`, link: `/${dir}/${c.code.toLowerCase()}/` })),
})).filter((g) => g.items.length);
const caParts = groups(chapters, 'ca-mutcd');
const fedParts = groups(fedChapters, 'mutcd');

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
      components: {
        ThemeProvider: './src/components/ThemeProvider.astro',
        ThemeSelect: './src/components/ThemeSelect.astro',
      },
      head: [{ tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/site.js', defer: true } }],
      pagination: true,
      tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 2 },
      sidebar: [
        { label: 'Start here', items: [
          { label: 'Home', link: '/' },
          { label: 'How to use this site', link: '/guide/' },
          { label: 'Sources and versions', link: '/sources/' },
        ] },
        { label: 'Libraries', items: [
          { label: 'Sign Library', link: '/signs/' },
        ] },
        { label: 'CA MUTCD 2026', items: [{ label: 'About this manual', link: '/ca-mutcd/' }, ...caParts] },
        { label: 'Federal MUTCD 11th Ed. Rev. 1', collapsed: true, items: [{ label: 'About this manual', link: '/mutcd/' }, ...fedParts] },
      ],
    }),
  ],
});
