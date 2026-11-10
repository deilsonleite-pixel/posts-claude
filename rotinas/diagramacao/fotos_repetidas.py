#!/usr/bin/env python3
"""fotos_repetidas.py — impede a mesma foto em peças do mesmo acontecimento (Cunha Law, regra do Deilson 10/11/2026).
Compara a foto nova com o registro de fotos já usadas (/mnt/project-files/cunha-law/design/fotos-usadas/).
Detecta a MESMA foto mesmo recortada, ampliada ou com outro enquadramento (ORB + homografia; mesma foto dá 500+ pontos, fotos diferentes do mesmo palco ficam abaixo de 100; corte em 150).
Fotos diferentes da mesma coletiva/entrevista (outro ângulo, outro plano) passam.

  checar:    fotos_repetidas.py checar <foto.jpg> [--evento slug] [--peca id] [--dias 60]
  registrar: fotos_repetidas.py registrar <foto.jpg> --peca id --evento slug [--momento "coletiva 09/11 Casa Branca"]
Sai com código 1 e "F1 ..." quando a foto já foi usada (em qualquer peça dos últimos --dias, ou do mesmo evento em qualquer data)."""
import sys,os,json,datetime,cv2,numpy as np
REG=os.environ.get('FOTOS_USADAS','/mnt/project-files/cunha-law/design/fotos-usadas')
A=sys.argv[1:];cmd=A[0];foto=A[1]
def opt(k,d=None): return A[A.index(k)+1] if k in A else d
def carrega(p):
  im=cv2.imread(p,cv2.IMREAD_GRAYSCALE)
  if im is None: raise SystemExit('não abriu '+p)
  s=900/max(im.shape);return cv2.resize(im,None,fx=s,fy=s) if s<1 else im
orb=cv2.ORB_create(3000)
def feats(im): return orb.detectAndCompute(im,None)
def mesma(a,b):
  ka,da=a;kb,db=b
  if da is None or db is None or len(ka)<20 or len(kb)<20: return 0
  m=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da,db,k=2)
  good=[x[0] for x in m if len(x)==2 and x[0].distance<0.75*x[1].distance]
  if len(good)<12: return len(good)
  src=np.float32([ka[g.queryIdx].pt for g in good]);dst=np.float32([kb[g.trainIdx].pt for g in good])
  H,mask=cv2.findHomography(src,dst,cv2.RANSAC,5.0)
  return int(mask.sum()) if mask is not None else 0
idx=os.path.join(REG,'indice.json');os.makedirs(REG,exist_ok=True)
L=json.load(open(idx)) if os.path.exists(idx) else []
if cmd=='checar':
  ev=opt('--evento');peca=opt('--peca');dias=int(opt('--dias',60));hoje=datetime.date.today()
  f=feats(carrega(foto));falhas=[]
  for r in L:
    if peca and r['peca']==peca: continue  # a própria peça (revisão) pode manter a foto
    rec=(hoje-datetime.date.fromisoformat(r['data'])).days<=dias
    if not (rec or (ev and r.get('evento')==ev)): continue
    p=os.path.join(REG,r['arquivo'])
    if not os.path.exists(p): continue
    n=mesma(f,feats(carrega(p)))
    if n>=150: falhas.append(f"F1 foto repetida: já usada em {r['peca']} ({r['data']}, evento {r.get('evento') or '-'}; {n} pontos iguais). Buscar outra foto {('do mesmo momento ('+r['momento']+')') if r.get('momento') else 'do mesmo momento'}, com outro ângulo ou plano")
  print(json.dumps({'ok':not falhas,'falhas':falhas},ensure_ascii=False));sys.exit(1 if falhas else 0)
elif cmd=='registrar':
  peca=opt('--peca');ev=opt('--evento')
  if not peca or not ev: raise SystemExit('registrar precisa de --peca e --evento')
  im=cv2.imread(foto);s=1200/max(im.shape[:2]);im=cv2.resize(im,None,fx=s,fy=s) if s<1 else im
  n=sum(1 for r in L if r['peca']==peca)+1;nome=f"{peca}__{n:02d}.jpg";cv2.imwrite(os.path.join(REG,nome),im,[cv2.IMWRITE_JPEG_QUALITY,88])
  L.append({'peca':peca,'evento':ev,'momento':opt('--momento',''),'data':datetime.date.today().isoformat(),'arquivo':nome})
  json.dump(L,open(idx,'w'),ensure_ascii=False,indent=1);print('registrada',nome)
