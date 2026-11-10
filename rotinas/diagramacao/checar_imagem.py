#!/usr/bin/env python3
"""checar_imagem.py — conferência da FOTO na arte (Cunha Law, 04/11/2026). Uso: checar_imagem.py <geometria.json> <arte_sem_texto.png> [--pessoa]
Regras (ver REGRAS-DIAGRAMACAO.md, parte Imagem):
 I1 resolução: a foto não pode ser ampliada mais de 1,3x (fonte com pouca resolução fica borrada)
 I2 foto esticada: proporção exibida = proporção original (só cover/contain; nunca 'fill' / 100% 100%)
 I3 foto preenche: a foto vai de borda a borda na largura e ocupa >= 45% da área da arte
 I4 rosto livre: nenhum texto, etiqueta ou avatar sobre um rosto (com folga de 6%)
 I5 rosto inteiro: rosto não cortado pela borda da arte nem pela borda da foto
 I6 pessoa pública (--pessoa): rosto principal com altura >= 14% da arte (>= ~190 px), fácil de reconhecer — foto pequena/distante reprova
 I7 exposição: no máximo 2% de pixels estourados (>= 250) na área da foto
"""
import json,sys,os,cv2,numpy as np
geo=json.load(open(sys.argv[1]));img=cv2.imread(sys.argv[2]);pessoa='--pessoa' in sys.argv
W,H=geo['W'],geo['H'];img=cv2.resize(img,(W,H)) if img.shape[1]!=W else img
falhas=[];avisos=[]
fotos=[f for f in geo['fotos'] if not f.get('arte_inteira')]
if not fotos and not [f for f in geo['fotos'] if f.get('arte_inteira')]: falhas.append('I3 sem foto na arte (todo post leva imagem do assunto)')
area=0
for f in fotos:
  nw,nh=f.get('nw') or 0,f.get('nh') or 0
  if nw and nh:
    fit=(f.get('fit') or '')
    if fit in('fill','100% 100%') and abs((f['w']/f['h'])/(nw/nh)-1)>0.02: falhas.append(f"I2 foto esticada ({f['src'][-40:]})")
    esc=max(f['w']/nw,f['h']/nh) if fit not in('contain',) else min(f['w']/nw,f['h']/nh)
    if esc>1.3: falhas.append(f"I1 foto ampliada {esc:.1f}x ({nw}x{nh} px para {f['w']}x{f['h']}): buscar arquivo maior")
    elif min(nw,nh)<1080: avisos.append(f"foto com {nw}x{nh} px: no limite")
  area=max(area,f['w']*f['h'])
  if f['w']<W-4 and f['w']*f['h']>0.15*W*H: falhas.append(f"I3 foto não vai de borda a borda ({f['w']} de {W} px de largura)")
if fotos and area<0.45*W*H: falhas.append(f"I3 foto pequena: ocupa {area*100//(W*H)}% da arte (mín. 45%)")
# rostos
here=os.path.dirname(os.path.abspath(__file__))
det=cv2.FaceDetectorYN.create(os.path.join(here,'modelos','yunet.onnx'),'',(W,H),0.7,0.3,5000)
_,fs=det.detect(img);rostos=[] if fs is None else [tuple(map(int,x[:4])) for x in fs]
for (x,y,w,h) in rostos:
  m=int(0.06*H);R=(x-m,y-m,x+w+m,y+h+m)
  for t in geo['textos']:
    if t['x']<R[2] and t['x']+t['w']>R[0] and t['y']<R[3] and t['y']+t['h']>R[1]:
      falhas.append(f"I4 texto/caixa sobre rosto: \"{t['t']}\" (rosto em x{x} y{y} {w}x{h})");break
  if x<2 or y<2 or x+w>W-2: falhas.append(f"I5 rosto cortado pela borda (x{x} y{y})")
  for f in fotos:
    if f['x']<x<f['x']+f['w'] and f['y']<y<f['y']+f['h'] and y+h>f['y']+f['h']+2: falhas.append('I5 rosto cortado pela borda da foto')
if pessoa:
  if not rostos: falhas.append('I6 notícia de pessoa pública sem o rosto da pessoa na arte')
  elif max(h for *_,h in rostos)<0.14*H: falhas.append(f"I6 rosto pequeno: {max(h for *_,h in rostos)} px de altura (mín. {int(0.14*H)}): foto mais próxima ou maior")
for f in fotos[:1]:
  roi=cv2.cvtColor(img[max(0,f['y']):f['y']+f['h'],max(0,f['x']):f['x']+f['w']],cv2.COLOR_BGR2GRAY)
  if roi.size and (roi>=250).mean()>0.02: falhas.append(f"I7 {100*(roi>=250).mean():.0f}% de pixels estourados na foto")
print(json.dumps({'ok':not falhas,'falhas':falhas,'avisos':avisos,'rostos':rostos},ensure_ascii=False))
