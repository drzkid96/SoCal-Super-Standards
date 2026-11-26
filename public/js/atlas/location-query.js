// All locality names and aliases resolve to entries in the bundled geographic directory.
const normalize = value => String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
  .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
const cityAliases = {la:'Los Angeles', 'l a':'Los Angeles', sd:'San Diego', ventura:'San Buenaventura',
  'ventura san buenaventura':'San Buenaventura', 'san buenaventura ventura':'San Buenaventura'};
const countyAliases = {oc:'Orange', 'o c':'Orange', 'la county':'Los Angeles', 'l a county':'Los Angeles',
  'sd county':'San Diego', 'sb county':'San Bernardino'};

export function makePlaceSearch(places) {
  const cities = places.filter(p => p.kind === 'city');
  const counties = places.filter(p => p.kind === 'county');
  function city(term) {
    const key = normalize(term).replace(/^city of /, '');
    const wanted = normalize(cityAliases[key] || key);
    return cities.find(p => normalize(p.name) === wanted ||
      wanted === 'san buenaventura' && p.name.startsWith('San Buenaventura'));
  }
  function county(term) {
    const key = normalize(term);
    const name = countyAliases[key] || (key.startsWith('county of ') ? key.slice(10)
      : key.endsWith(' county') ? key.slice(0, -7) : '');
    return counties.find(p => normalize(p.name) === normalize(name));
  }
  function suggestions(term, allowed) {
    const key = normalize(term).replace(/^city of /, '');
    if (key.length < 2) return [];
    return places.filter(p => allowed(p) && (normalize(p.name).startsWith(key) ||
      p.name.startsWith('San Buenaventura') && 'ventura'.startsWith(key)))
      .sort((a,b) => a.name.localeCompare(b.name) || a.kind.localeCompare(b.kind)).slice(0,12);
  }
  function parse(input) {
    let text = input.trim();
    const numeric = /^([+-]?\d+(?:\.\d+)?)\s*(?:[,;]\s*|\s+)([+-]?\d+(?:\.\d+)?)$/.exec(text);
    if (numeric) {
      const [a,b] = numeric.slice(1).map(Number);
      const [x,y] = a < -90 || Math.abs(b) <= 90 && a < 0 ? [a,b] : [b,a];
      return Math.abs(x) <= 180 && Math.abs(y) <= 90 ? {x,y} : {error:'Enter a valid latitude and longitude.'};
    }
    let mode = '';
    const prefix = /^(stops?|streets?)\s*:\s*/i.exec(text);
    if (prefix) {
      mode = prefix[1].toLowerCase().startsWith('stop') ? 'stops' : 'streets';
      text = text.slice(prefix[0].length);
    }
    text = text.replace(/(?:,\s*|\s+)(?:CA|California)(?:\s+\d{5}(?:-\d{4})?)?$/i, '').trim();
    const parts = text.split(',').map(v => v.trim());
    let localCounty, localCity;
    if (parts.length > 1 && (localCounty = county(parts.at(-1)))) parts.pop();
    if (parts.length > 1) {
      localCity = city(parts.at(-1));
      if (!localCity) return {error:'City or county not found. Use an incorporated city or a county name, such as Orange County.'};
      parts.pop();
    }
    if (parts.length !== 1) return {error:'Enter a name followed by a city, a county, or both.'};
    const term = parts[0];
    if (!term) return {error:'Enter a city, street, intersection, stop name, or coordinates.'};
    const area = mode ? null : county(term) || city(term);
    if (localCounty && [localCity,area].some(p => p && p.county !== localCounty.county))
      return {error:'The named location and county do not match.'};
    if (area && !localCity) return {area};
    const pair = mode || /\bpark\s+and\s+ride\b/i.test(term) ? null
      : term.split(/\s*(?:&|@|\/)\s*|\s+(?:and|at)\s+/i);
    if (pair?.length > 1 && (pair.length !== 2 || pair.some(v => !v.trim())))
      return {error:'Enter two street names, for example Holly St & Arroyo Pkwy, Pasadena. For a stop name containing a slash, begin with “stop:”.'};
    if (pair?.length === 2 && normalize(pair[0]) === normalize(pair[1]))
      return {error:'Enter two different street names for an intersection.'};
    if (pair?.length === 2 && pair.some(v => /^(?:street|st|avenue|ave|boulevard|blvd|road|rd|lane|ln|drive|dr|court|ct|parkway|pkwy)$/i.test(v.trim())))
      return {error:'Include the street name on each side, for example Main St & 1st Ave.'};
    return {term, mode, pair:pair?.length === 2 ? pair : null, localCity, localCounty};
  }
  return {parse,suggestions};
}

// A single divided-road junction can have several surveyed nodes. Keep every
// coordinate available while collecting adjacent records under their shared name.
export function groupCrossingPoints(items) {
  const grouped=[], matches=new Map();
  for(const item of items){
    if(item.type!=='Intersection'){grouped.push(item);continue;}
    const key=[item.county,item.place,item.label].join('|');
    let nearby=matches.get(key);
    if(!nearby){nearby=[];matches.set(key,nearby);}
    const index=nearby.find(i=>{
      const point=grouped[i];
      const dx=(point.x-item.x)*111320*Math.cos(item.y*Math.PI/180),dy=(point.y-item.y)*110900;
      return Math.hypot(dx,dy)<=65;
    });
    if(index===undefined){nearby.push(grouped.length);grouped.push(item);}
    else{
      const record=grouped[index];
      if(!record.points)grouped[index]={...record,points:[record,item]};
      else record.points.push(item);
    }
  }
  return grouped;
}
