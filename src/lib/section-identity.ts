import fs from 'node:fs';
import { BASE } from './nav';

type Profile = { key: string; name: string; kind: string; home: string; publications: {url: string; title: string}[] };
type Section = [string, string, string];
type Link = { label: string; href: string };
const read = (file: string) => JSON.parse(fs.readFileSync(file, 'utf8'));
const sections: Record<string, Section> = read('.standards/section-identity.json');
const profiles: Record<string, Profile> = read('public/api/v2/profiles.json');
const scopes: Record<string, { roots: string[] }> = read('public/data/agency-modes.json');
const topics: Record<string,string> = read('public/api/v2/topics.json');
const aliases: Record<string,string> = { 'aashto': 'guides' };
const owners = Object.entries(scopes).flatMap(([key, mode]) => mode.roots.map(prefix => ({ prefix, key })))
  .sort((a, b) => b.prefix.length - a.prefix.length);
const books = Object.values(profiles).flatMap(profile => profile.publications)
  .sort((a, b) => b.url.length - a.url.length);
const first = (s:string) => s.charAt(0).toUpperCase()+s.slice(1);
const names: Record<string,string> = {
  topics:'Design topic', signs:'Sign reference', markings:'Marking reference', details:'Drawing or detail',
  bulletins:'Policy and design reference', guides:'Design guide', regions:'Jurisdiction directory',
  transit:'Operator guide', boe:'Street design section', mutcd:'Manual chapter', 'ca-mutcd':'Manual chapter',
  search:'Search', map:'Municipal standards map', agencies:'Agency directory', keywords:'Subject index'
};
export function sectionIdentity(id: string) {
  const [top, sub, third] = id.split('/');
  const path = '/'+id+'/', url=BASE+path;
  const key=owners.find(item => path.startsWith(item.prefix))?.key;
  const agency=key && profiles[key];
  const book=books.find(entry=>url.startsWith(entry.url));
  const family=sections[aliases[top]||top] || (agency ?
    [agency.name,agency.kind+' publications and standards.','green'] :
    [first(top.replaceAll('-',' ')), 'Browse the source and its related references.', 'teal']);
  let type = sub ? (names[top] || (book ? 'Publication section' : 'Reference page')) : 'Section index';
  if(top==='regions' && sub && !third)type=agency?.kind||'Authority profile';
  if(top==='regions' && third)type='Source publication';
  if(book?.url===url && top!=='regions')type=top==='transit'?'Operator guide':'Source publication';
  if(top==='map')type=sub?'Database documentation':'Municipal directory';
  const tone=agency?.kind==='Transit agency'?'violet':family[2];
  const parent: Link | undefined=book && book.url!==url ? {label:book.title,href:book.url} :
    agency && agency.home!==url ? {label:agency.name,href:agency.home} :
    sub ? {label:family[0],href:BASE+'/'+(aliases[top]||top)+'/'} : undefined;
  const mapHref = agency ? BASE+'/map/?issuer='+agency.key :
    top==='topics' && topics[sub] ? BASE+'/map/?topic='+sub : BASE+'/map/';
  const label= top==='regions' && agency ? (agency.kind==='Transit agency'?'Transit operators':'Issuing jurisdictions') :
    family[0];
  return { label, type, tone, parent, mapHref, showMap:top!=='map' && (!!agency||top==='topics'||top==='regions'||top==='agencies'), description:family[1] };
}
