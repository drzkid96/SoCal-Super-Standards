(() => {
  const base='/SoCal-Super-Standards', article=document.querySelector('.sl-markdown-content');
  if(!article || location.pathname===base+'/' || location.pathname===base+'/search/')return;
  const heading=document.querySelector('h1')?.textContent.trim() || document.title.split('|')[0];
  const manual=location.pathname.includes('/ca-mutcd/')?'Caltrans · California MUTCD 2026':location.pathname.includes('/mutcd/')?'FHWA · MUTCD 11th Edition Revision 1':'';
  const title=manual ? manual+' · '+heading : heading;
  const book=article.querySelector('.book-reader'),operator=article.querySelector('.operator-book');
  const route=location.pathname.replace(base+'/','').replace(/\/$/,'');
  let manifest;
  const hierarchy=()=>manifest ||= fetch(base+'/api/v1/guides.json').then(check).then(r=>r.json());
  function check(r){if(!r.ok)throw Error('Source unavailable ('+r.status+')');return r;}
  const create=(tag,text)=>{const e=document.createElement(tag);if(text)e.textContent=text;return e;};
  const safe=s=>s.normalize('NFKD').replace(/[^\p{Letter}\p{Number}]+/gu,'_').replace(/^_|_$/g,'').slice(0,150).toUpperCase();
  function toolbar(parent){const d=create('div');d.className='reference-actions';parent.append(d);return d;}
  function button(bar,label,fn){const b=create('button',label);b.type='button';bar.append(b);b.onclick=async()=>{b.disabled=true;try{await fn(b);b.textContent=label.startsWith('Copy')?'Copied':'Done';}catch(e){b.textContent='Retry · '+label;b.title=e.message;}finally{b.disabled=false;setTimeout(()=>b.textContent=label,1800);}};return b;}
  function save(bytes,name,type){const a=create('a'),url=URL.createObjectURL(new Blob([bytes],{type}));a.href=url;a.download=safe(name)+'.pdf';a.click();setTimeout(()=>URL.revokeObjectURL(url),60000);}
  const library=()=>import(base+'/vendor/pdf-lib.esm.min.js');
  async function picture(src){
    const im=new Image();im.src=src;await im.decode();
    const c=document.createElement('canvas'),ratio=Math.min(1,2200/Math.max(im.naturalWidth,im.naturalHeight));c.width=Math.max(1,Math.round(im.naturalWidth*ratio));c.height=Math.max(1,Math.round(im.naturalHeight*ratio));
    const ctx=c.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,c.width,c.height);ctx.drawImage(im,0,0,c.width,c.height);return c;
  }
  const bytes=(canvas,type)=>new Promise((ok,fail)=>canvas.toBlob(x=>x?ok(x):fail(Error('Image export failed')),type,.91));
  function copyImage(src){const png=picture(src).then(c=>bytes(c,'image/png'));return navigator.clipboard.write([new ClipboardItem({'image/png':png})]);}
  async function imagePage(pdf,src){const c=await picture(src),data=await bytes(c,'image/jpeg'),img=await pdf.embedJpg(await data.arrayBuffer());const scale=792/Math.max(c.width,c.height);pdf.addPage([c.width*scale,c.height*scale]).drawImage(img,{x:0,y:0,width:c.width*scale,height:c.height*scale});}
  async function single(src,name){const pdf=await (await library()).PDFDocument.create();await imagePage(pdf,src);save(await pdf.save(),name,'application/pdf');}
  const publisher=article.querySelector('.reg-credit a')?.href || (operator?article.querySelector('a[href^="https://"]')?.href:null);
  const citation=(label,url)=>[label,...(publisher?['Publisher '+publisher]:[]),'SoCal Super Standards','Accessed '+new Date().toISOString().slice(0,10),url].join('. ');
  function figureTools(fig,i){
    const im=fig.querySelector('img');if(!im||fig.querySelector('.reference-actions'))return;
    const orig=im.closest('a')?.href;const src=orig&&/\.(webp|avif|png|jpe?g|svg)(?:\?|$)/i.test(orig)?orig:im.src;
    if(!src)return;
    const parent=fig.closest('[data-chapter-url]');
    fig.id ||= 'ref-figure-'+(i+1);
    const addr=new URL(parent?.dataset.chapterUrl||location.href,location.origin);addr.hash=fig.id;
    const label=fig.querySelector('figcaption')?.textContent.trim()||im.alt||'Figure '+(i+1),bar=toolbar(fig);
    button(bar,'Copy image',()=>copyImage(src));button(bar,'Copy citation',()=>navigator.clipboard.writeText(citation(title+' · '+label,addr.href)));
    button(bar,'Sheet PDF',()=>single(src,title+' '+label));
  }
  function enhance(root){root.querySelectorAll('figure:not(.vibe-hero)').forEach(figureTools);}
  const top=toolbar(article);article.prepend(top);
  async function fetchArticle(path){const r=await fetch(base+'/'+path+'/');return new DOMParser().parseFromString(await check(r).text(),'text/html').querySelector('.sl-markdown-content');}
  async function continuous(){
    const chapters=(await hierarchy())[book.dataset.book]||[];if(!chapters.length)return;
    const id=book.dataset.book;const wrapper=create('div'),pick=create('select');pick.ariaLabel='Chapter';chapters.forEach(([label,path])=>pick.add(new Option(label,path)));
    book.replaceChildren(pick);article.replaceChildren(book,wrapper);
    let index=0,loading=false,serial=0;
    async function next(reset=false){
      if(!reset&&loading)return;
      if(reset){serial++;wrapper.replaceChildren();index=pick.selectedIndex;}const epoch=serial,at=index;if(at>=chapters.length)return;
      loading=true;more.disabled=true;const [name,path]=chapters[at];
      try{const original=await fetchArticle(path);if(!original||epoch!==serial)return;
        original.querySelectorAll('.book-reader,.reference-actions,[data-pagefind-filter]').forEach(el=>el.remove());
        const section=create('section');section.dataset.chapterUrl=base+'/'+path+'/';section.className='continuous-chapter';
        const h=create('h2'),a=create('a',name);a.href=base+'/'+path+'/';h.append(a);section.append(h);
        original.querySelectorAll('a[href^="#"]').forEach(a=>a.href=base+'/'+path+'/'+a.getAttribute('href'));
        original.querySelectorAll('[id]').forEach(el=>el.id=path.replaceAll('/','-')+'-'+el.id);
        section.append(...original.childNodes);wrapper.append(section);index++;enhance(section);
        more.hidden=index>=chapters.length;
      }finally{if(epoch===serial){loading=false;more.disabled=false;}}
    }
    const more=create('button','Read next chapter');more.onclick=()=>next();article.append(more);pick.onchange=()=>next(true);await next();
    if('IntersectionObserver' in window)new IntersectionObserver(es=>{if(es[0].isIntersecting&&!more.hidden)next();},{rootMargin:'300px'}).observe(more);
  }
  function clean(root){const n=root.cloneNode(true);n.querySelectorAll('script,style,nav,button,select,input,.reference-actions,.book-reader,.sec-toc,.reg-controls,.reg-contact,.export-tools,.operator-book,[data-pagefind-filter]').forEach(e=>e.remove());return n;}
  // Reflow the article text into printable pages, preserving headings, figure order and table rows.
  async function addArticle(pdf,root,heading){
    const n=clean(root),c=document.createElement('canvas');c.width=1200;c.height=1553;const ctx=c.getContext('2d');let y=0;
    function clear(){ctx.fillStyle='white';ctx.fillRect(0,0,c.width,c.height);ctx.fillStyle='#172727';y=65;}
    async function flush(){if(y<=65)return;const im=await pdf.embedJpg(await (await bytes(c,'image/jpeg')).arrayBuffer());pdf.addPage([612,792]).drawImage(im,{x:0,y:0,width:612,height:792});clear();}
    async function lines(str,bold=false){ctx.font=(bold?'bold 29':'23')+'px sans-serif';let row='';
      for(const word of str.replace(/\s+/g,' ').trim().split(' ')){if(row&&ctx.measureText(row+' '+word).width>1060){if(y>1460)await flush();ctx.fillText(row,65,y);y+=34;row='';}row+=(row?' ':'')+word;}
      if(row){if(y>1460)await flush();ctx.fillText(row,65,y);y+=44;}}
    clear();await lines(heading,true);
    async function visit(el){if(el.nodeType===3){if(el.textContent.trim())await lines(el.textContent);return;}
      if(el.tagName==='IMG'){const src=el.getAttribute('data-full-scan')||el.getAttribute('src');if(src){await flush();await imagePage(pdf,new URL(src,location.origin).href);}return;}
      if(el.tagName==='TR'){await lines([...el.children].map(td=>td.textContent.trim()).join('   |   '));return;}
      if(!el.querySelector('img,p,li,div,table,section,h1,h2,h3,h4,details,figure') && el.tagName!=='TABLE'){if(el.textContent.trim())await lines(el.textContent,/^H[1-6]$/.test(el.tagName));return;}
      for(const child of el.childNodes)await visit(child);}
    for(const el of n.childNodes)await visit(el);await flush();
  }
  async function exportDocs(all=false,section){
    const pdf=await (await library()).PDFDocument.create();let name=title;
    if(section){name=title+' '+section.label;await addArticle(pdf,section.node,name);}
    else if(all&&book){name=manual||book.dataset.book.replaceAll('/',' ');const list=(await hierarchy())[book.dataset.book];for(const [label,path] of list)await addArticle(pdf,await fetchArticle(path),label);}
    else await addArticle(pdf,article,title);
    save(await pdf.save(),name,'application/pdf');
  }
  if(operator){
    const field=operator.querySelector('input'),frame=operator.querySelector('img'),limit=Number(operator.dataset.count);
    const page=()=>Math.max(1,Math.min(limit,Number(field.value)||1));
    const show=()=>{let m=location.hash.match(/^#page-(\d+)$/);field.value=m?Math.min(limit,Number(m[1])):1;frame.src=operator.dataset.images+page()+'.webp';operator.querySelector('[data-turn="-1"]').disabled=page()===1;operator.querySelector('[data-turn="1"]').disabled=page()===limit;};
    field.onchange=()=>location.hash='page-'+page();operator.querySelectorAll('[data-turn]').forEach(b=>b.onclick=()=>location.hash='page-'+(page()+Number(b.dataset.turn)));
    article.querySelectorAll('a[href^="#page-"]').forEach(a=>a.onclick=e=>{e.preventDefault();history.pushState(null,'',a.hash);show();operator.scrollIntoView();});
    window.addEventListener('hashchange',show);show();
    button(top,'Copy image',()=>copyImage(frame.src));
    let src;const original=()=>src ||= fetch(operator.dataset.pdf).then(check).then(r=>r.arrayBuffer());
    button(top,'Chapter PDF',async()=>{
      const starts=operator.dataset.sections.split(',').map(Number),first=starts.filter(n=>n<=page()).at(-1)||1,last=(starts.find(n=>n>page())||limit+1)-1;
      const {PDFDocument}=await library(),dest=await PDFDocument.create(),source=await PDFDocument.load(await original());
      for(const sheet of await dest.copyPages(source,Array.from({length:last-first+1},(_,i)=>first+i-1)))dest.addPage(sheet);
      save(await dest.save(),title+' PAGES '+first+' TO '+last,'application/pdf');});
    button(top,'Guide PDF',async()=>save(await original(),title,'application/pdf'));
    button(top,'Page PDF',async()=>{const {PDFDocument}=await library(),dest=await PDFDocument.create(),source=await PDFDocument.load(await original());const [p]=await dest.copyPages(source,[page()-1]);dest.addPage(p);save(await dest.save(),title+' PAGE '+page(),'application/pdf');});
  }else if(article.querySelector('.reg-scan')){
    const current=()=>article.querySelector('.reg-page:not([hidden]) .reg-scan');
    button(top,'Copy image',()=>copyImage(current().href));button(top,'Page PDF',()=>single(current().href,current().dataset.title));
    button(top,'Guide PDF',async()=>{const pdf=await (await library()).PDFDocument.create();for(const scan of article.querySelectorAll('.reg-scan'))await imagePage(pdf,scan.href);save(await pdf.save(),title,'application/pdf');});
  }else{
    button(top,book&&route!==book.dataset.book?'Chapter PDF':'Page PDF',()=>exportDocs());
    if(book)button(top,'Guide PDF',()=>exportDocs(true));
    for(const h of article.querySelectorAll('h2')){if(!/^\d[A-Z]\.\d+/.test(h.textContent.trim()))continue;
      const anchor=h.closest('.sl-heading-wrapper')||h;const b=toolbar(anchor.parentElement);anchor.after(b);
      button(b,'Copy section citation',()=>{const link=new URL(location.pathname,location.origin);link.hash=anchor.previousElementSibling?.matches('.anchor')?anchor.previousElementSibling.id:h.id;return navigator.clipboard.writeText(citation(title+' · '+h.textContent,link.href));});
      button(b,'Section PDF',()=>{const node=create('div');for(let e=b.nextElementSibling;e&&!e.matches('h2,.anchor,.sl-heading-wrapper:has(h2)');e=e.nextElementSibling)node.append(e.cloneNode(true));return exportDocs(false,{label:h.textContent,node});});}
    enhance(article);
  }
  button(top,'Copy citation',()=>navigator.clipboard.writeText(citation(title+(operator?' · page '+operator.querySelector('input').value:''),location.href)));
  if(location.hash.startsWith('#ref-figure-'))document.getElementById(location.hash.slice(1))?.scrollIntoView();
  if(book && new URL(location.href).searchParams.get('read')==='1')continuous().then(()=>article.prepend(top));
})();
