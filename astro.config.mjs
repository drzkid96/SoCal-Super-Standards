// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
execFileSync('python3', ['pipeline/prepare_reference.py'], { stdio: 'inherit' });
import { createHash } from 'node:crypto';
const scriptVersion = name => createHash('sha256').update(fs.readFileSync('public/js/'+name+'.js')).digest('hex').slice(0,12);

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
const flatTopics = topicDefs.flatMap((g) => g.topics.map((t) => ({ label: t.name, link: `/topics/${t.slug}/` })));
const ladotCfg = JSON.parse(fs.readFileSync('./pipeline/config/ladot.json', 'utf8'));
const guideCfg = JSON.parse(fs.readFileSync('./pipeline/config/guides.json', 'utf8'));
const guideDocs = guideCfg.map((c) => ({ label: c.short, link: `/${c.slug}/` }));
const refCards = JSON.parse(fs.readFileSync('./data/refcards.json', 'utf8')).map((g) => ({ label: g.short, link: `/guides/${g.slug}/` }));
const agencyCfg = JSON.parse(fs.readFileSync('./pipeline/config/agencies.json', 'utf8'));
const AGENCY_LABELS = {
  'caltrans/standard-plans-2026': 'Caltrans 2026 Standard Plans (current)',
  'burbank/standard-plans': 'Burbank Standard Plans (BT series)',
  'pasadena/standard-plans': 'Pasadena Standard Plans (S-700 series)',
};
const cityAgencyDocs = [
  { label: 'All LA County Cities (Hub)', link: '/cities/' },
  { label: 'Long Beach (22 sheets)', link: '/long-beach/standard-plans/' },
  { label: 'Palmdale (16 sheets)', link: '/palmdale/standard-plans/' },
  { label: 'Torrance (19 sheets)', link: '/torrance/standard-plans/' },
  { label: 'Pasadena (S-700 series)', link: '/pasadena/standard-plans/' },
  { label: 'Burbank (BT series)', link: '/burbank/standard-plans/' },
  { label: 'Santa Monica (SM / B / SWSM)', link: '/santa-monica/standard-plans/' },
  { label: 'Gardena (14 sheets)', link: '/gardena/standard-plans/' },
  { label: 'Glendora (12 sheets, 2024)', link: '/glendora/standard-plans/' },
  { label: 'Culver City (45 sheets, 2025)', link: '/culver-city/standard-plans/' },
  { label: 'West Hollywood (7 sheets)', link: '/west-hollywood/standard-plans/' },
];
const ladotDocs = ladotCfg.map(doc => ({ label: doc.short, link: `/${doc.slug}/` }));

export default defineConfig({
  site: 'https://drzkid96.github.io',
  base: '/SoCal-Super-Standards',
  trailingSlash: 'always',
  redirects: Object.fromEntries(Object.entries(JSON.parse(fs.readFileSync('.standards/redirects.json','utf8'))).map(([from, to]) => [from, '/SoCal-Super-Standards'+to])),
  integrations: [
    { name: 'article-citations', hooks: { 'astro:build:done': ({ dir }) => {
      execFileSync('python3', ['pipeline/link_citations.py', decodeURIComponent(dir.pathname)], { stdio: 'inherit' });
    } } },
    starlight({
      title: 'SoCal Super Standards',
      description: 'Southern California transportation standards. Browse by municipality, issuing agency, guide, design topic or drawing number.',
      customCss: [
        '@fontsource/albert-sans/400.css',
        '@fontsource/albert-sans/500.css',
        '@fontsource/albert-sans/600.css',
        '@fontsource/albert-sans/700.css',
        '@fontsource/albert-sans/400-italic.css',
        '@fontsource/albert-sans/700-italic.css',
        './src/styles/site.css',
        './src/styles/atlas.css',
        './src/styles/browse.css',
        './src/styles/reading.css',
        './src/styles/shell.css',
      ],
      social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/drzkid96/SoCal-Super-Standards' }],
      lastUpdated: false,
      components: {
        Header: './src/components/Header.astro',
        PageTitle: './src/components/PageTitle.astro',
        Pagination: './src/components/Pagination.astro',
        ThemeProvider: './src/components/ThemeProvider.astro',
        ThemeSelect: './src/components/ThemeSelect.astro',
      },
      head: [
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/jurisdiction.js?v=' + scriptVersion('jurisdiction'), defer: true } },
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/search.js?v=' + scriptVersion('search'), defer: true } },
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/site.js?v=' + scriptVersion('site'), defer: true } },
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/reference-tools.js?v=' + scriptVersion('reference-tools'), defer: true } },
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/sheets.js?v=' + scriptVersion('sheets'), defer: true } },
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/recent-pages.js?v=' + scriptVersion('recent-pages'), defer: true } },
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/reader-size.js?v=' + scriptVersion('reader-size'), defer: true } },
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/calculations.js?v=' + scriptVersion('calculations'), defer: true } },
        { tag: 'script', attrs: { src: '/SoCal-Super-Standards/js/panel.js?v=' + scriptVersion('panel'), defer: true } },
      ],
      routeMiddleware: './src/lib/boe-navigation.ts',
      pagination: true,
      tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 2 },
      sidebar: [
        { label: 'Quick Lookup', items: [
          { label: 'Search all standards', link: '/search/' },
          { label: 'Detail & Drawing Index', link: '/details/' },
          { label: 'Sign Library', link: '/signs/' },
          { label: 'Pavement Markings', link: '/markings/' },
          { label: 'Caltrans Line Types (49)', link: '/markings/line-types/' },
          { label: 'Keyword Index A–Z', link: '/keywords/' },
          { label: 'What Governs (Status)', link: '/bulletins/standards-status/' },
        ] },
        { label: 'Design by Topic', collapsed: true, items: [
          { label: 'All 12 Topics (Visual Hub)', link: '/topics/' },
          ...flatTopics,
          { label: 'Tool: Lane Width Comparison', link: '/bulletins/lane-widths/' },
          { label: 'Tool: Bikeway Comparison', link: '/bulletins/bikeway-design-comparison/' },
          { label: 'Tool: LADOT Curb Paint Calc', link: '/ladot/curb-paint/' },
        ] },
        { label: 'Issuing agencies', collapsed: true, items: [
          { label: 'Browse agencies', link: '/agencies/' },
          { label: 'Southern California regional standards', link: '/regions/' },
          { label: 'Caltrans', link: '/caltrans/' },
          { label: 'FHWA', link: '/fhwa/' },
          { label: 'U.S. Access Board', link: '/ada/' },
          { label: 'LA Bureau of Engineering', link: '/boe/' },
          { label: 'LADOT', link: '/ladot/' },
        ] },
        { label: 'State & Federal Standards', collapsed: true, items: [
          { label: 'CA MUTCD 2026', collapsed: true, items: [{ label: 'Overview', link: '/ca-mutcd/' }, ...caParts, { label: 'LA28 Supplement (GRN)', link: '/caltrans/la28-supplement/' }] },
          { label: 'Caltrans 2026 Standard Plans', link: '/caltrans/standard-plans-2026/' },
          { label: 'Bulletins & Policy Memos', collapsed: true, items: [
            { label: 'All Bulletins & Memos', link: '/bulletins/' },
            { label: 'Caltrans HDM Ch. 1000 Bikeways', link: '/bulletins/caltrans-hdm-ch1000/' },
            { label: 'Caltrans DIB 94 Complete Streets', link: '/bulletins/caltrans-dib-94/' },
            { label: 'Caltrans DIB 89-02 Class IV', link: '/bulletins/caltrans-dib-89-02/' },
            { label: 'Caltrans DIB 82-06 Accessibility', link: '/bulletins/caltrans-dib-82-06/' },
            { label: 'Caltrans DIB 79-04 · 81-03 · 90 · 92 · 93', collapsed: true, items: [
              { label: 'DIB 79-04 (2R/3R)', link: '/bulletins/caltrans-dib-79-04/' },
              { label: 'DIB 81-03 (CAPM)', link: '/bulletins/caltrans-dib-81-03/' },
              { label: 'DIB 90 (DDI)', link: '/bulletins/caltrans-dib-90/' },
              { label: 'DIB 92 (SPI)', link: '/bulletins/caltrans-dib-92/' },
              { label: 'DIB 93 (Evacuation Routes)', link: '/bulletins/caltrans-dib-93/' },
            ] },
            { label: 'LADOT Policy Memos & Checklist', collapsed: true, items: [
              { label: 'LADOT Lane Reconfiguration (2023)', link: '/bulletins/ladot-lane-reconfiguration-2023/' },
              { label: 'LADOT Bikeway Marking (2022)', link: '/bulletins/ladot-bikeway-marking-2022/' },
              { label: 'LADOT Leading Pedestrian Interval', link: '/bulletins/ladot-lpi-2021/' },
              { label: 'LADOT Exclusive Pedestrian Phase', link: '/bulletins/ladot-exclusive-ped-phase-2017/' },
              { label: 'LADOT Accessible Parking Zones', link: '/bulletins/ladot-accessible-parking-2017/' },
              { label: 'LADOT S&S Plan Review Checklist', link: '/bulletins/ladot-ss-plan-checklist-2022/' },
            ] },
            { label: 'PROWAG (ADA Right-of-Way)', link: '/bulletins/prowag-2023/' },
            { label: 'CBC 11B Accessible Parking', link: '/bulletins/ca-accessible-parking-2026/' },
          ] },
          { label: 'Federal MUTCD 11th Ed. R1', collapsed: true, items: [{ label: 'Overview', link: '/mutcd/' }, ...fedParts] },
        ] },
        { label: 'LA County Agencies', collapsed: true, items: [
          { label: "LA BOE Street Design Manual", link: "/boe/street-design/" },
          ...cityAgencyDocs,
          { label: 'LADOT (12 Manuals & Drawings)', collapsed: true, items: [
            { label: 'All LADOT Documents', link: '/ladot/' },
            ...ladotDocs,
          ] },
        ] },
        { label: 'National Design Guides', collapsed: true, items: [
          { label: 'All Guides & Coverage', link: '/guides/' },
          ...refCards,
          ...guideDocs,
          { label: 'Sources & Versions', link: '/sources/' },
          { label: 'How to Use This Site', link: '/guide/' },
        ] },
      ],
    }),
  ],
});
