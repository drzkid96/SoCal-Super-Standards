import { readFileSync } from 'node:fs';
import { BASE, getPageNav } from './nav';
import { defineRouteMiddleware, type StarlightRouteData } from '@astrojs/starlight/route-data';

type Entry = StarlightRouteData['sidebar'][number];
type Heading = NonNullable<StarlightRouteData['toc']>['items'][number];
type Page = { label: string; parent: string; headings: Omit<Heading, 'children'>[] };
type Group = Extract<Entry, { type: 'group' }>;
const manual = BASE + '/boe/street-design/';
const directoryNames: Record<string, [string, string, string]> = JSON.parse(
  readFileSync('.standards/section-identity.json', 'utf8'));
const operators: string[][] = JSON.parse(readFileSync('data/reference/transit-guides.json', 'utf8'));
const directories = ['guides', 'topics', 'map', 'signs', 'details', 'markings', 'transit', 'regions'];
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

function group(label: string, entries: Entry[], collapsed = false): Group {
  return { type: 'group', label, entries, collapsed, badge: undefined };
}

function findGroup(entries: Entry[], name: string): Group | undefined {
  for (const entry of entries) {
    if (entry.type !== 'group') continue;
    if (entry.label === name) return entry;
    const child = findGroup(entry.entries, name);
    if (child) return child;
  }
}

// Every part remains reachable from the book index. Show the open chapter's
// siblings in place so the reader can move directly within the current part.
function manualNavigation(tree: Group, current: string, index: string): Group {
  const entries: Entry[] = [sectionLink('Contents', index, current)];
  for (const part of tree.entries) {
    if (part.type !== 'group') continue;
    if (part.entries.some(child => child.type === 'link' && child.href === current)) {
      entries.push(group(part.label, part.entries));
    } else {
      const number = /^Part (\d+)/.exec(part.label)?.[1];
      const first = part.entries.find(child => child.type === 'link');
      if (number) entries.push(sectionLink(part.label, index + '#part-' + number, current));
      else if (first?.type === 'link') entries.push(sectionLink(part.label, first.href, current));
    }
  }
  return group(tree.label, entries);
}

function collection(current: string, route: StarlightRouteData): Group | undefined {
  const id = current.slice(BASE.length + 1).replace(/\/$/, '');
  const [section] = id.split('/');
  const index = BASE + '/' + section + '/';
  if (current.startsWith(manual)) {
    return group('BOE Street Design Manual', [sectionLink('Manual index', manual, current), ...sections(manual, current)]);
  }
  if (section === 'mutcd' || section === 'ca-mutcd') {
    const edition = findGroup(route.sidebar, section === 'mutcd' ? 'Federal MUTCD 11th Ed. R1' : 'CA MUTCD 2026');
    if (edition) return manualNavigation(edition, current, index);
  }
  const entries = new Map<string, Entry>();
  const add = (label: string, href: string) => {
    if (!entries.has(href)) entries.set(href, sectionLink(label, href, current));
  };
  const title = directoryNames[section]?.[0];
  if (title) add(title, index);
  if (section === 'signs') {
    add('Sign blocks (DWG)', BASE + '/signs/cad/');
  } else if (section === 'transit') {
    for (const [slug, operator] of operators) add(operator, index + slug + '/');
  } else if (section === 'regions' || section === 'cities') {
    add('Find a municipality on the map', BASE + '/map/');
  }
  const up = getPageNav(id)?.up;
  if (up) add(up.label, up.href);
  if (id && route.entry.data.title) add(route.entry.data.title, current);
  return entries.size ? group(title || 'In this section', [...entries.values()]) : undefined;
}

export const onRequest = defineRouteMiddleware(({ url, locals }) => {
  const current = url.pathname.replace(/\/?$/, '/');
  const route = locals.starlightRoute;
  const local = collection(current, route);
  const directory = directories
    .filter(key => !(local?.entries.some(item => item.type === 'link' && item.href === BASE + '/' + key + '/')))
    .map(key => sectionLink(directoryNames[key][0], BASE + '/' + key + '/', current));
  route.sidebar = [...(local ? [local] : []), group('Browse standards', directory, Boolean(local))];
  if (!current.startsWith(manual)) return;

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
