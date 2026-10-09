// One camera implementation for inline/modal viewing. Never inject SVG markup;
// source and captions belong to the document, camera state to this page only.
(() => {
  'use strict';
  function start() {
    const entries = [...document.querySelectorAll('a.askr-image-entry')].map(anchor => ({
      anchor, src:anchor.href, alt:anchor.querySelector('img')?.alt || '',
      caption:anchor.closest('.quarto-figure,figure')?.querySelector('figcaption')?.textContent || anchor.title || '',
      description:anchor.dataset.askrDescription || '', group:anchor.dataset.askrGallery
    }));
    if (!entries.length) return;
    const loop = document.querySelector('#askr-viewer-config')?.dataset.loop !== 'false';
    function resolve(id) {
      const el = document.getElementById(id);
      const anchor = el?.closest('.askr-image-entry') || el?.querySelector('.askr-image-entry');
      return entries.find(e => e.anchor === anchor);
    }
    const dialog = document.createElement('dialog'); dialog.className='askr-viewer-dialog';
    dialog.setAttribute('aria-label','Image viewer'); document.body.append(dialog);
    let active=null, trigger=null, home=null, group=[], index=0, scroll=0, overflow='', backdrop=false;
    function button(label,text,action) {
      const b=document.createElement('button'); b.type='button'; b.title=label;
      b.setAttribute('aria-label',label); b.textContent=text; b.addEventListener('click',action); return b;
    }
    class Viewer {
      constructor(entry,label) {
        this.entry=entry; this.ratio=1; this.cx=this.cy=.5; this.points=new Map(); this.loaded=false; this.ticket=0;
        this.root=document.createElement('section'); this.root.className='askr-viewer';
        this.root.setAttribute('aria-label',label || 'Interactive image viewer');
        this.toolbar=document.createElement('div'); this.toolbar.className='askr-viewer-toolbar';
        this.percent=document.createElement('output'); this.percent.setAttribute('aria-label','Zoom relative to Fit');
        this.out=button('Zoom out','−',()=>this.zoom(1/1.25)); this.in=button('Zoom in','+',()=>this.zoom(1.25));
        this.fitButton=button('Fit image','Fit',()=>this.fit());
        this.expand=button('Expand image viewer','↗',()=>open(this.entry,this.expand,this));
        this.full=button('Toggle fullscreen','⛶',async()=>{
          try { if(document.fullscreenElement) await document.exitFullscreen(); else await this.root.requestFullscreen(); }
          catch(e) { this.status.textContent=`Fullscreen unavailable: ${e.message}`; }
        });
        this.closeButton=button('Close image viewer','×',()=>close());
        this.toolbar.append(this.out,this.in,this.fitButton,this.percent,this.expand,this.full,this.closeButton);
        this.stage=document.createElement('div'); this.stage.className='askr-viewer-stage'; this.stage.tabIndex=0;
        this.stage.setAttribute('role','region');
        this.stage.setAttribute('aria-label','Image controls: drag to pan; plus or minus to zoom; zero to fit; arrows to pan');
        this.image=document.createElement('img'); this.image.draggable=false;
        this.status=document.createElement('p'); this.status.className='askr-viewer-status'; this.status.setAttribute('role','status');
        this.retry=button('Retry image loading','Retry',()=>this.load(this.entry));
        this.stage.append(this.image,this.status,this.retry);
        this.caption=document.createElement('div'); this.caption.className='askr-viewer-caption';
        this.nav=document.createElement('div'); this.nav.className='askr-viewer-navigation';
        this.prev=button('Previous image','←',()=>change(-1)); this.next=button('Next image','→',()=>change(1));
        this.count=document.createElement('output'); this.count.setAttribute('aria-label','Image in gallery');
        this.nav.append(this.prev,this.count,this.next);
        const hint=document.createElement('p'); hint.className='askr-viewer-hint'; hint.textContent='Drag to pan · + / − to zoom · 0 to fit';
        this.root.append(this.toolbar,this.stage,this.caption,this.nav,hint); this.modal(false);
        this.stage.addEventListener('wheel',e=>{
          if(active!==this && document.activeElement!==this.stage) return;
          e.preventDefault(); const r=this.stage.getBoundingClientRect();
          this.zoom(Math.exp(-e.deltaY*.002),e.clientX-r.left,e.clientY-r.top);
        },{passive:false});
        this.stage.addEventListener('keydown',e=>{
          if(e.target!==this.stage) return;
          if(['+','=','-','0','ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)) e.preventDefault();
          if(e.key==='+'||e.key==='=') this.zoom(1.25); else if(e.key==='-') this.zoom(1/1.25);
          else if(e.key==='0') this.fit();
          else if(e.key.startsWith('Arrow')) this.pan(e.key==='ArrowLeft'?40:e.key==='ArrowRight'?-40:0,e.key==='ArrowUp'?40:e.key==='ArrowDown'?-40:0);
        });
        this.stage.addEventListener('pointerdown',e=>{
          if(e.target.closest('button')||e.button!==0) return;
          this.stage.focus({preventScroll:true}); this.stage.setPointerCapture(e.pointerId);
          this.points.set(e.pointerId,{x:e.clientX,y:e.clientY});
        });
        this.stage.addEventListener('pointermove',e=>{
          if(!this.points.has(e.pointerId)) return;
          const a=[...this.points.values()]; this.points.set(e.pointerId,{x:e.clientX,y:e.clientY}); const b=[...this.points.values()];
          if(a.length===1) this.pan(b[0].x-a[0].x,b[0].y-a[0].y);
          else if(a.length===2) {
            const d=p=>Math.hypot(p[1].x-p[0].x,p[1].y-p[0].y), c=p=>({x:(p[0].x+p[1].x)/2,y:(p[0].y+p[1].y)/2});
            const x=c(a),y=c(b),r=this.stage.getBoundingClientRect();
            if(d(a)) this.zoom(d(b)/d(a),x.x-r.left,x.y-r.top); this.pan(y.x-x.x,y.y-x.y);
          }
        });
        for(const type of ['pointerup','pointercancel','lostpointercapture']) this.stage.addEventListener(type,e=>this.points.delete(e.pointerId));
        this.observer=new ResizeObserver(()=>this.draw()); this.observer.observe(this.stage); this.load(entry);
      }
      modal(on) {
        this.expand.hidden=on; this.full.hidden=!on||!document.fullscreenEnabled||!this.root.requestFullscreen;
        this.closeButton.hidden=!on; this.nav.hidden=!on||group.length<2;
        if(on) { this.count.textContent=`${index+1} / ${group.length}`; this.prev.disabled=!loop&&index===0; this.next.disabled=!loop&&index===group.length-1; }
      }
      load(entry) {
        this.entry=entry; this.loaded=false; this.ratio=1; this.cx=this.cy=.5;
        this.status.textContent='Loading image…'; this.retry.hidden=true; this.image.hidden=true;
        this.in.disabled=this.out.disabled=this.fitButton.disabled=true; this.caption.replaceChildren();
        for(const text of [entry.caption,entry.description]) if(text) { const p=document.createElement('p'); p.textContent=text; this.caption.append(p); }
        this.caption.hidden=!this.caption.childElementCount;
        const ticket=++this.ticket, loader=new Image();
        loader.onload=()=>{
          if(ticket!==this.ticket) return;
          this.nw=loader.naturalWidth; this.nh=loader.naturalHeight; this.image.src=loader.src; this.image.alt=entry.alt || entry.caption;
          this.image.hidden=false; this.loaded=true; this.status.textContent=''; this.retry.hidden=true;
          this.in.disabled=this.out.disabled=this.fitButton.disabled=false; this.draw();
        };
        loader.onerror=()=>{ if(ticket===this.ticket) { this.status.textContent='Unable to load this image.'; this.retry.hidden=false; } };
        loader.src=entry.src;
      }
      dims() { const w=this.stage.clientWidth,h=this.stage.clientHeight; return {w,h,fit:Math.min(w/this.nw,h/this.nh)}; }
      draw() {
        this.percent.textContent=`${Math.round(this.ratio*100)}%`;
        if(!this.loaded||!this.stage.clientWidth||!this.stage.clientHeight) return;
        const {w,h,fit}=this.dims(),s=fit*this.ratio;
        this.image.style.width=`${this.nw}px`; this.image.style.height=`${this.nh}px`;
        this.image.style.transform=`translate(${w/2-this.cx*this.nw*s}px, ${h/2-this.cy*this.nh*s}px) scale(${s})`;
      }
      fit() { this.ratio=1; this.cx=this.cy=.5; this.draw(); }
      pan(dx,dy) { if(!this.loaded) return; const s=this.dims().fit*this.ratio; this.cx-=dx/(this.nw*s); this.cy-=dy/(this.nh*s); this.draw(); }
      zoom(factor,x,y) {
        if(!this.loaded) return; const {w,h,fit}=this.dims(); x??=w/2; y??=h/2;
        const ratio=this.ratio*factor; if(!(ratio>0)||!Number.isFinite(ratio)) return;
        const old=fit*this.ratio,next=fit*ratio;
        this.cx+=(x-w/2)/this.nw*(1/old-1/next); this.cy+=(y-h/2)/this.nh*(1/old-1/next);
        this.ratio=ratio; this.draw();
      }
      destroy() { ++this.ticket; this.observer.disconnect(); this.root.remove(); }
    }
    function open(entry,origin,existing=null) {
      if(dialog.open) return; trigger=origin; scroll=window.scrollY;
      overflow=document.body.style.overflow; document.body.style.overflow='hidden';
      group=existing?[entry]:entry.group?entries.filter(e=>e.group===entry.group):[entry]; index=group.indexOf(entry);
      active=existing||new Viewer(entry);
      if(existing) {
        home=document.createElement('div'); home.setAttribute('aria-hidden','true');
        home.style.height=`${active.root.getBoundingClientRect().height}px`; active.root.before(home);
      }
      dialog.append(active.root); active.modal(true); dialog.showModal(); active.draw(); active.closeButton.focus({preventScroll:true});
    }
    async function close() { if(document.fullscreenElement && dialog.contains(document.fullscreenElement)) await document.exitFullscreen(); if(dialog.open) dialog.close(); }
    dialog.addEventListener('close',()=>{
      if(!active) return; active.points.clear();
      if(home) { home.replaceWith(active.root); home=null; active.modal(false); active.draw(); } else active.destroy();
      active=null; document.body.style.overflow=overflow; window.scrollTo({top:scroll,behavior:'instant'});
      if(trigger?.isConnected) trigger.focus({preventScroll:true}); trigger=null;
    });
    dialog.addEventListener('cancel',e=>{ if(document.fullscreenElement && dialog.contains(document.fullscreenElement)) { e.preventDefault(); document.exitFullscreen(); } });
    dialog.addEventListener('pointerdown',e=>{ backdrop=e.target===dialog; });
    dialog.addEventListener('pointerup',e=>{ if(backdrop&&e.target===dialog) close(); backdrop=false; });
    function change(delta) {
      const next=index+delta; if(!loop&&(next<0||next>=group.length)) return;
      index=(next+group.length)%group.length; active.points.clear(); active.load(group[index]); active.modal(true);
    }
    for(const request of document.querySelectorAll('.askr-inline-request')) {
      const entry=resolve(request.dataset.askrImageTarget); if(!entry) throw new Error('Askr inline viewer target missing.');
      const viewer=new Viewer(entry,request.dataset.label); entry.anchor.hidden=true; entry.anchor.after(viewer.root);
      const originalCaption=entry.anchor.closest('.quarto-figure,figure')?.querySelector('figcaption');
      if(originalCaption) originalCaption.hidden=true;
      entry.anchor.closest('.askr-image-source')?.classList.add('askr-image-source-inline'); request.remove();
    }
    for(const entry of entries) {
      entry.anchor.setAttribute('aria-haspopup','dialog');
      entry.anchor.setAttribute('aria-label',entry.alt || entry.caption || 'View image');
      entry.anchor.addEventListener('click',e=>{ e.preventDefault(); open(entry,entry.anchor); });
    }
    for(const link of document.querySelectorAll('.askr-image-view')) {
      const entry=resolve(link.dataset.askrImageTarget); if(!entry) throw new Error('Askr image button target missing.');
      link.href=entry.src; link.setAttribute('role','button');
      link.addEventListener('click',e=>{ e.preventDefault(); open(entry,link); });
      link.addEventListener('keydown',e=>{ if(e.key===' ') { e.preventDefault(); open(entry,link); } });
    }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',start,{once:true}); else start();
})();
