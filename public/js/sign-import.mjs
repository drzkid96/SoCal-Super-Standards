import { makeCatalog, pdfLines, pdfSheetLabel, pastedPages, scanLines } from './sign-import-parser.mjs';

const assets = new URL('../', import.meta.url);
const pdfHome = new URL('vendor/pdfjs-5.6.205/',assets);
const mount = document.getElementById('sign-import-root');
const make = (tag, label, cls) => { const el=document.createElement(tag); if(label)el.textContent=label;if(cls)el.className=cls;return el; };
function button(label,click,cls) { const el=make('button',label,cls);el.type='button';el.onclick=click;return el; }
function labeled(el,label) { const wrapper=make('label',label,'si-label');wrapper.append(el);return wrapper; }
const hex = bytes => Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');
async function fingerprint(bytes) {return hex(await crypto.subtle.digest('SHA-256',bytes));}
let library;
async function pdfJs() {
  const js=await import(new URL('pdf.min.mjs',pdfHome).href);
  js.GlobalWorkerOptions.workerSrc=new URL('pdf.worker.min.mjs',pdfHome).href;
  return js;
}
async function catalog() {
  if(!library)library=fetch(new URL('data/sign-block-options.json',assets)).then(async res=>{
    if(!res.ok)throw Error('The sign catalog could not be opened.');
    return makeCatalog(await res.json());
  }).catch(err=>{library=null;throw err;});
  return library;
}
function init(root) {
  root.className='sign-import';
  if(!root.hasAttribute('data-auto-import'))root.append(make('h2','Import sign callouts'));
  root.append(make('p','Open a plan or paste its sign designations. Files stay in this browser. Review each sheet before adding DWGs.'));
  const sources=make('div','','si-sources'),fileBox=make('div','','si-input'),pasteBox=make('div','','si-input');
  const file=make('input');file.type='file';file.accept='.pdf,application/pdf';file.id='sign-import-file';
  const fileLabel=make('label','Plan PDF','si-label');fileLabel.htmlFor=file.id;
  fileBox.append(fileLabel,file,make('p','Sheet boundaries follow the PDF pages.','si-meta'));
  const raw=make('textarea');raw.id='sign-import-text';raw.rows=3;raw.placeholder='SHEET: SS-1\nR1-1, W16-7P(R)\nSHEET: SS-2\nW48(2)(CA)';
  const rawLabel=make('label','Paste callouts','si-label');rawLabel.htmlFor=raw.id;
  const examine=button('Review pasted text',()=>analyze(null,raw.value),'si-primary');
  pasteBox.append(rawLabel,raw,make('p','Start each sheet with SHEET: and its identifier, or use a form feed.','si-meta'),examine);
  sources.append(fileBox,pasteBox);root.append(sources);
  const status=make('p');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const review=make('div','','si-review');root.append(status,review);
  const state={serial:0,pdf:null,sheets:[],hash:'',documentName:'',ocrTask:null};
  let effects=[],selectionInfo=null,commit=null;
  file.onchange=()=>{if(file.files[0])analyze(file.files[0],null);};
  async function analyze(pdfFile,text) {
    if(!pdfFile&&!text?.trim()){status.textContent='Paste at least one sheet of callouts.';return;}
    const version=++state.serial;
    effects.forEach(fn=>fn());effects=[];review.replaceChildren();status.textContent='Reading the sign catalog…';
    const old=state.pdf;state.pdf=null;state.sheets=[];selectionInfo=null;commit=null;
    if(old)await old.destroy().catch(()=>{});
    try{
      const index=await catalog();if(version!==state.serial)return;
      const bytes=pdfFile?new Uint8Array(await pdfFile.arrayBuffer()):new TextEncoder().encode(text);
      const signature=await fingerprint(bytes);if(version!==state.serial)return;
      let pages=[],pdf=null;
      if(pdfFile){
        status.textContent='Opening '+pdfFile.name+'…';
        const js=await pdfJs();
        const job=js.getDocument({data:bytes,isEvalSupported:false,enableXfa:false,wasmUrl:new URL('wasm/',pdfHome).href,cMapUrl:new URL('cmaps/',pdfHome).href,cMapPacked:true,standardFontDataUrl:new URL('standard_fonts/',pdfHome).href});
        pdf=await job.promise;
        if(version!==state.serial){await pdf.destroy();return;}
        state.pdf=pdf;
        const labels=await pdf.getPageLabels().catch(()=>null);
        for(let n=1;n<=pdf.numPages;n++){
          if(version!==state.serial)return;
          status.textContent='Reading sheet '+n+' of '+pdf.numPages+'…';
          const page=await pdf.getPage(n);
          let lines=[],issue='';
          try {
            lines=pdfLines((await page.getTextContent()).items);
            const annotations=await page.getAnnotations({intent:'display'}).catch(()=>[]);
            for(const a of annotations){
              const title=a.titleObj?.str||a.title||'';
              if(/AutoCAD SHX Text/i.test(title)&&a.contentsObj?.str)lines.push(...a.contentsObj.str.split(/\r?\n/));
            }
          } catch {issue='The PDF text layer could not be read on this page.';}
          const sourceId=lines.map(s=>s.match(/^\s*(?:SHEET(?:\s+(?:NO\.?|NUMBER|ID))?\s*[:#]\s*)([A-Z]{1,5}[- ]?\d{1,4}(?:\.\d+)?)\s*$/i)?.[1]).find(Boolean);
          const sourceLabel=labels?.[n-1]||'';
          const label=sourceId||pdfSheetLabel(sourceLabel,n);
          pages.push({label,sourceLabel,lines,issue});page.cleanup();
        }
      }else pages=pastedPages(text);
      if(version!==state.serial)return;
      state.hash=signature;state.documentName=pdfFile?.name||'Pasted callouts';
      state.sheets=pages.map((p,i)=>({...p,number:i+1,records:scanLines(p.lines,index),ocr:false,manual:''}));
      draw(index,version);
      status.textContent='Read '+state.sheets.length+' sheet'+(state.sheets.length===1?'':'s')+' from '+state.documentName+'.';
    }catch(e){if(version===state.serial)status.textContent=e.name==='PasswordException'?'This PDF is password-protected. Open an unlocked copy or paste its callouts.':'Could not read the plan. '+(e.message||'Use an unlocked PDF or paste its callouts.');}
  }
  function summary(sheet) {
    const counts={matched:0,ambiguous:0,unmatched:0};sheet.records.forEach(r=>counts[r.status]++);
    return sheet.label+' · '+counts.matched+' exact · '+counts.ambiguous+' to choose · '+counts.unmatched+' unmatched';
  }
  function updateTotals(){
    if(!selectionInfo)return;
    let sheets=0,placements=0;const drawings=new Set();
    for(const s of state.sheets){
      const unique=new Set(s.records.map(r=>r.selected).filter(Boolean));
      if(unique.size)sheets++;
      placements+=unique.size;unique.forEach(id=>drawings.add(id));
    }
    selectionInfo.textContent=placements+' selected sheet placement'+(placements===1?'':'s')+' · '+drawings.size+' distinct DWG'+(drawings.size===1?'':'s')+' · '+sheets+' sheet'+(sheets===1?'':'s');
    commit.disabled=placements===0;
  }
  function options(node,record) {
    const holder=make('div');
    let selectChoice;
    if(!record.choices.length){holder.append(make('span','No matching native block','si-meta'));}
    else if(record.choices.length===1){
      const choice=record.choices[0],label=make('label'),box=make('input');box.type='checkbox';box.checked=Boolean(record.selected);
      box.onchange=()=>{record.selected=box.checked?choice.id:'';updateTotals();};
      selectChoice=id=>{record.selected=id;box.checked=Boolean(id);updateTotals();};
      label.append(box,document.createTextNode(choice.code+' · '+choice.sizeLabel+' · '+choice.variant));holder.append(label);
    }else{
      const input=make('select');input.setAttribute('aria-label','Choose block for '+record.raw);
      input.add(new Option('Choose exact artwork and size',''));
      for(const c of record.choices)input.add(new Option(c.code+' · '+c.sizeLabel+' · '+c.variant+' · '+c.id,c.id));
      input.value=record.selected;input.onchange=()=>{record.selected=input.value;updateTotals();};holder.append(input);
      selectChoice=id=>{record.selected=id;input.value=id;updateTotals();};
    }
    if(record.choices.length){
      const faces=make('details');faces.append(make('summary',record.choices.length>1?'Compare '+record.choices.length+' sign faces':'Preview sign face'));
      faces.addEventListener('toggle',()=>{
        if(!faces.open||faces.querySelector('.si-faces'))return;
        const grid=make('div','','si-faces');
        for(const c of record.choices){
          const tile=make('div');
          if(c.preview){const img=make('img');img.loading='lazy';img.src=new URL(c.preview.replace(/^\//,''),assets).href;img.alt=c.code+' · '+c.variant;tile.append(img);}
          tile.append(make('span',c.code+' · '+c.sizeLabel,'si-meta'),make('span',c.variant,'si-meta'));
          const choose=button('Use this face',()=>{selectChoice(c.id);faces.open=false;});choose.setAttribute('aria-label','Use '+c.code+' '+c.variant+' '+c.id);tile.append(choose);grid.append(tile);
        }
        faces.append(grid);
      });holder.append(faces);
    }
    const evidence=make('details');evidence.append(make('summary','Source text'),make('p',record.evidence,'si-meta'));
    holder.append(evidence);node.append(holder);
  }
  function draw(index,version) {
    effects.forEach(fn=>fn());effects=[];review.replaceChildren();
    review.append(make('h2','Review by sheet'));
    const footer=make('div','','si-buttons');selectionInfo=make('span','','si-meta');
    commit=button('Add selected DWGs',async()=>{
      commit.disabled=true;
      try {
        const groups=state.sheets.map(s=>({sheetId:'plan-'+state.hash+'-p'+s.number,label:s.label.trim()||'Sheet '+s.number,records:[...new Set(s.records.map(r=>r.selected).filter(Boolean))]})).filter(x=>x.records.length);
        if(!window.SSSSignCart?.importGroups)throw Error('The drawing selection is unavailable. Reload this page and try again.');
        await window.SSSSignCart.importGroups(groups,{mode:'merge',open:true});status.textContent='Added the reviewed drawings to '+groups.length+' sheet group'+(groups.length===1?'':'s')+'.';
      }catch(e){status.textContent=e.message;}finally{updateTotals();}
    },'si-primary');
    footer.append(commit,selectionInfo);review.append(footer);
    for(const sheet of state.sheets){
      const section=make('details','','si-sheet'),head=make('summary',summary(sheet));section.append(head);
      section.open=sheet.number===1;
      const name=make('input');name.value=sheet.label;name.maxLength=100;name.setAttribute('aria-label','Sheet label for page '+sheet.number);
      name.oninput=()=>{sheet.label=name.value;head.textContent=summary(sheet);};
      const label=make('label','Sheet identifier ');label.append(name);
      const printed=sheet.sourceLabel && sheet.sourceLabel!==sheet.label?' · PDF label '+sheet.sourceLabel:'';
      section.append(label,make('p','Source page '+sheet.number+printed+' · '+sheet.lines.length+' text line'+(sheet.lines.length===1?'':'s'), 'si-meta'));
      if(sheet.issue)section.append(make('p',sheet.issue));
      if(!sheet.records.length){
        section.append(make('p',sheet.lines.length?'The text layer contains no recognized sign callouts. Plotted outlines or scans may still show signs.':'No machine-readable text on this sheet. Paste its callouts or read a selected area with OCR.'));
      }
      if(sheet.ocr)section.append(make('p','OCR proposals require confirmation against the sheet.','si-meta'));
      for(const record of sheet.records){
        const row=make('div','','si-row');row.dataset.match=record.status;row.dataset.key=record.key;
        const left=make('div');left.append(make('strong',record.raw),make('div',record.count+' occurrence'+(record.count===1?'':'s')+' · '+({matched:'Exact designation',ambiguous:'Choose a block',unmatched:'Unmatched'}[record.status]),'si-meta'));row.append(left);options(row,record);section.append(row);
      }
      const edit=make('details');edit.append(make('summary','Add or correct callouts for this sheet'));
      const correction=make('textarea');correction.value=sheet.manual;correction.setAttribute('aria-label','Additional callouts for '+sheet.label);
      edit.append(correction,button('Apply sheet text',()=>{
        sheet.manual=correction.value;
        const previous=new Map(sheet.records.map(r=>[r.key,r.selected]));
        sheet.records=combined(sheet,index);
        for(const r of sheet.records)if(previous.has(r.key)&&r.choices.some(c=>c.id===previous.get(r.key)))r.selected=previous.get(r.key);
        renderAgain(index,version,sheet.number);
      }));section.append(edit);
      if(state.pdf){const tools=make('div','','si-tools');
        tools.append(button('Read a selected area (OCR)',async()=>{
          tools.replaceChildren(make('span','Opening sheet preview…'));
          try{
            const {openCrop}=await import('./sign-import-ocr.mjs');
            if(version!==state.serial)return;
            const dispose=await openCrop(tools,state.pdf,sheet.number,lines=>{
              sheet.ocr=true;sheet.ocrLines=[...new Set([...(sheet.ocrLines||[]),...lines])];
              const prior=new Map(sheet.records.map(r=>[r.key,r.selected]));
              sheet.records=combined(sheet,index);
              for(const row of sheet.records)if(prior.has(row.key))row.selected=prior.get(row.key);
              renderAgain(index,version,sheet.number);
            });
            if(version===state.serial)effects.push(dispose);else dispose();
          }catch(e){tools.replaceChildren(make('p','Could not open OCR. '+e.message));}
        }));section.append(tools);
      }
      review.append(section);
    }
    updateTotals();
  }
  function combined(sheet,index){
    const rows=scanLines([...sheet.lines,...sheet.manual.split(/\n/)],index),byKey=new Map(rows.map(r=>[r.key,r]));
    for(const o of scanLines(sheet.ocrLines||[],index)){
      const hit=byKey.get(o.key);
      if(!hit){o.selected='';o.evidence='OCR · '+o.evidence;rows.push(o);}
    }
    return rows;
  }
  function renderAgain(index,version,page){
    draw(index,version);
    const rows=review.querySelectorAll('.si-sheet');rows[page-1].open=true;
  }
}
if(mount)init(mount);
