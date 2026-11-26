// Native sign definitions stay in their original inches. Only their INSERTs are fitted to the legend.
(() => {
  const directory = new URL('../data/cad-sign-entities/', self.location.href);
  const templateURL = new URL('../cad-legend/template.dxf.in', self.location.href);
  const cadString = text => Array.from(String(text).replace(/[\r\n\t]/g, ' ')).map(ch =>
    ch.charCodeAt(0) > 127 ? Array.from({length:ch.length}, (_,i) => '\\U+' + ch.charCodeAt(i).toString(16).toUpperCase().padStart(4,'0')).join('') : ch
  ).join('');
  const tag = (...pairs) => pairs.join('\n')+'\n';
  const req = async url => {const r=await fetch(url); if(!r.ok)throw Error('Could not load the sign drawing. Please try again.'); return r;};
  const sha256 = async bytes => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)), b=>b.toString(16).padStart(2,'0')).join('');
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

  function build(template, records, groups, defs) {
    let next=0x100;
    const handle=()=> (next++).toString(16).toUpperCase();
    const recordParts=[],blockParts=[],model=[];
    const width=41,height=48,tableWidth=width*2,tableHeight=height*14;
    const gap=16,faceHeight=34.4,faceWidth=36.8;
    const ent=(type,layer,sub,...attrs)=>tag(0,type,5,handle(),330,'17',100,'AcDbEntity',8,layer,100,sub,...attrs);
    const line=(x,y,ex,ey)=>ent('LINE','LADOT-LEGEND-GRID','AcDbLine',10,x,20,y,30,0,11,ex,21,ey,31,0);
    const label=(value,x,y,size,layer,alignment=2)=>ent('TEXT',layer,'AcDbText',10,x,20,y,30,0,40,size,1,cadString(value),7,'Standard',72,1,11,x,21,y,31,0,100,'AcDbText',73,alignment);
    const names=new Map();
    for(const rec of records) {
      const {entry,text}=defs.get(rec.id);
      const name=cadString(rec.legendName || entry.name), bh=handle();
      names.set(rec.id,name);
      recordParts.push(tag(0,'BLOCK_RECORD',5,bh,330,'9',100,'AcDbSymbolTableRecord',100,'AcDbBlockTableRecord',2,name,340,'0'));
      blockParts.push(tag(0,'BLOCK',5,handle(),330,bh,100,'AcDbEntity',8,'0',100,'AcDbBlockBegin',2,name,70,0,10,0,20,0,30,0,3,name,1,''));
      // Group-code alignment matters: a 0 used as a coordinate is not an entity delimiter.
      const pairs=text.trimEnd().split(/\r?\n/);
      if(pairs.length%2)throw Error('Incomplete CAD geometry for '+rec.code);
      for(let i=0;i<pairs.length;i+=2){
        const k=Number(pairs[i]), val=pairs[i+1];
        blockParts.push(tag(k,val));
        if(k===0)blockParts.push(tag(5,handle(),330,bh));
      }
      blockParts.push(tag(0,'ENDBLK',5,handle(),330,bh,100,'AcDbEntity',8,'0',100,'AcDbBlockEnd'));
    }
    let tables=0;
    for (const group of groups) {
      const ordered=group.records;
      if(!ordered.length)continue;
      const total=Math.ceil(ordered.length/28);
      for(let part=0;part<total;part++) {
        const left=tables++*(tableWidth+gap);
        for(let x=0;x<=2;x++)model.push(line(left+x*width,0,left+x*width,tableHeight));
        for(let y=0;y<=14;y++)model.push(line(left,y*height,left+tableWidth,y*height));
        const title=(group.label || 'SIGN LEGEND')+(total>1?' ('+(part+1)+' OF '+total+')':'');
        model.push(label(title,left+width,tableHeight+9,Math.min(4.5,tableWidth/(Math.max(1,title.length)*.75)),'LADOT-LEGEND-TITLE'));
        ordered.slice(part*28,part*28+28).forEach((rec,slot)=>{
          const x=left+width*(slot%2+.5), bottom=tableHeight-height*(Math.floor(slot/2)+1);
          const bound=defs.get(rec.id).entry.bounds;
          const [minX,minY,maxX,maxY]=bound;
          const size=Math.min(faceWidth/(maxX-minX),faceHeight/(maxY-minY));
          const insertX=x-size*(minX+maxX)/2, insertY=bottom+29.8-size*(minY+maxY)/2;
          model.push(ent('INSERT','0','AcDbBlockReference',2,names.get(rec.id),10,insertX,20,insertY,30,0,41,size,42,size,43,size));
          const code=rec.code;
          model.push(label(code,x,bottom+6.545,Math.min(3.8052,37/(Math.max(code.length,1)*.66)),'LADOT-LEGEND-CODE',0));
        });
      }
    }
    const xmax=tables*(tableWidth+gap)-gap, ymax=tableHeight+16;
    const values={RECORDS:recordParts.join(''),BLOCKS:blockParts.join(''),ENTITIES:model.join(''),NEXT:handle(),COUNT:records.length+2,
      EXTMINX:0,EXTMINY:0,LIMMINX:0,LIMMINY:0,EXTMAXX:xmax,EXTMAXY:ymax,LIMMAXX:xmax,LIMMAXY:ymax,ZERO:0,
      CENTERX:xmax/2,CENTERY:ymax/2,VHEIGHT:Math.max(ymax,xmax/1.34)*1.08};
    return template.replace(/@([A-Z]+)@(\n?)/g,(_,key,newline)=>{
      if(!Object.hasOwn(values,key))throw Error('Unknown drawing template field '+key);
      return String(values[key])+(key==='RECORDS'||key==='BLOCKS'||key==='ENTITIES'?'':newline);
    });
  }
  self.SSSLegendDXF = {build, async create(records,groups) {
    const [response,defs]=await Promise.all([req(templateURL),loadGeometry(records)]);
    return build(await response.text(),records,groups,defs);
  }};
})();
