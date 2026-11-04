/* checar.js — conferência visual automática da arte (Cunha Law, 04/11/2026)
   Roda DENTRO da página já renderizada (1080x1350). Devolve {ok, falhas[], manchetes[]}.
   Regras medidas (ver REGRAS-DIAGRAMACAO.md):
   H1 nenhuma linha da manchete com 1 palavra só (manchete com 3+ palavras)
   H2 linha não termina em palavra fraca (o, de, para...)
   H3 equilíbrio: linha mais curta >= 60% da mais longa
   H4 preenchimento: linha mais longa >= 85% da largura da caixa de texto
   H5 fonte da manchete >= 96 px (48 px no celular) — abaixo disso, rediagramar
   H6 no máximo 3 linhas na manchete principal
   H7 destaque laranja: 1 trecho (palavra-chave ou a frase do impacto), no máximo 60% das palavras, nunca a manchete inteira
   H8 frase que termina (. ? !) fecha a linha, nunca fica no meio dela
   M1 todo texto dentro das margens: >= 80 px das laterais, >= 96 px da borda de baixo, >= 60 px do topo
   Rosto e foto esticada: não dá para medir com segurança aqui -> conferir olhando a imagem (regra V1 e V2). */
(function(g){
const FRACAS=new Set("o a os as um uma uns umas de da do das dos e em no na nos nas ao aos à às para pra por pelo pela pelos pelas com sem que se ou mas nem".split(" "));
function linhas(el){const ws=[];const tw=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let n;while(n=tw.nextNode()){const re=/\S+/g;let m;while(m=re.exec(n.textContent)){const r=document.createRange();r.setStart(n,m.index);r.setEnd(n,m.index+m[0].length);const b=r.getBoundingClientRect();if(b.width)ws.push({fs:parseFloat(getComputedStyle(n.parentElement).fontSize),w:m[0],l:b.left,r:b.right,t:b.top,h:b.height,em:!!n.parentElement.closest('em')});}}
 const L=[];for(const w of ws){const last=L[L.length-1];if(last&&Math.abs(last.t-w.t)<w.h*0.5){last.ws.push(w);last.r=Math.max(last.r,w.r);last.l=Math.min(last.l,w.l);}else L.push({t:w.t,l:w.l,r:w.r,fs:w.fs,ws:[w]});}L.forEach(x=>x.fs=Math.max(...x.ws.map(w=>w.fs)));return L;}
function caixa(el){let e=el;while(e){const cs=getComputedStyle(e);if(cs.display==='block'||cs.display==='flex'||cs.display==='grid'){const b=e.getBoundingClientRect();const w=b.width-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight);if(w>300)return w;}e=e.parentElement;}return 896;}
function checar(root=document,o={}){
 const minPx=o.minPx??96,maxL=o.maxLinhas??3,falhas=[],manchetes=[];
 const sl=root.querySelector('.sl')||root.body;const S=sl.getBoundingClientRect();
 const hs=[...root.querySelectorAll(o.sel||'.sl h4,[data-headline]')].filter(e=>e.offsetParent!==null&&e.textContent.trim());
 hs.forEach((el,i)=>{const L=linhas(el);if(!L.length)return;const fs=Math.max(...L.map(x=>x.fs));const porFrase=new Set(L.map(x=>Math.round(x.fs))).size>1;const W=Math.min(caixa(el),S.width-160);
  const wid=L.map(x=>x.r-x.l),mx=Math.max(...wid),mn=Math.min(...wid),nw=L.reduce((s,x)=>s+x.ws.length,0);
  const r={texto:L.map(x=>x.ws.map(w=>w.w).join(' ')).join(' / '),px:Math.round(fs),linhas:L.length,preenche:+(mx/W).toFixed(2),equilibrio:+(mn/mx).toFixed(2)};manchetes.push(r);
  const tag='Manchete "'+r.texto+'": ';const sec=i>0||el.dataset.secundaria!==undefined;
  if(nw>=3&&L.some(x=>x.ws.length===1))falhas.push(tag+'H1 palavra sozinha numa linha');
  L.slice(0,-1).forEach(x=>{const w=x.ws[x.ws.length-1].w.toLowerCase().replace(/[^\p{L}]/gu,'');if(FRACAS.has(w))falhas.push(tag+'H2 linha termina em "'+w+'"');});
  L.forEach(x=>x.ws.slice(0,-1).forEach(w=>{if(/[.?!]$/.test(w.w))falhas.push(tag+'H8 frase termina no meio da linha ("'+w.w+'")');}));
  const grupos={};L.forEach(x=>{(grupos[Math.round(x.fs)]=grupos[Math.round(x.fs)]||[]).push(x.r-x.l);});
  if(porFrase){Object.values(grupos).forEach(g=>{if(g.length>1&&Math.min(...g)/Math.max(...g)<0.6)falhas.push(tag+'H3 linhas desequilibradas');});Object.entries(grupos).forEach(([px,g])=>{if(!sec&&Math.max(...g)/W<0.85)falhas.push(tag+'H4 bloco de '+px+' px não preenche a largura');});}
  else if(L.length>1&&mn/mx<0.6)falhas.push(tag+'H3 linhas desequilibradas ('+r.equilibrio+')');
  if(!sec&&!porFrase&&mx/W<0.85)falhas.push(tag+'H4 não preenche a largura ('+Math.round(mx/W*100)+'%): aumentar a fonte');
  if(!sec&&fs<minPx)falhas.push(tag+'H5 fonte '+r.px+' px abaixo de '+minPx);
  if(!sec&&L.length>(porFrase?4:maxL))falhas.push(tag+'H6 '+L.length+' linhas (máx. '+maxL+')');
  const ems=el.querySelectorAll('em');const emw=[...ems].reduce((s,e)=>s+e.textContent.trim().split(/\s+/).length,0);
  if(!sec){if(!ems.length)falhas.push(tag+'H7 sem destaque laranja');else if(emw>=nw||emw/nw>0.6)falhas.push(tag+'H7 destaque grande demais ('+emw+' de '+nw+' palavras)');}
 });
 // M1 margens
 const tw=document.createTreeWalker(sl,NodeFilter.SHOW_TEXT);let n;while(n=tw.nextNode()){if(!n.textContent.trim())continue;const pe=n.parentElement;if(pe.closest('[data-livre],.bot'))continue;const cs=getComputedStyle(pe);if(cs.visibility==='hidden'||pe.offsetParent===null)continue;const r=document.createRange();r.selectNodeContents(n);for(const b of r.getClientRects()){if(!b.width)continue;const l=b.left-S.left,rt=S.right-b.right,bt=S.bottom-b.bottom,tp=b.top-S.top;if(l<80||rt<80||bt<96||tp<60){falhas.push('M1 texto fora da margem: "'+n.textContent.trim().slice(0,40)+'" (esq '+Math.round(l)+', dir '+Math.round(rt)+', baixo '+Math.round(bt)+', topo '+Math.round(tp)+')');break;}}}
 return {ok:!falhas.length,falhas:[...new Set(falhas)],manchetes};
}
g.checarArte=checar;
})(typeof window!=='undefined'?window:globalThis);
