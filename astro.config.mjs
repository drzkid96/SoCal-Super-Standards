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
const AGENCY_LABELS = {
  'caltrans/standard-plans-2026': 'Caltrans 2026 Standard Plans (current)',
  'caltrans/standard-plans-2018': 'Caltrans 2018 Standard Plans (superseded)',
  'burbank/standard-plans': 'Burbank Standard Plans (BT series)',
  'pasadena/standard-plans': 'Pasadena Standard Plans (S-700 series)',
};
const AGENCY_ORDER = [
  'caltrans/standard-plans-2026',
  'burbank/standard-plans',
  'pasadena/standard-plans',
  'caltrans/standard-plans-2018',
];
const agencyDocs = agencyCfg
  .filter((c) => !c.slug.includes('la28'))
  .sort((a, b) => (AGENCY_ORDER.indexOf(a.slug) + 1 || 99) - (AGENCY_ORDER.indexOf(b.slug) + 1 || 99))
  .map((c) => ({ label: AGENCY_LABELS[c.slug] || c.short, link: `/${c.slug}/` }));
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
        Header: './src/components/Header.astro',
        PageTitle: './src/components/PageTitle.astro',
        ThemeProvider: './src/components/ThemeProvider.astro',
        ThemeSelect: './src/components/ThemeSelect.astro',
      },
      head: [
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/site.js?v=' + BUILD, defer: true } },
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/agent.js?v=' + BUILD, defer: true } },
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/panel.js?v=' + BUILD, defer: true } },
      ],
      pagination: true,
      tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 2 },
      sidebar: [
        { label: 'Start here', items: [
          { label: 'Home', link: '/' },
          { label: 'Ask the standards (AI)', link: '/ask/' },
          { label: 'Standards status (what governs)', link: '/bulletins/standards-status/' },
          { label: 'How to use this site', link: '/guide/' },
        ] },
        { label: 'Find by number & libraries', items: [
          { label: 'Detail and Drawing Index', link: '/details/' },
          { label: 'Keyword Index A to Z', link: '/keywords/' },
          { label: 'Sign Library', link: '/signs/' },
          { label: 'Pavement Marking Library', link: '/markings/' },
          { label: 'Line Type Database', link: '/markings/line-types/' },
          { label: 'LADOT standard drawings', link: '/ladot/' },
          { label: 'MPP drawings, redrawn', link: '/ladot/mpp-details/' },
          { label: 'All agency standard drawings', link: '/details/?type=Standard+drawing' },
        ] },
        { label: 'Design by topic', items: [
          { label: 'All topics', link: '/topics/' },
          { label: 'LADOT curb paint & red curb', link: '/ladot/curb-paint/' },
          { label: 'Lane widths (all sources)', link: '/bulletins/lane-widths/' },
          ...topicGroups,
        ] },
        { label: 'Bulletins & policy memos', collapsed: true, items: [
          { label: 'All bulletins and memos', link: '/bulletins/' },
          { label: 'Standards status (what supersedes what)', link: '/bulletins/standards-status/' },
          { label: 'Lane width comparison', link: '/bulletins/lane-widths/' },
          { label: 'Bikeway design comparison', link: '/bulletins/bikeway-design-comparison/' },
          { label: 'Caltrans HDM Ch. 1000 Bikeways', link: '/bulletins/caltrans-hdm-ch1000/' },
          { label: 'Caltrans DIB 94 Complete Streets', link: '/bulletins/caltrans-dib-94/' },
          { label: 'Caltrans DIB 89-02 Class IV', link: '/bulletins/caltrans-dib-89-02/' },
          { label: 'Caltrans DIB 82-06 Accessibility', link: '/bulletins/caltrans-dib-82-06/' },
          { label: 'Caltrans DIB 79-04 2R/3R', link: '/bulletins/caltrans-dib-79-04/' },
          { label: 'Caltrans DIB 81-03 CAPM', link: '/bulletins/caltrans-dib-81-03/' },
          { label: 'Caltrans DIB 93 Evacuation routes', link: '/bulletins/caltrans-dib-93/' },
          { label: 'Caltrans DIB 92 SPI', link: '/bulletins/caltrans-dib-92/' },
          { label: 'Caltrans DIB 90 DDI', link: '/bulletins/caltrans-dib-90/' },
          { label: 'LADOT Lane Reconfiguration', link: '/bulletins/ladot-lane-reconfiguration-2023/' },
          { label: 'LADOT Bikeway Marking', link: '/bulletins/ladot-bikeway-marking-2022/' },
          { label: 'LADOT Leading Pedestrian Interval', link: '/bulletins/ladot-lpi-2021/' },
          { label: 'LADOT Exclusive Pedestrian Phase', link: '/bulletins/ladot-exclusive-ped-phase-2017/' },
          { label: 'LADOT S&S Plan Review Checklist', link: '/bulletins/ladot-ss-plan-checklist-2022/' },
          { label: 'LADOT Accessible Parking Zones', link: '/bulletins/ladot-accessible-parking-2017/' },
          { label: 'PROWAG (ADA right-of-way)', link: '/bulletins/prowag-2023/' },
          { label: 'CBC 11B accessible parking', link: '/bulletins/ca-accessible-parking-2026/' },
        ] },
        { label: 'Plan production', collapsed: true, items: [
          { label: 'MPP 531 plan preparation', link: '/ladot/mpp-531/01-policies-and-procedures/' },
          { label: 'LADOT drafting (CAD) standards', link: '/ladot/cad-standards/' },
          { label: 'MPP 521 signal design guidelines', link: '/ladot/mpp-521/' },
          { label: 'Red Book signal provisions', link: '/ladot/red-book/' },
          { label: 'LADOT S&S Plan Review Checklist', link: '/bulletins/ladot-ss-plan-checklist-2022/' },
        ] },
        { label: 'Source documents', items: [
          { label: 'CA MUTCD 2026', collapsed: true, items: [{ label: 'About this manual', link: '/ca-mutcd/' }, ...caParts, { label: 'LA28 Supplement (Games Route Network)', link: '/caltrans/la28-supplement/' }] },
          { label: 'Federal MUTCD 11th Ed. Rev. 1', collapsed: true, items: [{ label: 'About this manual', link: '/mutcd/' }, ...fedParts] },
          { label: 'LADOT', collapsed: true, items: [{ label: 'All LADOT documents', link: '/ladot/' }, ...ladotDocs] },
          { label: 'Caltrans, Burbank & Pasadena', collapsed: true, items: agencyDocs },
          { label: 'Federal guides (FHWA, ADA)', collapsed: true, items: guideDocs },
          { label: 'National design guides', collapsed: true, items: [{ label: 'About these guides', link: '/guides/' }, ...refCards] },
          { label: 'Sources and versions', link: '/sources/' },
        ] },
      ],
    }),
  ],
});
