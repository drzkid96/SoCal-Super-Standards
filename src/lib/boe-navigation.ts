import { readFileSync } from 'node:fs';
import { defineRouteMiddleware, type StarlightRouteData } from '@astrojs/starlight/route-data';

type Entry = StarlightRouteData['sidebar'][number];
type Heading = NonNullable<StarlightRouteData['toc']>['items'][number];
type Page = { label: string; parent: string; headings: Omit<Heading, 'children'>[] };
const manual = '/SoCal-Super-Standards/boe/street-design/';
const pages: Record<string, Page> = JSON.parse(readFileSync('.standards/boe-navigation.json', 'utf8'));
const children = new Map<string, string[]>();
for (const [url, page] of Object.entries(pages)) {
  const siblings = children.get(page.parent) || [];
  siblings.push(url);
  children.set(page.parent, siblings);
}

function sectionLink(label: string, href: string, current: string): Entry {
  return { type: 'link', label, href, isCurrent: current === href, attrs: {}, badge: undefined };
}

function sections(parent: string, current: string): Entry[] {
  return (children.get(parent) || []).map(href => {
    const label = pages[href].label;
    const nested = sections(href, current);
    if (!nested.length) return sectionLink(label, href, current);
    return { type: 'group', label, badge: undefined, collapsed: true,
      entries: [sectionLink('Section overview', href, current), ...nested] };
  });
}

export const onRequest = defineRouteMiddleware(({ url, locals }) => {
  const current = url.pathname.replace(/\/?$/, '/');
  if (!current.startsWith(manual)) return;
  const route = locals.starlightRoute;
  const manualGroup: Entry = { type: 'group', label: 'BOE Street Design Manual', collapsed: false, badge: undefined,
    entries: [sectionLink('Manual index', manual, current), ...sections(manual, current)] };
  route.sidebar = [manualGroup, ...route.sidebar.map(entry => {
    if (entry.type !== 'group' || entry.label !== 'LA County Agencies') return entry;
    return { ...entry, entries: entry.entries.filter(child => child.type !== 'link' || child.href !== manual) };
  })];

  const headings = pages[current]?.headings;
  if (!headings?.length || !route.toc) {
    route.toc = undefined;
    return;
  }
  const items: Heading[] = [route.toc.items[0]];
  const parents: Heading[] = [];
  for (const heading of headings) {
    const item = { ...heading, children: [] };
    while (parents.length && parents[parents.length - 1].depth >= item.depth) parents.pop();
    (parents.at(-1)?.children || items).push(item);
    parents.push(item);
  }
  route.toc = { minHeadingLevel: 2, maxHeadingLevel: 6, items };
});
