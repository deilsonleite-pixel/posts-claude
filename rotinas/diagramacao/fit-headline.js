/* fit-headline.js — Cunha Law, regra de headline (04/11/2026)
   Escolhe as quebras de linha e o tamanho da fonte da manchete para que:
   - nenhuma linha fique com uma palavra só (salvo manchete de 1 ou 2 palavras);
   - frase que termina (. ? ! :) fecha a linha, nunca fica no meio dela;
   - nenhuma linha termine em palavra fraca (o, a, de, do, em, para, que...);
   - as linhas fiquem equilibradas (a mais curta tem >= 60% da mais longa);
   - a linha mais longa preencha a largura da caixa (fonte calculada pela largura);
   - a fonte fique entre min e max (padrão 96 a 200 px), no máximo maxLinhas.
   Uso no navegador:  fitHeadline(elementoH4, {min:120, max:200, maxLinhas:3, alturaMax:null})
   Ou em todo o slide: fitAll(document)  (pega .sl h4 e [data-headline]; pula [data-nofit]).
   Mantém o destaque <em> (laranja) palavra por palavra. */
(function(g){
const FRACAS=new Set("o a os as um uma uns umas de da do das dos e em no na nos nas ao aos à às para pra por pelo pela pelos pelas com sem que se ou mas nem sua seu suas seus the of to in and".split(" "));
function tokens(el){const out=[];(function walk(n,em){for(const c of n.childNodes){if(c.nodeType===3){for(const w of c.textContent.split(/\s+/))if(w)out.push({w,em});}else if(c.nodeType===1){if(c.tagName==='BR')continue;walk(c,em||c.tagName==='EM');}}})(el,false);return out;}
function measurer(el){const cs=getComputedStyle(el);const cv=document.createElement('canvas').getContext('2d');
 const ls=parseFloat(cs.letterSpacing)||0, fs=parseFloat(cs.fontSize)||100, lsEm=ls/fs;
 cv.font=`${cs.fontStyle} ${cs.fontWeight} 100px ${cs.fontFamily}`;const up=cs.textTransform==='uppercase';
 return t=>{const s=up?t.toUpperCase():t;return (cv.measureText(s).width+lsEm*100*s.length)/100;};}
function partitions(n,k){const res=[];(function rec(start,k,acc){if(k===1){res.push([...acc,[start,n]]);return;}for(let e=start+1;e<=n-k+1;e++)rec(e,k-1,[...acc,[start,e]]);})(0,k,[]);return res;}
function fitHeadline(el,o={}){
 const min=o.min??96,max=o.max??200,maxL=o.maxLinhas??3,lh=o.lineHeight??(parseFloat(getComputedStyle(el).lineHeight)/parseFloat(getComputedStyle(el).fontSize)||0.92);
 const tk=tokens(el);if(!tk.length)return null;const m=measurer(el);const sp=m(' ')||0.22;
 const ww=tk.map(t=>m(t.w));
 const cs=getComputedStyle(el);const box=o.largura??(el.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight));
 let best=null;
 for(let k=1;k<=Math.min(maxL,tk.length);k++){
  for(const p of partitions(tk.length,k)){
   const wid=p.map(([a,b])=>{let s=0;for(let i=a;i<b;i++)s+=ww[i]+(i>a?sp:0);return s;});
   const lens=p.map(([a,b])=>b-a);
   if(tk.length>=3&&lens.some(l=>l<2))continue;                       // sem palavra sozinha
   if(p.slice(0,-1).some(([a,b])=>FRACAS.has(tk[b-1].w.toLowerCase().replace(/[^\p{L}]/gu,''))))continue; // linha não termina em palavra fraca
   if(k>1&&p.some(([a,b])=>{for(let i=a;i<b-1;i++)if(/[.?!:]$/.test(tk[i].w))return true;return false;}))continue; // frase termina no fim da linha, nunca no meio
   const bal=k>1?Math.min(...wid)/Math.max(...wid):1;if(bal<0.6)continue; // equilíbrio
   let fs=Math.min(max,box/Math.max(...wid));if(o.alturaMax)fs=Math.min(fs,o.alturaMax/(k*lh));
   if(fs<min)continue;
   const score=fs*(1-0.04*(k-1))+bal*6;                                // maior fonte; empate -> menos linhas e mais equilíbrio
   if(!best||score>best.score)best={score,fs:Math.floor(fs),p,k,bal};
  }
 }
 if(o.porFrase!==false){ // 2 frases que não cabem juntas: cada frase vira um bloco que preenche a largura (a do destaque maior)
  const fr=[];let cur=[];tk.forEach((t,i)=>{cur.push(t);if(/[.?!:]$/.test(t.w)||i===tk.length-1){fr.push(cur);cur=[];}});
  if(fr.length>=2&&fr.length<=3){const blocos=[];let ok=true,alt=0;
   for(const f of fr){const wf=f.map(t=>m(t.w));let bb=null;
    for(let k=1;k<=2;k++)for(const p of partitions(f.length,k)){const wid=p.map(([a,b])=>{let s=0;for(let i=a;i<b;i++)s+=wf[i]+(i>a?sp:0);return s;});
     if(f.length>=3&&p.some(([a,b])=>b-a<2))continue;if(p.slice(0,-1).some(([a,b])=>FRACAS.has(f[b-1].w.toLowerCase().replace(/[^\p{L}]/gu,''))))continue;
     const bal=k>1?Math.min(...wid)/Math.max(...wid):1;if(bal<0.6)continue;const fs=Math.min(max,box/Math.max(...wid));const sc=(k===1&&fs>=(o.minFrase??72))?1e6+fs:fs;/* cada frase em 1 linha sempre que couber no mínimo */if(!bb||sc>bb.sc)bb={sc,fs:Math.floor(fs),p,k};}
    if(!bb||bb.fs<(o.minFrase??72)){ok=false;break;}blocos.push({f,...bb});alt+=bb.fs*lh*bb.k;}
   if(ok&&(!o.alturaMax||alt<=o.alturaMax*1.05)&&(!best||Math.min(...blocos.map(B=>B.fs))>best.fs)){const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;');
    el.innerHTML=blocos.map(B=>B.p.map(([a,b])=>`<span data-frase style="display:block;white-space:nowrap;font-size:${B.fs}px">`+B.f.slice(a,b).map(t=>t.em?'<em>'+esc(t.w)+'</em>':esc(t.w)).join(' ')+'</span>').join('')).join('');
    el.style.textWrap='nowrap';el.dataset.fit='frases';return {ok:true,modo:'uma frase por bloco',px:blocos.map(B=>B.fs)};}}
 }
 if(!best){el.dataset.fit='falhou';return {ok:false,motivo:'Manchete longa demais para '+maxL+' linhas a '+min+' px: dividir em pergunta + resto menor, ou enxugar.'};}
 const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;');
 el.innerHTML=best.p.map(([a,b])=>'<span style="display:block;white-space:nowrap">'+tk.slice(a,b).map(t=>t.em?'<em>'+esc(t.w)+'</em>':esc(t.w)).join(' ')+'</span>').join('');
 el.style.fontSize=best.fs+'px';el.style.textWrap='nowrap';el.dataset.fit='ok';
 return {ok:true,px:best.fs,linhas:best.k,equilibrio:+best.bal.toFixed(2)};
}
function fitAll(doc=document,o={}){return [...doc.querySelectorAll('.sl h4:not([data-nofit]),[data-headline]:not([data-nofit])')].map(el=>fitHeadline(el,{...o,...JSON.parse(el.dataset.fitOpts||'{}')}));}
g.fitHeadline=fitHeadline;g.fitAll=fitAll;
})(typeof window!=='undefined'?window:globalThis);
