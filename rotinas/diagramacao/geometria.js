/* geometria.js — mede fotos e textos do slide renderizado (para checar_imagem.py). Roda na página. */
(function(g){
async function geometria(doc=document){
 const sl=doc.querySelector('.sl')||doc.body;const S=sl.getBoundingClientRect();const rel=b=>({x:Math.round(b.left-S.left),y:Math.round(b.top-S.top),w:Math.round(b.width),h:Math.round(b.height)});
 const fotos=[];
 for(const el of sl.querySelectorAll('*')){const cs=getComputedStyle(el);const b=el.getBoundingClientRect();if(b.width<200||b.height<200)continue;
  let src=null,tipo=null;if(el.tagName==='IMG'){src=el.currentSrc||el.src;tipo='img';}else{const m=/url\(["']?([^"')]+)["']?\)/.exec(cs.backgroundImage);if(m){src=m[1];tipo='bg';}}
  if(!src||/\.svg|avatar/.test(src))continue;
  const im=new Image();im.src=src;try{await im.decode();}catch(e){}
  fotos.push({...rel(b),tipo,src:src.slice(0,120),url:src,nw:im.naturalWidth,nh:im.naturalHeight,fit:tipo==='img'?cs.objectFit:cs.backgroundSize,arte_inteira:el.classList.contains('pre')});}
 const textos=[];const tw=doc.createTreeWalker(sl,NodeFilter.SHOW_TEXT);let n;while(n=tw.nextNode()){if(!n.textContent.trim())continue;const pe=n.parentElement;if(pe.offsetParent===null)continue;const r=doc.createRange();r.selectNodeContents(n);for(const b of r.getClientRects())if(b.width)textos.push({...rel(b),t:n.textContent.trim().slice(0,30)});}
 // caixas que não são texto mas cobrem a foto: etiqueta, avatar, cartões
 for(const el of sl.querySelectorAll('.kick,.top.av,.bot .who,.bot.av img,[data-caixa]')){const b=el.getBoundingClientRect();if(b.width)textos.push({...rel(b),t:'['+(el.className||el.tagName)+']'});}
 return {W:Math.round(S.width),H:Math.round(S.height),fotos,textos};}
g.geometriaArte=geometria;
})(typeof window!=='undefined'?window:globalThis);
