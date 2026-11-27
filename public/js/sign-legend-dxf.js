// Sign legend tables. Each sign is one cell block whose base point is the lower-left corner of its table cell,
// with its code as one MTEXT centered under the face. Cell sizes are the measured LADOT plan legend, in plotted inches.
(() => {
  const directory = new URL('../data/cad-sign-entities/', self.location.href);
  const templateURL = new URL('../cad-legend/template.dxf.in', self.location.href);
  const CELL = {width:1.025, height:1.2, faceWidth:0.92, faceHeight:0.86, artX:0.5125, artY:0.745, codeY:0.16, codeHeight:0.095, codeWidth:0.96, advance:0.84};
  const DEFAULT_LAYOUT = {columns:2, rows:14, title:'', scale:40};
  const cadString = text => Array.from(String(text).replace(/[\r\n\t]/g, ' ')).map(ch =>
    ch.charCodeAt(0) > 127 ? Array.from({length:ch.length}, (_,i) => '\\U+' + ch.charCodeAt(i).toString(16).toUpperCase().padStart(4,'0')).join('') : ch
  ).join('');
  const mtextString = text => cadString(String(text).replace(/\\/g,'\\\\').replace(/[{}]/g,c=>'\\'+c).split(/\s+/).filter(Boolean).join(' '));
  const tag = (...pairs) => pairs.join('\n')+'\n';
  const req = async url => {const r=await fetch(url); if(!r.ok)throw Error('Could not load the sign drawing. Please try again.'); return r;};
  const sha256 = async bytes => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)), b=>b.toString(16).padStart(2,'0')).join('');
  const clampInt = (value, low, high, fallback) => {const n=Math.round(Number(value)); return Number.isFinite(n)?Math.max(low,Math.min(high,n)):fallback;};
  function layoutOf(options={}) {
    return {columns:clampInt(options.columns,1,8,DEFAULT_LAYOUT.columns), rows:clampInt(options.rows,1,24,DEFAULT_LAYOUT.rows),
      title:String(options.title||'').replace(/\s+/g,' ').trim().slice(0,80), scale:DEFAULT_LAYOUT.scale};
  }
  // Signs per table follow the chosen columns and rows; long groups continue as numbered tables.
  function tables(groups, options) {
    const {columns,rows,title}=layoutOf(options), size=columns*rows, out=[];
    for (const group of groups) {
      const total=Math.ceil(group.records.length/size);
      for (let part=0; part<total; part++) {
        const name=(title || group.label || 'SIGN LEGEND').toUpperCase();
        out.push({title:name+(total>1?' ('+(part+1)+' OF '+total+')':''), records:group.records.slice(part*size,part*size+size)});
      }
    }
    return out;
  }
  const codeHeight = code => Math.min(CELL.codeHeight, CELL.codeWidth/(CELL.advance*Math.max(String(code).trim().length,1)));
  const fit = ([minX,minY,maxX,maxY]) => {
    const s=Math.min(CELL.faceWidth/(maxX-minX), CELL.faceHeight/(maxY-minY));
    return {s, x:CELL.artX-s*(minX+maxX)/2, y:CELL.artY-s*(minY+maxY)/2};
  };
  async function loadGeometry(records) {
    const index=await (await req(new URL('index.json',directory))).json();
    const definitions=new Map();
    let next=0;
    async function load() {
      while(next<records.length) {
        const r=records[next++], entry=index.records?.[r.id] || index[r.id];
        if(!entry || entry.name!==r.blockName)throw Error('The drawing definition for '+r.code+' changed. Refresh the chart.');
        const response=await req(new URL(encodeURIComponent(r.id)+'.dxf.gz',directory));
        const bytes=new Uint8Array(await response.arrayBuffer());
        if(entry.sha256 && await sha256(bytes)!==entry.sha256)throw Error('The drawing definition for '+r.code+' could not be verified.');
        const text=new TextDecoder().decode(fflate.gunzipSync(bytes));
        definitions.set(r.id,{entry,text});
      }
    }
    await Promise.all(Array.from({length:Math.min(5,records.length)},load));
    return definitions;
  }

  function build(template, records, groups, defs, options) {
    const layout=layoutOf(options), k=layout.scale;
    let next=0x100;
    const handle=()=> (next++).toString(16).toUpperCase();
    const recordParts=[],blockParts=[],model=[];
    const width=CELL.width*k,height=CELL.height*k,tableWidth=width*layout.columns,tableHeight=height*layout.rows,gap=0.4*k;
    const ent=(type,layer,sub,...attrs)=>tag(0,type,5,handle(),330,'17',100,'AcDbEntity',8,layer,100,sub,...attrs);
    const line=(x,y,ex,ey)=>ent('LINE','P-SIGN-TABL','AcDbLine',10,x,20,y,30,0,11,ex,21,ey,31,0);
    const mtext=(value,x,y,size,layer,attachment)=>ent('MTEXT',layer,'AcDbMText',10,x,20,y,30,0,40,size,41,0,71,attachment,72,1,1,mtextString(value),7,'ROMANS');
    const blockRecord=name=>{const bh=handle(); recordParts.push(tag(0,'BLOCK_RECORD',5,bh,330,'9',100,'AcDbSymbolTableRecord',100,'AcDbBlockTableRecord',2,name,340,'0')); return bh;};
    const begin=(name,bh)=>blockParts.push(tag(0,'BLOCK',5,handle(),330,bh,100,'AcDbEntity',8,'0',100,'AcDbBlockBegin',2,name,70,0,10,0,20,0,30,0,3,name,1,''));
    const end=bh=>blockParts.push(tag(0,'ENDBLK',5,handle(),330,bh,100,'AcDbEntity',8,'0',100,'AcDbBlockEnd'));
    const names=new Map();
    for(const rec of records) {
      const {entry,text}=defs.get(rec.id);
      const name=cadString(rec.legendName || entry.name), face=name+'-FACE';
      names.set(rec.id,name);
      // Native face at its original size, nested once so the geometry stays exact.
      let bh=blockRecord(face); begin(face,bh);
      const pairs=text.trimEnd().split(/\r?\n/);
      if(pairs.length%2)throw Error('Incomplete CAD geometry for '+rec.code);
      for(let i=0;i<pairs.length;i+=2){
        const code=Number(pairs[i]), val=pairs[i+1];
        blockParts.push(tag(code,val));
        // Group-code alignment matters: a 0 used as a coordinate is not an entity delimiter.
        if(code===0)blockParts.push(tag(5,handle(),330,bh));
      }
      end(bh);
      // Cell block: base point at the cell's lower-left corner, face fitted inside the cell.
      const {s,x,y}=fit(entry.bounds);
      bh=blockRecord(name); begin(name,bh);
      blockParts.push(tag(0,'INSERT',5,handle(),330,bh,100,'AcDbEntity',8,'0',62,0,100,'AcDbBlockReference',2,face,10,x,20,y,30,0,41,s,42,s,43,s));
      end(bh);
    }
    const list=tables(groups,layout);
    list.forEach((table,n)=>{
      const left=n*(tableWidth+gap);
      for(let x=0;x<=layout.columns;x++)model.push(line(left+x*width,0,left+x*width,tableHeight));
      for(let y=0;y<=layout.rows;y++)model.push(line(left,y*height,left+tableWidth,y*height));
      const titleHeight=Math.min(0.14*k,tableWidth/(Math.max(1,table.title.length)*0.9));
      model.push(mtext(table.title,left+tableWidth/2,tableHeight+0.12*k,titleHeight,'P-SIGN-TITL',8));
      table.records.forEach((rec,slot)=>{
        const cornerX=left+width*(slot%layout.columns), cornerY=tableHeight-height*(Math.floor(slot/layout.columns)+1);
        model.push(ent('INSERT','P-SIGN','AcDbBlockReference',2,names.get(rec.id),10,cornerX,20,cornerY,30,0,41,k,42,k,43,k));
        model.push(mtext(rec.code,cornerX+CELL.artX*k,cornerY+CELL.codeY*k,codeHeight(rec.code)*k,'P-SIGN-TEXT',8));
      });
    });
    const xmax=Math.max(1,list.length)*(tableWidth+gap)-gap, ymax=tableHeight+0.4*k;
    const values={RECORDS:recordParts.join(''),BLOCKS:blockParts.join(''),ENTITIES:model.join(''),NEXT:handle(),COUNT:recordParts.length+2,
      EXTMINX:0,EXTMINY:0,LIMMINX:0,LIMMINY:0,EXTMAXX:xmax,EXTMAXY:ymax,LIMMAXX:xmax,LIMMAXY:ymax,ZERO:0,
      CENTERX:xmax/2,CENTERY:ymax/2,VHEIGHT:Math.max(ymax,xmax/1.34)*1.08};
    return template.replace(/@([A-Z]+)@(\n?)/g,(_,key,newline)=>{
      if(!Object.hasOwn(values,key))throw Error('Unknown drawing template field '+key);
      return String(values[key])+(key==='RECORDS'||key==='BLOCKS'||key==='ENTITIES'?'':newline);
    });
  }
  self.SSSLegendDXF = {build, tables, layoutOf, loadGeometry, fit, codeHeight, CELL, async create(records,groups,options) {
    const [response,defs]=await Promise.all([req(templateURL),loadGeometry(records)]);
    return build(await response.text(),records,groups,defs,options);
  }};
})();
