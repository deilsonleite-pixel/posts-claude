// Instalação (uma vez por sessão): pip install opencv-python-headless  (o detector de rosto usa modelos/yunet.onnx).
/* render.js — renderiza a arte, aplica a regra de manchete e confere (Cunha Law, 04/11/2026)
   Peça da Central:  node render.js central.html peca.json saida/prefixo [slides "1,3"] [--sem-fit]
   Arte própria:     node render.js arte.html - saida/prefixo        (HTML 1080x1350 com .sl; manchete em h4 ou [data-headline])
   Gera <prefixo>_NN.png, <prefixo>_NN_celular.png (540 px, como no feed) e imprime a conferência.
   Sai com código 1 se alguma regra falhar: NÃO entregar a arte assim.
   Precisa de img/avatar-leo.jpg e blob/<id>.jpg ao lado (como o r.js), quando a peça usar. */
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');
const FIT=fs.readFileSync(__dirname+'/fit-headline.js','utf8'),CHK=fs.readFileSync(__dirname+'/checar.js','utf8'),GEO=fs.readFileSync(__dirname+'/geometria.js','utf8');const {execFileSync}=require('child_process');
(async()=>{const a=process.argv.slice(2);const semFit=a.includes('--sem-fit'),pessoa=a.includes('--pessoa');const [html,piece,out,only]=a.filter(x=>!x.startsWith('--'));
const b=await chromium.launch();const pg=await b.newPage({viewport:{width:1080,height:1350}});
const base=path.dirname(path.resolve(html));
await pg.route('**/*',r=>{const u=r.request().url();if(u.includes('avatar-leo')&&fs.existsSync(__dirname+'/img/avatar-leo.jpg'))return r.fulfill({path:__dirname+'/img/avatar-leo.jpg'});if(u.includes('/_blob/')){const id=u.split('/_blob/')[1];for(const d of [__dirname+'/blob/',base+'/blob/'])for(const e of ['.jpg','.png'])if(fs.existsSync(d+id+e))return r.fulfill({path:d+id+e});}if(u.startsWith('file:')||u.includes('fonts.g')||u.startsWith('data:'))return r.continue();return r.abort();});
let falhou=false;
async function conferir(nome){await pg.evaluate(()=>document.fonts.ready);
 if(!semFit){await pg.addScriptTag({content:FIT});const f=await pg.evaluate(()=>{const r=fitAll(document);if(window.ajustarFoto)ajustarFoto();return r;});f.forEach(x=>{if(x&&!x.ok){console.log('  FIT: '+x.motivo);}});}
 await pg.addScriptTag({content:CHK});const r=await pg.evaluate(()=>checarArte(document));
 const el=pg.locator('.sl').first();await el.screenshot({path:nome+'.png'});
 const buf=await el.screenshot();const p2=await b.newPage({viewport:{width:540,height:675}});await p2.setContent(`<body style="margin:0"><img style="width:540px" src="data:image/png;base64,${buf.toString('base64')}">`);await p2.screenshot({path:nome+'_celular.png'});await p2.close();
 await pg.addScriptTag({content:GEO});const geo=await pg.evaluate(()=>geometriaArte(document));fs.writeFileSync(nome+'_geo.json',JSON.stringify(geo));
 await pg.addStyleTag({content:'.sl *{color:transparent!important;text-shadow:none!important;-webkit-text-stroke:0!important} .sl .kick,.sl .top,.sl .bot,.sl em,.sl .txt{background:transparent!important;border-color:transparent!important;box-shadow:none!important} .sl img:not(.pre){opacity:1} .sl .top img,.sl .bot img{visibility:hidden}'});
 await el.screenshot({path:nome+'_semtexto.png'});
 let im={ok:true,falhas:[],avisos:[]};try{im=JSON.parse(execFileSync('python3',[__dirname+'/checar_imagem.py',nome+'_geo.json',nome+'_semtexto.png'].concat(pessoa?['--pessoa']:[])).toString());}catch(e){im=JSON.parse((e.stdout||'{}').toString()||'{}');im.falhas=im.falhas||['checar_imagem.py não rodou: '+e.message.slice(0,120)];}
 fs.unlinkSync(nome+'_semtexto.png');fs.unlinkSync(nome+'_geo.json');r.falhas.push(...(im.falhas||[]));r.ok=r.ok&&!(im.falhas||[]).length;
 console.log((r.ok?'OK   ':'FALHA ')+path.basename(nome));r.manchetes.forEach(m=>console.log(`  manchete: ${m.texto} | ${m.px}px | ${m.linhas} linha(s) | preenche ${Math.round(m.preenche*100)}% | equilíbrio ${m.equilibrio}`));r.falhas.forEach(x=>console.log('  - '+x));(im.avisos||[]).forEach(x=>console.log('  aviso: '+x));if(!r.ok)falhou=true;}
if(!piece||piece==='-'){await pg.goto('file://'+path.resolve(html)+(a.find(x=>x.startsWith('--d='))?'?d='+encodeURIComponent(a.find(x=>x.startsWith('--d=')).slice(4)):''));await pg.waitForTimeout(1200);await conferir(out);}
else{await pg.goto('file://'+path.resolve(html));await pg.waitForTimeout(1500);const p=JSON.parse(fs.readFileSync(piece));const n=p.slides.length;
 const css=await pg.evaluate(()=>[...document.querySelectorAll('style,link[rel=stylesheet]')].map(x=>x.outerHTML).join(''));
 for(let i=0;i<n;i++){if(only&&!only.split(',').includes(String(i+1)))continue;const s={...p.slides[i]};delete s.png;
  const h=await pg.evaluate(([s,p,i,n])=>slide(s,p,i,n),[s,p,i,n]);
  await pg.setContent(`<html><head>${css}</head><body style="margin:0">${h}</body></html>`).catch(()=>{});await pg.waitForTimeout(800);
  await conferir(`${out}_${String(i+1).padStart(2,'0')}`);await pg.goto('file://'+path.resolve(html));await pg.waitForTimeout(600);}}
await b.close();process.exit(falhou?1:0);})();
