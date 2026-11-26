import { joinCalloutLines } from './sign-import-parser.mjs';

const vendor=new URL('../vendor/sign-ocr-7.0.0/',import.meta.url);
const el=(tag,text='')=>{const node=document.createElement(tag);node.textContent=text;return node;};
const cap=(n,min,max)=>Math.max(min,Math.min(max,n));
const signLayer=/(?:signs?[-_ ]*(?:text|notes?|callouts?)|(?:text|notes?|callouts?)[-_ ]*signs?)/i;

export async function openCrop(host,doc,pageNumber,onRead){
  host.replaceChildren();
  const panel=el('div'),msg=el('p','Drag over a sign legend or callout. You can also enter its bounds as percentages of the sheet.');host.append(panel);panel.append(msg);
  const page=await doc.getPage(pageNumber);
  const base=page.getViewport({scale:1});
  const layerBox=el('label'),layers=el('input');layers.type='checkbox';
  const initialConfig=await doc.getOptionalContentConfig({intent:'display'});
  const entries=[...initialConfig];const potential=entries.filter(([,g])=>signLayer.test(g.name));
  if(potential.length){layerBox.append(layers,document.createTextNode(' Show sign-text drawing layers only'));panel.append(layerBox);}
  const wrapper=el('div');wrapper.className='si-crop';const canvas=el('canvas'),rect=el('span');rect.className='si-rect';wrapper.append(canvas,rect);panel.append(wrapper);
  const bounds=[0,0,100,100],inputs=[];
  const fields=el('div');fields.className='si-bounds';
  const readout=el('p');readout.setAttribute('role','status');readout.setAttribute('aria-live','polite');
  const previewText=el('textarea');previewText.rows=4;previewText.setAttribute('aria-label','Review OCR text');previewText.hidden=true;
  const accept=el('button','Use reviewed OCR text');accept.type='button';accept.hidden=true;
  accept.onclick=()=>onRead(previewText.value.split(/\r?\n/));
  const run=el('button','Read area on this device');run.type='button';
  const note=el('p','OCR proposes text. Compare it with the sheet before selecting a drawing.');note.className='si-meta';
  panel.append(fields,note,run,readout,previewText,accept);
  let active=true,renderTask=null,engine=null,running=false;
  async function config(){
    const cfg=await doc.getOptionalContentConfig({intent:'display'});
    if(layers.checked)for(const [id,g] of cfg)cfg.setVisibility(id,signLayer.test(g.name),false);
    return cfg;
  }
  function setBounds(values) {
    bounds[0]=cap(values[0],0,99.5);bounds[1]=cap(values[1],0,99.5);
    bounds[2]=cap(values[2],bounds[0]+.5,100);bounds[3]=cap(values[3],bounds[1]+.5,100);
    inputs.forEach((v,i)=>{v.value=bounds[i].toFixed(1);});
    Object.assign(rect.style,{left:bounds[0]+'%',top:bounds[1]+'%',width:(bounds[2]-bounds[0])+'%',height:(bounds[3]-bounds[1])+'%'});
  }
  ['Left %','Top %','Right %','Bottom %'].forEach((name,i)=>{
    const label=el('label',name),input=el('input');input.type='number';input.min='0';input.max='100';input.step='.1';
    input.onchange=()=>{const values=[...bounds];values[i]=Number(input.value);if(Number.isFinite(values[i]))setBounds(values);};
    label.append(input);fields.append(label);inputs.push(input);
  });
  setBounds(bounds);
  let first=null;
  const point=evt=>{const box=canvas.getBoundingClientRect();return [cap(100*(evt.clientX-box.left)/box.width,0,100),cap(100*(evt.clientY-box.top)/box.height,0,100)];};
  wrapper.onpointerdown=e=>{if(running)return;first=point(e);wrapper.setPointerCapture(e.pointerId);};
  function drag(e){if(!first)return;const [x,y]=point(e);setBounds([Math.min(x,first[0]),Math.min(y,first[1]),Math.max(x,first[0]),Math.max(y,first[1])]);}
  wrapper.onpointermove=drag;wrapper.onpointerup=e=>{drag(e);first=null;};wrapper.onpointercancel=()=>{first=null;};
  async function preview(){
    if(renderTask){renderTask.cancel();try{await renderTask.promise;}catch{}}
    const cfg=await config();if(!active)return;
    const view=page.getViewport({scale:Math.min(1,1000/Math.max(base.width,base.height))});
    canvas.width=Math.ceil(view.width);canvas.height=Math.ceil(view.height);
    renderTask=page.render({canvasContext:canvas.getContext('2d'),viewport:view,optionalContentConfigPromise:Promise.resolve(cfg)});
    try{await renderTask.promise;}catch(e){if(e.name!=='RenderingCancelledException')throw e;}
  }
  layers.onchange=()=>preview().catch(e=>{readout.textContent='Preview unavailable. '+e.message;});
  run.onclick=async()=>{
    run.disabled=true;layers.disabled=true;running=true;accept.hidden=true;
    let surface;
    try{
      readout.textContent='Preparing the selected area…';
      const w=base.width*(bounds[2]-bounds[0])/100,h=base.height*(bounds[3]-bounds[1])/100;
      const scale=Math.min(3.2,3800/Math.max(w,h),Math.sqrt(6e6/(w*h)));
      const view=page.getViewport({scale});surface=el('canvas');surface.width=Math.ceil(w*scale);surface.height=Math.ceil(h*scale);
      const cfg=await config();if(!active)return;
      await page.render({canvasContext:surface.getContext('2d'),viewport:view,transform:[1,0,0,1,-view.width*bounds[0]/100,-view.height*bounds[1]/100],optionalContentConfigPromise:Promise.resolve(cfg)}).promise;
      if(!active)return;
      const {default:T}=await import(new URL('tesseract.mjs',vendor).href);
      engine=await T.createWorker('eng',1,{workerPath:new URL('worker.min.js',vendor).href,workerBlobURL:false,corePath:new URL('tesseract-core-lstm.js',vendor).href,langPath:vendor.href,gzip:true,
        logger:m=>{if(active)readout.textContent=m.status+' '+Math.round((m.progress||0)*100)+'%';}});
      if(!active)return;
      await engine.setParameters({tessedit_pageseg_mode:'11',preserve_interword_spaces:'1'});
      const result=await engine.recognize(surface,{}, {text:true,blocks:true});
      if(!active)return;
      const positions=(result.data.blocks||[]).flatMap(block=>block.paragraphs.flatMap(p=>p.lines.map(line=>({
        text:line.text.trim(),left:line.bbox.x0,right:line.bbox.x1,baseline:-line.bbox.y1,height:line.bbox.y1-line.bbox.y0,turn:0,
      }))));
      previewText.hidden=false;previewText.value=positions.length?joinCalloutLines(positions).join('\n'):result.data.text.trim();accept.hidden=!previewText.value;
      readout.textContent=previewText.value?'Review and correct the recognized text below.':'No readable text found. Select a smaller area or paste a callout.';
    }catch(e){if(active)readout.textContent='OCR could not read this area. '+e.message;}
    finally{if(engine){await engine.terminate().catch(()=>{});engine=null;}if(surface)surface.width=surface.height=1;running=false;run.disabled=false;layers.disabled=false;}
  };
  await preview();
  return ()=>{active=false;renderTask?.cancel();if(engine){engine.terminate().catch(()=>{});engine=null;}canvas.width=canvas.height=1;};
}
