import fs from 'node:fs';

export const BASE = '/SoCal-Super-Standards';

export type NavLink = { label: string; href: string };
export type PageNav = { prev?: NavLink; up?: NavLink; next?: NavLink };

const normId = (raw: string) => (raw || '').replace(/\/index$/, '').replace(/^index$/, '').replace(/^\/+|\/+$/g, '');
const trunc = (s: string, n = 42) => (s.length <= n ? s : s.slice(0, n - 1).trimEnd() + '…');

// Build-time cached sequential maps for every section on the site
const NAV_MAP = new Map<string, PageNav>();

function registerSeq(items: NavLink[], up?: NavLink) {
  for (let i = 0; i < items.length; i++) {
    const id = normId(items[i].href.replace(BASE, ''));
    if (!id) continue;
    const prev = i > 0 ? items[i - 1] : undefined;
    const next = i + 1 < items.length ? items[i + 1] : undefined;
    NAV_MAP.set(id, { prev, up, next });
  }
}

function init() {
  if (NAV_MAP.size > 0) return;

  // 1. Topics
  try {
    const tGroups = JSON.parse(fs.readFileSync('./data/topics.json', 'utf8')) as {
      group: string;
      topics: { slug: string; name: string }[];
    }[];
    const topics = tGroups.flatMap((g) => g.topics.map((t) => ({ label: trunc(t.name, 38), href: `${BASE}/topics/${t.slug}/` })));
    registerSeq(topics, { label: 'All Topics', href: `${BASE}/topics/` });
  } catch {}

  // 2. National design guides
  try {
    const refs = JSON.parse(fs.readFileSync('./data/refcards.json', 'utf8')) as { slug: string; short: string }[];
    registerSeq(
      refs.map((r) => ({ label: r.short, href: `${BASE}/guides/${r.slug}/` })),
      { label: 'National Design Guides', href: `${BASE}/guides/` },
    );
  } catch {}

  // 3. Bulletins & policy memos
  const bulletins: NavLink[] = [
    { label: 'Standards Status', href: `${BASE}/bulletins/standards-status/` },
    { label: 'Lane Width Comparison', href: `${BASE}/bulletins/lane-widths/` },
    { label: 'Bikeway Design Comparison', href: `${BASE}/bulletins/bikeway-design-comparison/` },
    { label: 'Caltrans HDM Ch. 1000', href: `${BASE}/bulletins/caltrans-hdm-ch1000/` },
    { label: 'Caltrans DIB 94', href: `${BASE}/bulletins/caltrans-dib-94/` },
    { label: 'Caltrans DIB 89-02', href: `${BASE}/bulletins/caltrans-dib-89-02/` },
    { label: 'Caltrans DIB 82-06', href: `${BASE}/bulletins/caltrans-dib-82-06/` },
    { label: 'Caltrans DIB 79-04', href: `${BASE}/bulletins/caltrans-dib-79-04/` },
    { label: 'Caltrans DIB 81-03', href: `${BASE}/bulletins/caltrans-dib-81-03/` },
    { label: 'Caltrans DIB 93', href: `${BASE}/bulletins/caltrans-dib-93/` },
    { label: 'Caltrans DIB 92', href: `${BASE}/bulletins/caltrans-dib-92/` },
    { label: 'Caltrans DIB 90', href: `${BASE}/bulletins/caltrans-dib-90/` },
    { label: 'LADOT Lane Reconfiguration', href: `${BASE}/bulletins/ladot-lane-reconfiguration-2023/` },
    { label: 'LADOT Bikeway Marking', href: `${BASE}/bulletins/ladot-bikeway-marking-2022/` },
    { label: 'LADOT LPI Policy', href: `${BASE}/bulletins/ladot-lpi-2021/` },
    { label: 'LADOT Exclusive Ped Phase', href: `${BASE}/bulletins/ladot-exclusive-ped-phase-2017/` },
    { label: 'LADOT S&S Plan Checklist', href: `${BASE}/bulletins/ladot-ss-plan-checklist-2022/` },
    { label: 'LADOT Accessible Parking', href: `${BASE}/bulletins/ladot-accessible-parking-2017/` },
    { label: 'PROWAG (ADA)', href: `${BASE}/bulletins/prowag-2023/` },
    { label: 'CBC 11B Accessible Parking', href: `${BASE}/bulletins/ca-accessible-parking-2026/` },
  ];
  registerSeq(bulletins, { label: 'All Bulletins & Memos', href: `${BASE}/bulletins/` });

  // 4. CA MUTCD 2026 & Federal MUTCD 11E R1 chapters
  for (const [dir, jsonPath, upLabel] of [
    ['ca-mutcd', './data/ca-mutcd/chapters.json', 'CA MUTCD 2026'],
    ['mutcd', './data/mutcd/chapters.json', 'Federal MUTCD 11th Ed. R1'],
  ] as const) {
    try {
      const chs = JSON.parse(fs.readFileSync(jsonPath, 'utf8')) as { code: string; title: string }[];
      registerSeq(
        chs.map((c) => ({ label: `${c.code} ${trunc(c.title, 30)}`, href: `${BASE}/${dir}/${c.code.toLowerCase()}/` })),
        { label: upLabel, href: `${BASE}/${dir}/` },
      );
    } catch {}
  }

  // 5. Document chapters (LADOT, Caltrans, Burbank, Pasadena, FHWA, ADA)
  for (const cfgFile of ['./pipeline/config/ladot.json', './pipeline/config/agencies.json', './pipeline/config/guides.json']) {
    try {
      const cfgs = JSON.parse(fs.readFileSync(cfgFile, 'utf8')) as { slug: string; short: string }[];
      for (const c of cfgs) {
        const dp = `./data/docs/${c.slug.replace('/', '__')}.json`;
        if (!fs.existsSync(dp)) continue;
        const d = JSON.parse(fs.readFileSync(dp, 'utf8')) as { chapters?: { slug: string; title: string }[] };
        const chs = d.chapters || [];
        if (chs.length > 0) {
          registerSeq(
            chs.map((ch) => ({ label: trunc(ch.title, 34), href: `${BASE}/${c.slug}/${ch.slug}/` })),
            { label: `${c.short} overview`, href: `${BASE}/${c.slug}/` },
          );
        }
      }
    } catch {}
  }

  // 6. Standard drawing pages grouped by source document
  try {
    const det = JSON.parse(fs.readFileSync('./public/data/details.json', 'utf8')) as {
      type: string;
      src: string;
      num: string;
      title: string;
      url: string;
    }[];
    const bySrc = new Map<string, { num: string; title: string; url: string }[]>();
    for (const i of det) {
      if (i.type !== 'Standard drawing') continue;
      if (!bySrc.has(i.src)) bySrc.set(i.src, []);
      bySrc.get(i.src)!.push(i);
    }
    const natKey = (s: string) => (s.match(/\d+/g) || ['0']).map((n) => Number(n));
    for (const [src, list] of bySrc.entries()) {
      list.sort((a, b) => {
        const ka = natKey(a.num), kb = natKey(b.num);
        for (let k = 0; k < Math.max(ka.length, kb.length); k++) {
          const d = (ka[k] ?? 0) - (kb[k] ?? 0);
          if (d !== 0) return d;
        }
        return a.num.localeCompare(b.num);
      });
      registerSeq(
        list.map((x) => ({ label: `${x.num} ${trunc(x.title, 28)}`, href: x.url })),
        { label: `All ${src} drawings`, href: `${BASE}/details/?src=${encodeURIComponent(src)}` },
      );
    }
    // Secondary LADOT detail pages not listed as primary items in details.json
    const ladotDir = './src/content/docs/details/ladot';
    if (fs.existsSync(ladotDir)) {
      const extras: NavLink[] = [];
      for (const f of fs.readdirSync(ladotDir).sort()) {
        if (!f.endsWith('.md')) continue;
        const slug = f.slice(0, -3);
        const id = `details/ladot/${slug}`;
        if (!NAV_MAP.has(id)) {
          const num = slug.replace(/^.*?(s-\d+(?:-\d+)?)$/i, '$1').toUpperCase().replace(/-/g, '.').replace(/^S\./, 'S-');
          extras.push({ label: `${num} (secondary sheet)`, href: `${BASE}/${id}/` });
        }
      }
      if (extras.length) {
        registerSeq(extras, { label: 'All LADOT drawings', href: `${BASE}/details/?sg=LADOT&type=Standard+drawing` });
      }
    }
  } catch {}

  // 7. Sign Library pages (ordered as in data/signs/signs.json)
  try {
    const signs = JSON.parse(fs.readFileSync('./data/signs/signs.json', 'utf8')) as {
      code: string;
      slug: string;
      name?: string;
      descriptor?: string;
    }[];
    registerSeq(
      signs.map((s) => ({
        label: `${s.code} ${trunc(s.name || s.descriptor || '', 26)}`.trim(),
        href: `${BASE}/signs/${s.slug}/`,
      })),
      { label: 'Sign Library', href: `${BASE}/signs/` },
    );
  } catch {}

  // 8. SoCal Municipal Standards sequence
  registerSeq(
    [
      { label: 'Burbank Standard Plans', href: `${BASE}/burbank/standard-plans/` },
      { label: 'Pasadena Standard Plans', href: `${BASE}/pasadena/standard-plans/` },
      { label: 'Long Beach Standard Plans', href: `${BASE}/long-beach/standard-plans/` },
      { label: 'Palmdale Standard Drawings', href: `${BASE}/palmdale/standard-plans/` },
      { label: 'Torrance Standard Plans', href: `${BASE}/torrance/standard-plans/` },
      { label: 'Gardena Standard Plans', href: `${BASE}/gardena/standard-plans/` },
      { label: 'Glendora 2024 Standards', href: `${BASE}/glendora/standard-plans/` },
      { label: 'Santa Monica Standard Details', href: `${BASE}/santa-monica/standard-plans/` },
      { label: 'West Hollywood Engineering', href: `${BASE}/west-hollywood/standard-plans/` },
      { label: 'Culver City Complete Streets', href: `${BASE}/culver-city/standard-plans/` },
    ],
    { label: 'LA County Cities Hub', href: `${BASE}/cities/` },
  );

  // 9. Markings & LADOT utility subpages
  NAV_MAP.set('markings/line-types', {
    prev: { label: 'Pavement Marking Library', href: `${BASE}/markings/` },
    up: { label: 'Pavement Markings', href: `${BASE}/markings/` },
  });
  NAV_MAP.set('ladot/curb-paint', {
    up: { label: 'LADOT Standards', href: `${BASE}/ladot/` },
    next: { label: 'MPP Redrawn Gallery', href: `${BASE}/ladot/mpp-details/` },
  });
  NAV_MAP.set('ladot/mpp-details', {
    prev: { label: 'Curb Paint & Red Curb', href: `${BASE}/ladot/curb-paint/` },
    up: { label: 'LADOT Standards', href: `${BASE}/ladot/` },
  });
}

export function getPageNav(entryId: string): PageNav | undefined {
  init();
  return NAV_MAP.get(normId(entryId));
}
