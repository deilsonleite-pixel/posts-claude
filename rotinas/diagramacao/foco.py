#!/usr/bin/env python3
"""foco.py — calcula o object-position para a foto (Cunha Law, 04/11/2026).
Uso: foco.py foto.jpg [altura_da_area_da_foto=700] [largura=1080] [--recortar saida.jpg] [--rosto 0.40]
--recortar: corta a foto na proporção da área, com o rosto ocupando ~40% da altura da área (meio corpo, como foto de
imprensa), sem ampliar mais de 1,3x. Use o arquivo cortado com foco "50% 50%".
Põe o rosto principal (o maior) a ~60% da largura (longe do avatar, que fica à esquerda) e a ~46% da altura da área da foto,
para o rosto ficar inteiro, longe do texto e do avatar. Sem rosto: centro do assunto mais contrastado (fallback 50% 35%).
Também avisa se a foto vai ser ampliada demais (resolução) ou se o rosto fica pequeno."""
import sys,os,cv2,json
A=sys.argv[1:];rec=A[A.index('--recortar')+1] if '--recortar' in A else None;fr=float(A[A.index('--rosto')+1]) if '--rosto' in A else 0.33
P=[x for i,x in enumerate(A) if not x.startswith('--') and (i==0 or not A[i-1].startswith('--'))]
f=P[0];Hb=int(P[1]) if len(P)>1 else 700;Wb=int(P[2]) if len(P)>2 else 1080
im=cv2.imread(f);h,w=im.shape[:2];s=max(Wb/w,Hb/h);sw,sh=w*s,h*s
det=cv2.FaceDetectorYN.create(os.path.join(os.path.dirname(os.path.abspath(__file__)),'modelos','yunet.onnx'),'',(w,h),0.7,0.3,5000)
_,fs=det.detect(im);out={'escala':round(s,2),'foto':[w,h]}
def pos(cx,cy,ty=0.38):
  px=0 if sw<=Wb+1 else min(100,max(0,(cx*s-Wb/2)/(sw-Wb)*100))
  py=0 if sh<=Hb+1 else min(100,max(0,(cy*s-Hb*ty)/(sh-Hb)*100))
  return f"{px:.0f}% {py:.0f}%"
if fs is not None and len(fs):
  x,y,fw,fh=max(fs,key=lambda r:r[2]*r[3])[:4];out['foco']=pos(x+fw/2,y+fh/2);out['rosto_px_na_arte']=int(fh*s)
else: out['foco']='50% 35%';out['rosto']='nenhum'
if s>1.3: out['alerta']=f'foto ampliada {s:.1f}x: buscar arquivo maior'
if rec and fs is not None and len(fs):
  x,y,fw,fh=max(fs,key=lambda r:r[2]*r[3])[:4]
  ch=min(h,max(Hb/1.3,fh/fr));cw=ch*Wb/Hb
  if cw>w: cw=w;ch=cw*Hb/Wb
  cx=min(max(x+fw/2-cw*0.60,0),w-cw);cy=min(max(y+fh/2-ch*0.46,0),h-ch)  # rosto a 60% da largura (o avatar fica à esquerda) e 46% da altura
  cv2.imwrite(rec,im[int(cy):int(cy+ch),int(cx):int(cx+cw)],[cv2.IMWRITE_JPEG_QUALITY,93])
  out.update({'recorte':rec,'recorte_px':[int(cw),int(ch)],'ampliacao':round(float(Hb/ch),2),'rosto_px_na_arte':int(fh*Hb/ch),'foco':'50% 50%'})
  out.pop('alerta',None)
  if Hb/ch>1.3: out['alerta']='recorte ampliado demais'
print(json.dumps(out,ensure_ascii=False))
