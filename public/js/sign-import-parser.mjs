// Preserve identity through extraction. Only an exact, unique native specimen is preselected.
const family = '(?:OM|SW|SR|SG|W|R|D|M|G|C|E|S|I|EM|CW|MOT|NLU)';
const dash = /[‐‑‒–—−]/g;
const number = '(?:\\s*-\\s*)?\\d+[A-Za-z]*(?:\\s*-\\s*\\d+[A-Za-z]*){0,3}';
const special = '(?:MOD(?:IFIED)?(?:[ -]+(?:\\d+|[A-Z](?![A-Z])))?|LEFT|RIGHT|LT|RT)';
const codes = new RegExp('(?<![\\p{L}\\p{N}_-])(?:'+family+'\\s*'+number+'|41-\\d{4})(?:[ \\t]*\\([^()\\r\\n]{1,55}\\)|[ \\t]+'+special+'\\b|\\/(?:LT|RT|L|R)\\b)*(?![\\p{L}\\p{N}_-])','giu');
const speedFamily = /^(R2-1|W13-1P?)(?:\s+|\s*-\s*|\s*\()([0-9]{1,2})(?:\s*(?:M\.?P\.?H\.?))?\)?$/i;
const speedTail = /^\s*(?:[,;:]?\s*(?:(?:SPEED LIMIT)\s+)?)(\d{1,2})\s*(?:M\.?P\.?H\.?)\b/i;
const textKey = value => value.normalize('NFKC').replace(dash,'-').replace(/[“”]/g,'"').replace(/[‘’]/g,"'").trim().toUpperCase();

export function designation(value) {
  let s=textKey(value);
  const speed=s.match(speedFamily);
  if(speed) s=speed[1]+'('+speed[2]+')';
  return s.replace(/\bMODIFIED\b/g,'MOD').replace(/\s*([()\-/])\s*/g,'$1').replace(/\s+/g,' ')
    .replace(/^([A-Z]{1,3})\s+(?=\d)/,'$1').replace(/\s+(MOD(?: [A-Z0-9]+)?|LT|RT|LEFT|RIGHT)$/,'($1)');
}
function baseCode(key) {
  const first=key.match(/^(?:OM|SW|SR|SG|W|R|D|M|G|C|E|S|I|EM|CW|MOT|NLU)-?\d+[A-Z]*(?:-\d+[A-Z]*)*/);
  if(!first) return '';
  // L and R terminate many published directional numbers. Keep the remainder and California suffix.
  return first[0].replace(/(?<=\d|P)(?:LT|RT|L|R)$/,'')+(key.includes('(CA)')?'(CA)':'');
}
function grouped(map,key,data) {
  if(!key)return;
  if(!map.has(key))map.set(key,new Map());
  map.get(key).set(data.id,data);
}
const libWord = s => s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&').replace(/\s+/g,'\\s+');
export function makeCatalog(records) {
  const exact=new Map(), families=new Map(), phrases=new Set();
  for(const record of records) {
    const aliases=Array.isArray(record.aliases)?record.aliases:[];
    for(const name of [record.code,...aliases].filter(s=>typeof s==='string'&&s.trim())) {
      const key=designation(name);grouped(exact,key,record);
      const base=baseCode(key);grouped(families,base,record);
      if(!base && /[A-Z]/.test(key) && /[\s\d]/.test(key))phrases.add(textKey(name));
    }
    if(/^R2-1$/i.test(record.code)) {
      const speed=(record.variant||'').match(/^SPEED LIMIT\s+(\d{1,2})$/i);
      if(speed)grouped(exact,'R2-1('+speed[1]+')',record);
    }
  }
  const terms=[...phrases].sort((a,b)=>b.length-a.length).map(libWord);
  return {exact,families,phrases:terms.length?new RegExp('(?<![A-Z0-9])(?:'+terms.join('|')+')(?![A-Z0-9])','gi'):null};
}
function resolve(raw,catalog) {
  const key=designation(raw);
  let choices=[...(catalog.exact.get(key)?.values()||[])];
  const base=baseCode(key), related=[...(catalog.families.get(base)?.values()||[])];
  const bare=base===key;
  // Unqualified speed and directional families cannot choose a sign legend from its code alone.
  const conditional=key==='R2-1'||/^W13-1P?$/.test(key)||
    related.some(r=>/\((?:L|R|LT|RT|LEFT|RIGHT)\)|(?<=\d|P)(?:L|R)(?=\(CA\)|$)/.test(designation(r.code)));
  if(bare && conditional && related.length>choices.length)choices=related;
  const exact=catalog.exact.has(key);
  if(!choices.length && bare)choices=related;
  // A worded legend can be printed on several sign designs even where the
  // library has one drawing bearing that exact name. Confirm those explicitly.
  const coded=Boolean(base)||/^41-\d{4}/.test(key);
  const status=choices.length===1&&exact&&coded?'matched':choices.length?'ambiguous':'unmatched';
  return {raw,key,status,count:1,choices,selected:status==='matched'?choices[0].id:''};
}
export function scanLines(lines,catalog) {
  const rows=new Map();
  const bareQualifier=/^(?:\((?:CA|MOD(?:[ -][A-Z0-9]+)?|LEFT|RIGHT|LT|RT|L|R|\d{1,3})\)|MOD(?:[ -][A-Z0-9]+)?)$/i;
  const unplaced=new Set();
  const nonempty=lines.filter(line=>line.trim());
  for(let i=0;i<nonempty.length;i++)if(bareQualifier.test(nonempty[i].trim())){
    for(const line of nonempty.slice(Math.max(0,i-2),i))unplaced.add(line);
  }
  function add(raw,evidence) {
    const candidate=resolve(raw.trim(),catalog);
    if(unplaced.has(evidence)&&candidate.status==='matched'){
      candidate.status='ambiguous';candidate.selected='';
    }
    const seen=rows.get(candidate.key);
    if(seen)seen.count++;
    else rows.set(candidate.key,{...candidate,evidence:evidence.trim().slice(0,240)});
  }
  for(const original of lines) {
    const s=original.normalize('NFKC').replace(dash,'-').trim();
    if(!s)continue;
    if(bareQualifier.test(s)){add(s,'Unattached qualifier: '+original);continue;}
    // An explicit full line can be a local or composite designation (including quoted legends).
    if(catalog.exact.has(designation(s)) && !/^[a-z]+$/i.test(s)){add(s,original);continue;}
    const used=[];
    if(catalog.phrases)for(const m of s.matchAll(catalog.phrases)){
      used.push([m.index,m.index+m[0].length]);add(m[0],original);
    }
    for(const m of s.matchAll(codes)) {
      if(used.some(([a,b])=>m.index<b&&m.index+m[0].length>a))continue;
      let raw=m[0].trim();
      // A CAD sign family without a dash is valid for California R26/SW24, for example.
      // A standalone sheet prefix/identifier such as S-2 is not a sign unless cataloged.
      if(/^[A-Z]+\s*-\s*\d+$/i.test(raw)&&!catalog.exact.has(designation(raw)))continue;
      if(/^(R2\s*-\s*1|W13\s*-\s*1P?)$/i.test(raw)){
        const next=s.slice(m.index+m[0].length).match(speedTail);
        if(next)raw+=' ('+next[1]+')';
      }
      add(raw,original);
    }
  }
  return [...rows.values()];
}

// Add a stacked qualifier only when the source coordinates identify one immediate
// callout above it. Text from another column, page or sign remains independent.
export function joinCalloutLines(lines) {
  const result=lines.map(line=>({...line}));
  const head=new RegExp('^(?:'+family+')\\s*'+number+'(?:\\s*\\([^()]+\\))*$','i');
  const qualifier=/^\((?:CA|MOD(?:[ -][A-Z0-9]+)?|LT|RT|LEFT|RIGHT|L\/?R|L|R|\d{1,3})\)$/i;
  for(const row of result){
    if(!qualifier.test(row.text.trim()))continue;
    const candidates=result.filter(up=>{
      const h=Math.max(row.height,up.height),delta=up.baseline-row.baseline;
      const overlap=Math.min(row.right,up.right)-Math.max(row.left,up.left);
      const center=Math.abs(up.left+up.right-row.left-row.right)/2;
      return head.test(up.text.trim())&&row.turn===up.turn&&delta>.35*h&&delta<2*h&&
        overlap>.45*Math.min(row.right-row.left,up.right-up.left)&&center<h*1.5;
    });
    if(candidates.length===1){candidates[0].text+=row.text.trim();row.text='';}
  }
  return result.map(row=>row.text).filter(Boolean);
}
export function pastedPages(raw) {
  const result=[];let lines=[],label='';
  const finish=force=>{if(force||lines.length||label)result.push({label:label||'Sheet '+(result.length+1),lines});lines=[];label='';};
  for(const [i,chunk] of raw.replace(/\r\n?/g,'\n').split('\f').entries()) {
    if(i)finish(true);
    for(const line of chunk.split('\n')) {
      const head=line.match(/^\s*(?:-{2,}\s*)?(?:SHEET|PAGE)\s*(?:[:#]\s*|\s+)\s*([A-Z0-9][^\n]{0,65}?)(?:\s*-{2,})?\s*$/i);
      if(head){
        if(lines.some(x=>x.trim())||label)finish(false);
        label=head[1].trim();
      } else lines.push(line);
    }
  }
  finish(false);return result;
}

export function pdfSheetLabel(raw, page) {
  const label=String(raw||'').trim();
  const repeated=label.match(/^\[(\d+)\]\s+(\d+)\s+(.+)$/);
  if(repeated && Number(repeated[1])===page && Number(repeated[2])===page)return repeated[3].trim();
  return label && label!==String(page)?label:'Sheet '+page;
}
export function pdfLines(items) {
  // Reconstruct nearby runs on the same baseline, including rotated plot callouts.
  const groups=new Map();
  for(const item of items){
    if(!item.str?.trim()||!item.transform)continue;
    const [a,b,c,d,x,y]=item.transform,len=Math.hypot(a,b);
    if(!(len>0))continue;
    const height=Math.max(.1,Math.hypot(c,d)||len),angle=Math.atan2(b,a);
    const turn=Math.round(angle/(Math.PI/90)), bucket=groups.get(turn)||[];groups.set(turn,bucket);
    const along=x*Math.cos(angle)+y*Math.sin(angle),baseline=y*Math.cos(angle)-x*Math.sin(angle);
    bucket.push({along,baseline,height,width:Math.abs(item.width||0),text:item.str.trim()});
  }
  const result=[];
  for(const [turn,tokens] of groups){
    tokens.sort((a,b)=>b.baseline-a.baseline||a.along-b.along);
    const bands=[];
    for(const token of tokens){
      let last=bands.at(-1);
      if(!last||Math.abs(token.baseline-last.baseline)>Math.min(last.height,token.height)*.32){last={...token,runs:[]};bands.push(last);}
      last.runs.push(token);
    }
    for(const band of bands){
      let text='',start=0,end=0,previous=null;
      const flush=()=>{if(text)result.push({text,left:start,right:end,baseline:band.baseline,height:band.height,turn});text='';};
      for(const t of band.runs.sort((a,b)=>a.along-b.along)){
        const gap=t.along-end, h=previous?Math.min(previous.height,t.height):t.height;
        if(previous && (gap>h*1.5||gap< -h*.6))flush();
        else if(text && gap>h*.14)text+=' ';
        if(!text)start=t.along;
        text+=t.text;end=t.along+t.width;previous=t;
      }
      flush();
    }
  }
  return joinCalloutLines(result);
}
