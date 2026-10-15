#!/usr/bin/env python3
"""Cenários do fluxo, sem internet: python3 test_fluxo.py  (sai com erro se algum falhar)."""
import json, os, shutil, subprocess, sys, tempfile, datetime as dt
from zoneinfo import ZoneInfo

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fluxo_worker.py")
SP = ZoneInfo("America/Sao_Paulo")
FUT = (dt.datetime.now(SP) + dt.timedelta(days=5)).strftime("%Y-%m-%dT12:00")
FUT2 = (dt.datetime.now(SP) + dt.timedelta(days=6)).strftime("%Y-%m-%dT07:30")
PAST = (dt.datetime.now(SP) - dt.timedelta(days=1)).strftime("%Y-%m-%dT12:00")
NOW = dt.datetime.now(dt.timezone.utc)
iso = lambda d: d.isoformat().replace("+00:00", "Z")
TXT = "Teste descartável da Central: não publicar."
SNAP = {"titulo": "Teste", "texto": TXT, "midia_n": 1, "formato": "post"}
falhas = []

def post(uuid, quando, redes=("instagram", "facebook"), draft=False, text=TXT, n=1):
    return {"id": 1, "uuid": uuid, "publicationDate": {"dateTime": quando + ":00", "timezone": "America/Sao_Paulo"}, "text": text,
            "providers": [{"network": r, "status": "PENDING"} for r in redes], "media": ["m"] * n, "autoPublish": True, "draft": draft,
            "instagramData": {"type": "POST"}}

def roda(central, fluxo, posts=None, pecas=None, extra=None):
    d = tempfile.mkdtemp()
    os.makedirs(d + "/fluxo"); os.makedirs(d + "/pecas")
    for k, v in fluxo.items():
        json.dump(v, open(f"{d}/fluxo/{k}.json", "w"))
    for k, v in (pecas or {}).items():
        json.dump(v, open(f"{d}/pecas/{k}.json", "w"))
    args = ["python3", W, "plano", central, d]
    if posts is not None:
        json.dump({"data": posts}, open(d + "/posts.json", "w")); args += ["--posts", d + "/posts.json"]
    args += extra or []
    r = json.loads(subprocess.check_output(args))
    shutil.rmtree(d)
    return r

def aut(redes=("instagram", "facebook"), q=FUT, aid="A1", rev=1):
    return {"id": aid, "rev": rev, "redes": {r: q for r in redes}, "por": "u", "em": iso(NOW), "snap": SNAP}

def ok(nome, cond, r):
    print(("OK   " if cond else "FALHA"), nome)
    if not cond:
        falhas.append(nome); print(json.dumps(r, ensure_ascii=False, indent=1)[:2500])

APR = {"on": True, "rev": 1}
PEC = {"x": {"tipo": "post", "rev": 1, "data": FUT[:10]}}

# 1. aprovado sem "Pode postar" não gera envio
r = roda("marcelao", {"x": {"aprov": APR}}, [], PEC)
ok("Aprovar sozinho não agenda", not r["acoes"], r)

# 2. Pode postar gera exatamente um envio (IG+FB no mesmo post)
r = roda("marcelao", {"x": {"aprov": APR, "aut": aut()}}, [], PEC)
ok("Pode postar cria um único agendamento com as duas redes", len(r["acoes"]) == 1 and r["acoes"][0]["tipo"] == "metricool_criar" and r["acoes"][0]["redes"] == ["facebook", "instagram"], r)

# 3. clique repetido / rodada simultânea: envio recente em andamento não repete
pl = {k: {"st": "enviando", "aut": "A1", "desde": iso(NOW - dt.timedelta(minutes=3)), "tent": 1, "quando": FUT} for k in ("instagram", "facebook")}
r = roda("marcelao", {"x": {"aprov": APR, "aut": aut(), "plat": pl}}, [], PEC)
ok("Envio em andamento não é repetido", not r["acoes"], r)

# 4. resultado incerto: consulta antes de repetir -> adota o que já existe
pl = {k: {"st": "enviando", "aut": "A1", "desde": iso(NOW - dt.timedelta(minutes=40)), "tent": 1, "quando": FUT} for k in ("instagram", "facebook")}
r = roda("marcelao", {"x": {"aprov": APR, "aut": aut(), "plat": pl}}, [post("U9", FUT)], PEC)
ok("Resultado incerto: acha o agendamento e não envia de novo", not [a for a in r["acoes"] if a["tipo"] == "metricool_criar"] and any(m["patch"].get("plat", {}).get("instagram", {}).get("st") == "agendado" for m in r["marcas"]), r)

# 5. resultado incerto sem registro: nova tentativa controlada (tent 2), e falha após 3
r = roda("marcelao", {"x": {"aprov": APR, "aut": aut(), "plat": pl}}, [], PEC)
ok("Sem registro após 20 min: nova tentativa numerada", len(r["acoes"]) == 1 and r["acoes"][0]["claim"]["plat"]["instagram"]["tent"] == 2, r)
pl3 = {k: dict(v, tent=3) for k, v in pl.items()}
r = roda("marcelao", {"x": {"aprov": APR, "aut": aut(), "plat": pl3}}, [], PEC)
ok("Após 3 tentativas: Falha no agendamento, sem novo envio", not r["acoes"] and any(m["patch"].get("plat", {}).get("instagram", {}).get("st") == "falha" for m in r["marcas"]), r)

# 6. confirmado de verdade só quando o registro confere
pl = {k: {"st": "enviado", "aut": "A1", "ext": {"uuid": "U1"}, "desde": iso(NOW), "tent": 1, "quando": FUT} for k in ("instagram", "facebook")}
r = roda("marcelao", {"x": {"aprov": APR, "aut": aut(), "plat": pl}}, [post("U1", FUT)], PEC)
ok("Registro conferido vira Agendado", all(m["patch"]["plat"][k]["st"] == "agendado" for m in r["marcas"] if m["patch"].get("plat") for k in ("instagram", "facebook")), r)
r = roda("marcelao", {"x": {"aprov": APR, "aut": aut(), "plat": pl}}, [post("U1", FUT, draft=True)], PEC)
ok("Rascunho não conta como agendado", not any(m["patch"].get("plat", {}).get("instagram", {}).get("st") == "agendado" for m in r["marcas"]), r)
r = roda("marcelao", {"x": {"aprov": APR, "aut": aut(), "plat": pl}}, [post("U1", FUT, text="outra legenda")], PEC)
ok("Legenda diferente: corrige em vez de confirmar", any(a["tipo"] == "metricool_atualizar" for a in r["acoes"]), r)

# 7. retirar aprovação cancela o agendamento existente
pl = {k: {"st": "agendado", "aut": "A1", "ext": {"uuid": "U1"}, "quando": FUT, "rev": 1} for k in ("instagram", "facebook")}
r = roda("marcelao", {"x": {"aprov": {"on": False, "rev": 1}, "aut": None, "plat": pl}}, [post("U1", FUT)], PEC)
ok("Retirar aprovação cancela no Metricool", len(r["acoes"]) == 1 and r["acoes"][0]["tipo"] == "metricool_cancelar" and r["acoes"][0]["info"]["draft"] is True, r)
r = roda("marcelao", {"x": {"aprov": {"on": False, "rev": 1}, "plat": {k: dict(v, st="cancelando") for k, v in pl.items()}}}, [post("U1", FUT, draft=True)], PEC)
ok("Cancelamento confirmado quando a plataforma mostra rascunho", all(m["patch"]["plat"][k]["st"] == "cancelado" for m in r["marcas"] if m["patch"].get("plat") for k in ("instagram", "facebook")), r)

# 8. alteração concluída (rev 2): autorização da v1 não vale -> cancela agendamento da v1, não reenvia sozinho
r = roda("marcelao", {"x": {"aprov": APR, "aut": aut(), "plat": pl}}, [post("U1", FUT)], {"x": {"tipo": "post", "rev": 2, "data": FUT[:10]}})
ok("Nova versão não fica agendada com a versão velha", any(a["tipo"] == "metricool_cancelar" for a in r["acoes"]) and not any(a["tipo"] == "metricool_criar" for a in r["acoes"]), r)

# 9. redes independentes: YouTube não conectado falha, Instagram segue
q = {"instagram": FUT2, "youtube": FUT2[:10] + "T19:30"}
a9 = {"id": "A9", "rev": 1, "redes": q, "em": iso(NOW), "snap": dict(SNAP, formato="reel")}
r = roda("marcelao", {"r1": {"aprov": APR, "aut": a9}}, [])
ok("Cada rede com sua situação (IG envia, YT falha por falta de conexão)", any(a["tipo"] == "metricool_criar" and a["redes"] == ["instagram"] for a in r["acoes"]) and any(m["patch"].get("plat", {}).get("youtube", {}).get("erro_cod") == "rede_nao_conectada" for m in r["marcas"]), r)

# 10. horário vencido não vira publicação imediata
r = roda("marcelao", {"x": {"aprov": APR, "aut": aut(q=PAST)}}, [], PEC)
ok("Horário passado: pede nova data, não envia", not r["acoes"] and any(m["patch"].get("plat", {}).get("instagram", {}).get("erro_cod") == "horario_passou" for m in r["marcas"]), r)

# 11. agendamento apagado direto no Metricool: central corrige e encerra a autorização
r = roda("marcelao", {"x": {"aprov": APR, "aut": aut(), "plat": pl}}, [], PEC)
ok("Removido na plataforma: deixa de mostrar Agendado", any(m["patch"].get("plat", {}).get("instagram", {}).get("st") == "cancelado_ext" for m in r["marcas"]) and any(m["patch"].get("aut", 1) is None for m in r["marcas"]), r)

# 12. excluir peça agendada: cancela primeiro, limpa depois, nunca reenvia
exc = {"em": iso(NOW), "estado": "cancelando", "arquivos": [{"path": "img/x.png"}], "src": "peca"}
r = roda("marcelao", {"x": {"excluido": exc, "aprov": {"on": False}, "plat": pl}}, [post("U1", FUT)], {})
ok("Excluída e agendada: pede cancelamento, ainda não limpa", [a["tipo"] for a in r["acoes"]] == ["metricool_cancelar"], r)
r = roda("marcelao", {"x": {"excluido": exc, "aprov": {"on": False}, "plat": {k: dict(v, st="cancelado") for k, v in pl.items()}}}, [], {})
ok("Cancelamento confirmado: segue para apagar arquivos", [a["tipo"] for a in r["acoes"]] == ["limpar_arquivos"], r)
r = roda("marcelao", {"x": {"excluido": dict(exc, estado="concluido"), "aut": aut(), "aprov": APR}}, [], {})
ok("Excluída não volta a ser enviada (tarefa antiga bloqueada)", not r["acoes"], r)

# 13. Cunha via Zoho Social (API simulada, sem rede)
import importlib.util
spec = importlib.util.spec_from_file_location("fw", W); fw = importlib.util.module_from_spec(spec); spec.loader.exec_module(fw)
fw.zoho_token = lambda z: "tok"
FUTD = "2026-12-01"  # depois do período em que a equipe agendou direto no Zoho
def zplano(fluxo, pecas, status_api, midia=True, postado=()):
    fw.zoho_req = lambda z, tok, m, path, body=None: status_api(path)
    fw.zoho_midia = lambda c, doc, p: ([{"file_path": "u", "name": "n", "type": "image", "format": "jpg", "size": 1, "width": 1080, "height": 1350}] if midia else None)
    d = tempfile.mkdtemp(); [os.makedirs(d + x) for x in ("/fluxo", "/pecas", "/postado")]
    for k, v in fluxo.items(): json.dump(v, open(f"{d}/fluxo/{k}.json", "w"))
    for k, v in pecas.items(): json.dump(v, open(f"{d}/pecas/{k}.json", "w"))
    for k in postado: json.dump({"v": 1}, open(f"{d}/postado/{k}.json", "w"))
    r = fw.plano("cunha", d); shutil.rmtree(d); return r
def pz(r):
    for m in r["marcas"]:
        if m["patch"].get("plat", {}).get("instagram"): return m["patch"]["plat"]["instagram"]
    return {}
A = aut(redes=("instagram",))
PZ = {"c": {"tipo": "post", "rev": 1, "data": FUTD, "slides": [{}], "atualizado": "x"}}
r = zplano({"c": {"aprov": APR, "aut": A}}, PZ, lambda p: (200, {}))
ok("Zoho: Pode postar gera um agendamento com horário em ms e imagem do repositório", len(r["acoes"]) == 1 and r["acoes"][0]["tipo"] == "zoho_criar" and r["acoes"][0]["corpo"]["post"]["schedule_time"] > 0 and r["acoes"][0]["corpo"]["post"]["messages"][0]["channels"][0]["network"] == "instagram", r)
r = zplano({"c": {"aprov": APR, "aut": A}}, PZ, lambda p: (200, {}), midia=False)
ok("Zoho: sem imagem da versão, não envia (aguarda mídia)", not r["acoes"] and pz(r)["st"] == "aguardando_midia", r)
pl = {"instagram": {"st": "enviado", "aut": "A1", "ext": {"id": "99"}, "quando": FUT, "rev": 1}}
r = zplano({"c": {"aprov": APR, "aut": A, "plat": pl}}, PZ, lambda p: (200, {"data": [{"network": "instagram", "status": "scheduled"}]}))
ok("Zoho: status 'scheduled' na API vira Agendado", pz(r)["st"] == "agendado" and not r["acoes"], r)
r = zplano({"c": {"aprov": {"on": False, "rev": 1}, "plat": dict(pl, instagram=dict(pl["instagram"], st="agendado"))}}, PZ, lambda p: (200, {"data": [{"network": "instagram", "status": "scheduled"}]}))
ok("Zoho: aprovação retirada com post agendado = Cancelamento pendente com instrução", pz(r)["st"] == "cancelando" and "Cancele no Zoho" in pz(r)["erro"], r)
r = zplano({"c": {"aprov": {"on": False, "rev": 1}, "plat": {"instagram": dict(pl["instagram"], st="cancelando")}}}, PZ, lambda p: (404, {}))
ok("Zoho: post sumiu depois do pedido = cancelamento confirmado", pz(r)["st"] == "cancelado", r)
r = zplano({"c": {"aprov": APR, "aut": A, "plat": {"instagram": {"st": "enviando", "aut": "A1", "desde": iso(NOW), "tent": 1, "quando": FUT}}}}, PZ, lambda p: (200, {}))
ok("Zoho: envio em andamento não é repetido", not r["acoes"], r)
r = zplano({"c": {"aprov": APR, "aut": A}}, {"c": dict(PZ["c"], data="2026-10-19")}, lambda p: (200, {}))
ok("Zoho: até 20/10 (agendado pela equipe) não envia de novo", not r["acoes"] and pz(r)["st"] == "externo", r)
r = zplano({"c": {"aprov": APR, "aut": A, "plat": pl}}, PZ, lambda p: (200, {"data": [{"network": "instagram", "status": "unpublished", "error": {"code": 1, "message": "token expirado"}}]}))
ok("Zoho: erro da rede aparece como Falha com a mensagem", pz(r)["st"] == "falha" and "token expirado" in pz(r)["erro"], r)

# 14. Metricool fora do ar: mantém aguardando, não marca falha nas peças
r = roda("marcelao", {"x": {"aprov": APR, "aut": aut(), "plat": pl}}, None, PEC, ["--sem-conexao", "timeout"])
ok("Sem resposta da plataforma: nada muda nas peças", not r["acoes"] and not r["marcas"] and r["status_plataforma"]["ok"] is False, r)

print("\n%d cenário(s) com falha" % len(falhas) if falhas else "\nTodos os cenários passaram.")
sys.exit(1 if falhas else 0)
