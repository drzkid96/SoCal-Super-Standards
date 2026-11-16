// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import fs from 'node:fs';
const BUILD = Date.now().toString(36);

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
const topicDefs = JSON.parse(fs.readFileSync('./data/topics.json', 'utf8'));
const topicGroups = topicDefs.map((g) => ({ label: g.group, collapsed: false, items: g.topics.map((t) => ({ label: t.name, link: `/topics/${t.slug}/` })) }));
const ladotCfg = JSON.parse(fs.readFileSync('./pipeline/config/ladot.json', 'utf8'));
const guideCfg = JSON.parse(fs.readFileSync('./pipeline/config/guides.json', 'utf8'));
const guideDocs = guideCfg.map((c) => ({ label: c.short, link: `/${c.slug}/` }));
const refCards = JSON.parse(fs.readFileSync('./data/refcards.json', 'utf8')).map((g) => ({ label: g.short + ' (outline)', link: `/guides/${g.slug}/` }));
const agencyCfg = JSON.parse(fs.readFileSync('./pipeline/config/agencies.json', 'utf8'));
const agencyDocs = agencyCfg.map((c) => ({ label: c.title.replace(/^City of /, '').replace(/ Department.*$/, '').replace(/ Public Works.*$/, '') + ' standard plans', link: `/${c.slug}/` }));
const ladotDocs = ladotCfg.map((c) => {
  const d = JSON.parse(fs.readFileSync(`./data/docs/${c.slug.replace('/', '__')}.json`, 'utf8'));
  return { label: c.short, collapsed: true, items: [
    { label: 'Overview', link: `/${c.slug}/` },
    ...d.chapters.map((ch) => ({ label: ch.title, link: `/${c.slug}/${ch.slug}/` })),
  ] };
});

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
      head: [
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/site.js?v=' + BUILD, defer: true } },
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/agent.js?v=' + BUILD, defer: true } },
      ],
      pagination: true,
      tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 2 },
      sidebar: [
        { label: 'Start here', items: [
          { label: 'Home', link: '/' },
          { label: 'Ask the standards (AI)', link: '/ask/' },
          { label: 'How to use this site', link: '/guide/' },
        ] },
        { label: 'Find by number', items: [
          { label: 'Detail and Drawing Index', link: '/details/' },
          { label: 'Sign Library', link: '/signs/' },
          { label: 'LADOT standard drawings', link: '/ladot/' },
          { label: 'All agency standard drawings', link: '/details/?type=Standard+drawing&sg=' },
        ] },
        { label: 'Design by topic', items: [
          { label: 'All topics', link: '/topics/' },
          ...topicGroups,
        ] },
        { label: 'Plan production', collapsed: true, items: [
          { label: 'MPP 531 plan preparation', link: '/ladot/mpp-531/01-policies-and-procedures/' },
          { label: 'LADOT drafting (CAD) standards', link: '/ladot/cad-standards/' },
          { label: 'MPP 521 signal design guidelines', link: '/ladot/mpp-521/' },
          { label: 'Red Book signal provisions', link: '/ladot/red-book/' },
        ] },
        { label: 'Source documents', items: [
          { label: 'CA MUTCD 2026', collapsed: true, items: [{ label: 'About this manual', link: '/ca-mutcd/' }, ...caParts] },
          { label: 'Federal MUTCD 11th Ed. Rev. 1', collapsed: true, items: [{ label: 'About this manual', link: '/mutcd/' }, ...fedParts] },
          { label: 'LADOT', collapsed: true, items: [{ label: 'All LADOT documents', link: '/ladot/' }, ...ladotDocs] },
          { label: 'Other agencies', collapsed: true, items: agencyDocs },
          { label: 'Federal guides (FHWA, ADA)', collapsed: true, items: guideDocs },
          { label: 'National design guides', collapsed: true, items: [{ label: 'About these guides', link: '/guides/' }, ...refCards] },
          { label: 'Sources and versions', link: '/sources/' },
        ] },
      ],
    }),
  ],
});
