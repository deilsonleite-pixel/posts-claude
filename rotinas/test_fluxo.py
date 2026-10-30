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
_LS = fw.limite_semana
def zplano(fluxo, pecas, status_api, midia=True, postado=(), limite="2099-12-31", extras=()):
    fw.limite_semana = lambda hoje=None: limite
    fw.CFG["centrais"]["cunha"]["redes_extras"] = list(extras)
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
# urgente (regra de 16/10/2026): Pode postar publica na hora, mesmo com o horário da peça já passado
HOJE = fw.AGORA.strftime("%Y-%m-%d")
PU = {"c": dict(PZ["c"], urgente=True, data=HOJE)}
r = zplano({"c": {"aprov": APR, "aut": aut(redes=("instagram", "facebook"), q=PAST)}}, PU, lambda p: (200, {}))
ok("Zoho: urgente com Pode postar vira Publicar agora (POST /posts/publish, sem schedule_time), IG e FB",
   len(r["acoes"]) == 2 and all(a["endpoint"] == "/posts/publish" and a["agora"] and a["corpo"]["post"]["type"] == "publish" and "schedule_time" not in a["corpo"]["post"] for a in r["acoes"]), r)
r = zplano({"c": {"aprov": APR, "aut": aut(redes=("instagram",), q=PAST)}}, PZ, lambda p: (200, {}))
ok("Zoho: não urgente com horário passado continua sem sair (nada publica na hora)", not r["acoes"] and pz(r).get("erro_cod") == "horario_passou", r)
r = zplano({"c": {"aprov": APR}}, PU, lambda p: (200, {}))
ok("Zoho: urgente só aprovado, sem Pode postar, não publica", not r["acoes"], r)
r = zplano({"c": {"aprov": APR, "aut": aut(redes=("instagram",), q=PAST)}}, {"c": dict(PZ["c"], urgente=True, data="2026-10-16")}, lambda p: (200, {}))
ok("Zoho: urgente de outro dia não é publicado na hora", not r["acoes"], r)
r = zplano({"c": {"aprov": APR, "aut": A}}, PZ, lambda p: (200, {}), limite="2000-01-01")
ok("Zoho: Pode postar de semana seguinte espera a sexta (nada criado, nada gravado)", not r["acoes"] and not pz(r), r)
r = zplano({"c": {"aprov": APR, "aut": A}}, {"c": dict(PZ["c"], data=None)}, lambda p: (200, {}))
ok("Zoho: peça sem data (fixado) usa a data do Pode postar e é agendada", len(r["acoes"]) == 1 and r["acoes"][0]["tipo"] == "zoho_criar", r)
# X e Threads (regra do Deilson, 27/10/2026): mesmo horário do Instagram, legenda curta, X só até 4 imagens
LEGX = "Vai morar nos EUA? Fale com quem entende de visto!\n\n" + "Corpo longo da legenda. " * 20 + "\n\nEsta conversa é fictícia e foi criada com humor.\n\n📲 Salve e mande para um amigo.\n\nConteúdo informativo. Cada caso migratório exige análise individual."
PX = {"c": dict(PZ["c"], legenda=LEGX, hashtags="#vistoamericano #b #c #imigracaoeua #cunhalaw")}
r = zplano({"c": {"aprov": APR, "aut": aut(redes=("instagram", "facebook"))}}, PX, lambda p: (200, {}), extras=("twitter", "threads"))
_by = {a["redes"][0]: a for a in r["acoes"]}
_tx = _by.get("twitter", {}).get("corpo", {}).get("post", {}).get("messages", [{}])[0].get("message", "")
ok("Zoho: post vai também para X e Threads no horário do Instagram, com legenda curta (gancho, aviso de fictícia e aviso legal, sem CTA)",
   set(_by) == {"instagram", "facebook", "twitter", "threads"} and _by["twitter"]["quando"] == FUT and _by["threads"]["corpo"]["post"]["messages"][0]["channels"][0]["network"] == "threadsbyig"
   and fw._tam(_tx) <= 270 and _tx.startswith("Vai morar") and "fictícia" in _tx and "Conteúdo informativo" in _tx and "Salve" not in _tx
   and _tx.endswith("#vistoamericano #imigracaoeua"), r)
r = zplano({"c": {"aprov": APR, "aut": aut(redes=("instagram",))}}, {"c": dict(PX["c"], tipo="carrossel", slides=[{}] * 6)}, lambda p: (200, {}), extras=("twitter", "threads"))
ok("Zoho: carrossel com mais de 4 imagens não vai para o X (vai para o Threads)", sorted(a["redes"][0] for a in r["acoes"]) == ["instagram", "threads"], r)
r = zplano({"c": {"aprov": APR, "aut": aut(redes=("instagram",), q=PAST)}}, PX, lambda p: (200, {}), extras=("twitter", "threads"))
ok("Zoho: peça de horário passado não é republicada no X/Threads", not any(a["redes"][0] in ("twitter", "threads") for a in r["acoes"]) and not any((m["patch"].get("plat") or {}).get("twitter") for m in r["marcas"]), r)
r = zplano({"c": {"aprov": APR, "aut": aut(redes=("instagram",))}}, {"c": dict(PX["c"], tipo="reel")}, lambda p: (200, {}), extras=("twitter", "threads"))
ok("Zoho: reel não vai para X/Threads", [a["redes"][0] for a in r["acoes"]] == ["instagram"], r)
_ZA = fw.zoho_agendados
fw.zoho_agendados = lambda z, tok: [{"post_id": "777", "schedule_time": int(fw.q_dt(FUT).timestamp() * 1000),
    "messages": [{"message": "Texto da peça já agendado à mão no Zoho, com IG e FB juntos.", "channels": [{"network": "instagram"}, {"network": "facebookpage"}]}]}]
_A2 = aut(redes=("instagram", "facebook")); _A2["snap"] = dict(_A2.get("snap") or {}, texto="Texto da peça já agendado à mão no Zoho, com IG e FB juntos.")
r = zplano({"c": {"aprov": APR, "aut": _A2}}, PZ, lambda p: (200, {}))
_pl = next((m["patch"]["plat"] for m in r["marcas"] if m["patch"].get("plat")), {})
ok("Zoho: post igual já no Zoho (IG+FB juntos, feito à mão) é adotado nas duas redes, sem criar duplicado",
   not r["acoes"] and all(_pl.get(x, {}).get("ext", {}).get("id") == "777" for x in ("instagram", "facebook")), r)
fw.zoho_agendados = _ZA
# tentativas até agendar (Deilson 21/10/2026)
import importlib
m2 = importlib.reload(fw) if False else fw
_req, _tk, _ag, _sl = fw.zoho_req, fw.zoho_token, fw.zoho_agendados, fw.time.sleep
fw.time.sleep = lambda s: None
fw.zoho_token = lambda z, renovar=False: "T"
_ac = {"doc": "x", "redes": ["instagram"], "quando": FUT, "aut": "a1", "esperado": {"rev": 1}, "claim": {"plat": {"instagram": {"tent": 1}}},
       "corpo": {"post": {"type": "schedule", "schedule_time": 1, "messages": [{"message": "Texto X", "channels": [{"network": "instagram"}]}]}}}
_af = os.path.join(tempfile.mkdtemp(), "a.json"); json.dump(_ac, open(_af, "w"))
_seq = [(503, {}), (429, {}), (200, {"data": [{"success": True, "post_id": "901"}]})]
fw.zoho_req = lambda z, tok, m, p, b=None: _seq.pop(0)
fw.zoho_agendados = lambda z, tok: []
r = fw.zoho_criar("cunha", _af)
ok("Zoho: falha temporária (503, 429) tenta de novo até agendar", r.get("ok") and r["plat"]["instagram"]["ext"]["id"] == "901" and not _seq, r)
_seq = [(0, {})]
fw.zoho_agendados = lambda z, tok: [{"post_id": "902", "schedule_time": int(fw.q_dt(FUT).timestamp() * 1000), "messages": [{"message": "Texto X", "channels": [{"network": "instagram"}]}]}]
r = fw.zoho_criar("cunha", _af)
ok("Zoho: sem resposta, mas o post já foi criado -> adota, não duplica", r.get("ok") and r["plat"]["instagram"]["ext"]["id"] == "902" and not _seq, r)
fw.zoho_req = lambda z, tok, m, p, b=None: (400, {"message": "imagem recusada"})
r = fw.zoho_criar("cunha", _af)
ok("Zoho: recusa definitiva grava FALHA NO AGENDAMENTO e pede aviso ao Deilson", not r["ok"] and r.get("avisar") and "FALHA NO AGENDAMENTO" in r["plat"]["instagram"]["erro"] and "imagem recusada" in r["aviso"], r)
fw.zoho_req = lambda z, tok, m, p, b=None: (503, {})
fw.zoho_agendados = lambda z, tok: []
r = fw.zoho_criar("cunha", _af)
ok("Zoho: sem resposta em todas as tentativas -> incerto e aviso", r.get("incerto") and r.get("avisar") and r.get("aviso"), r)
fw.zoho_req, fw.zoho_token, fw.zoho_agendados, fw.time.sleep = _req, _tk, _ag, _sl

_d = __import__("datetime")
ok("Semana: terça 20/10 agenda até domingo 25/10; sexta 23/10 já vale até 01/11",
   _LS(_d.datetime(2026, 10, 20, 12, tzinfo=fw.SP)) == "2026-10-25" and _LS(_d.datetime(2026, 10, 23, 12, tzinfo=fw.SP)) == "2026-11-01" and _LS(_d.datetime(2026, 10, 25, 12, tzinfo=fw.SP)) == "2026-11-01", {})
r = zplano({"c": {"aprov": APR, "aut": A}}, PZ, lambda p: (200, {}), midia=False)
ok("Zoho: sem imagem da versão, não cria post e pede a subida da imagem na hora (nada espera rodada)",
   [a["tipo"] for a in r["acoes"]] == ["cunha_midia"] and r["acoes"][0]["doc"] == "c" and pz(r)["st"] == "aguardando_midia", r)
pl = {"instagram": {"st": "enviado", "aut": "A1", "ext": {"id": "99"}, "quando": FUT, "rev": 1}}
r = zplano({"c": {"aprov": APR, "aut": A, "plat": pl}}, PZ, lambda p: (200, {"data": [{"network": "instagram", "status": "scheduled"}]}))
ok("Zoho: status 'scheduled' na API vira Agendado", pz(r)["st"] == "agendado" and not r["acoes"], r)
r = zplano({"c": {"aprov": {"on": False, "rev": 1}, "plat": dict(pl, instagram=dict(pl["instagram"], st="agendado"))}}, PZ, lambda p: (200, {"data": [{"network": "instagram", "status": "scheduled"}]}))
ok("Zoho: aprovação retirada com post agendado = Cancelamento pendente com instrução", pz(r)["st"] == "cancelando" and "Cancele no Zoho" in pz(r)["erro"], r)
r = zplano({"c": {"aprov": {"on": False, "rev": 1}, "plat": {"instagram": dict(pl["instagram"], st="cancelando")}}}, PZ, lambda p: (404, {}))
ok("Zoho: post sumiu depois do pedido = cancelamento confirmado", pz(r)["st"] == "cancelado", r)
r = zplano({"c": {"aprov": APR, "aut": A, "plat": {"instagram": {"st": "enviando", "aut": "A1", "desde": iso(NOW), "tent": 1, "quando": FUT}}}}, PZ, lambda p: (200, {}))
ok("Zoho: envio em andamento não é repetido", not r["acoes"], r)
r = zplano({"c": {"aprov": APR, "aut": dict(A, em="2026-10-15T18:05:40Z")}}, {"c": dict(PZ["c"], data="2026-10-19")}, lambda p: (200, {}))
ok("Zoho: até 20/10 (agendado pela equipe, autorização legada) não envia de novo", not r["acoes"] and pz(r)["st"] == "externo", r)
r = zplano({"c": {"aprov": APR, "aut": A}}, {"c": dict(PZ["c"], data="2026-10-20")}, lambda p: (200, {}))
ok("Zoho: Pode postar novo em peça até 20/10 agenda normalmente", len(r["acoes"]) == 1 and r["acoes"][0]["tipo"] == "zoho_criar", r)
r = zplano({"c": {"aprov": APR, "aut": A, "plat": pl}}, PZ, lambda p: (200, {"data": [{"network": "instagram", "status": "unpublished", "error": {"code": 1, "message": "token expirado"}}]}))
ok("Zoho: erro da rede aparece como Falha com a mensagem", pz(r)["st"] == "falha" and "token expirado" in pz(r)["erro"], r)
r = zplano({"c": {"aprov": APR, "aut": A}}, {"c": dict(PZ["c"], data="2026-10-19")}, lambda p: (200, {}), postado=("p_c",))
ok("Zoho: publicado até 20/10 aparece como concluído (não externo)", pz(r)["st"] == "concluido" and not r["acoes"], r)

# 13b. Zoho: envio incerto (enviando sem id) -> procura na lista do Zoho antes de reenviar
MS = int(fw.q_dt(FUT).timestamp() * 1000)
ENV = {"c": {"aprov": APR, "aut": A, "plat": {"instagram": {"st": "enviando", "aut": "A1", "desde": iso(NOW - dt.timedelta(minutes=60)), "tent": 1, "quando": FUT}}}}
def lista(itens, chamadas=None):
    pags = {"/posts/schedules": (200, {"cursor": 10, "data": [{"post_id": "111", "schedule_time": MS + 3600000, "messages": [{"message": TXT}]}]}),
            "/posts/schedules?cursor=10": (200, {"cursor": None, "data": itens})}
    def f(p):
        if chamadas is not None: chamadas.append(p)
        return pags.get(p, (200, {}))
    return f
ch = []
r = zplano(ENV, PZ, lista([{"post_id": "777", "schedule_time": MS, "messages": [{"message": TXT + " #imigracao", "channels": [{"network": "instagram"}]}]}], ch))
ok("Zoho: post já existente (mesmo horário e começo do texto) é adotado, sem reenviar", not r["acoes"] and pz(r)["st"] == "enviado" and pz(r)["ext"]["id"] == "777" and "/posts/schedules?cursor=10" in ch, r)
r = zplano(ENV, PZ, lista([{"post_id": "777", "schedule_time": MS, "messages": [{"message": "Outro post qualquer"}]}]))
ok("Zoho: nada parecido na lista -> nova tentativa numerada", len(r["acoes"]) == 1 and r["acoes"][0]["tipo"] == "zoho_criar" and r["acoes"][0]["claim"]["plat"]["instagram"]["tent"] == 2, r)
r = zplano(dict(ENV, d={"aprov": APR, "plat": {"instagram": {"st": "agendado", "ext": {"id": "777"}, "quando": FUT}}}), PZ,
           lambda p: lista([{"post_id": "777", "schedule_time": MS, "messages": [{"message": TXT, "channels": [{"network": "instagram"}]}]}])(p) if "schedules" in p else (200, {"data": [{"network": "instagram", "status": "scheduled"}]}))
ok("Zoho: post que já pertence a outra peça não é adotado", any(a["tipo"] == "zoho_criar" and a["doc"] == "c" for a in r["acoes"]), r)
r = zplano(ENV, PZ, lambda p: (500, {}) if "schedules" in p else (200, {}))
ok("Zoho: lista indisponível -> não reenvia nesta rodada", not r["acoes"] and not pz(r), r)

# 13d. Zoho: Instagram + Facebook = um agendamento por rede (Facebook = "facebookpage")
def canal(a): return a["corpo"]["post"]["messages"][0]["channels"][0]["network"]
AF = aut(redes=("instagram", "facebook"))
r = zplano({"c": {"aprov": APR, "aut": AF}}, PZ, lambda p: (200, {}))
ok("Zoho: IG+FB gera duas ações zoho_criar separadas", sorted((a["redes"][0], canal(a)) for a in r["acoes"] if a["tipo"] == "zoho_criar") == [("facebook", "facebookpage"), ("instagram", "instagram")], r)
PIG = {"instagram": {"st": "agendado", "aut": "A1", "ext": {"id": "99"}, "quando": FUT, "rev": 1, "sync": iso(NOW)}}
r = zplano({"c": {"aprov": APR, "aut": AF, "plat": PIG}}, PZ, lambda p: (200, {"data": [{"network": "instagram", "status": "scheduled"}]}))
ok("Zoho: Facebook acrescentado a post já agendado no IG cria só o do Facebook", [(a["redes"], canal(a)) for a in r["acoes"]] == [(["facebook"], "facebookpage")], r)
def pzr(r, rede):
    for m in r["marcas"]:
        if m["patch"].get("plat", {}).get(rede): return m["patch"]["plat"][rede]
    return {}
ENVF = {"c": {"aprov": APR, "aut": AF, "plat": {k: {"st": "enviando", "aut": "A1", "desde": iso(NOW - dt.timedelta(minutes=60)), "tent": 1, "quando": FUT} for k in ("instagram", "facebook")}}}
dois = [{"post_id": "701", "schedule_time": MS, "messages": [{"message": TXT, "channels": [{"network": "instagram"}]}]},
        {"post_id": "702", "schedule_time": MS, "messages": [{"message": TXT, "channels": [{"network": "facebookpage"}]}]}]
r = zplano(ENVF, PZ, lista(dois))
ok("Zoho: adoção respeita a rede (IG pega o post do IG, FB o do FB)", not r["acoes"] and pzr(r, "instagram").get("ext", {}).get("id") == "701" and pzr(r, "facebook").get("ext", {}).get("id") == "702", r)
r = zplano(ENVF, PZ, lista(dois[:1]))
ok("Zoho: só o post do IG existe -> FB não adota o do IG e é reenviado", pzr(r, "instagram").get("ext", {}).get("id") == "701" and [a["redes"] for a in r["acoes"]] == [["facebook"]], r)
r = zplano(ENVF, PZ, lista([{"post_id": "703", "schedule_time": MS, "messages": [{"message": TXT}]}]))
ok("Zoho: lista sem a rede do post -> não adota nem reenvia (evita trocar IG por FB)", not r["acoes"] and not pzr(r, "instagram") and not pzr(r, "facebook"), r)

# 13c. Zoho: token de acesso pedido uma vez e reaproveitado por 50 min (entre processos, via $CENTRAIS_TMP)
import io, urllib.request, time
def novo_fw():
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
tmpd = tempfile.mkdtemp()
os.environ.update(CENTRAIS_TMP=tmpd, ZOHO_CLIENT_ID="cid", ZOHO_CLIENT_SECRET="sec", ZOHO_REFRESH_TOKEN="ref")
pedidos = []
def fake_urlopen(req, timeout=None):
    pedidos.append(req.full_url)
    return io.BytesIO(json.dumps({"access_token": "T%d" % len(pedidos)}).encode())
urlopen0, urllib.request.urlopen = urllib.request.urlopen, fake_urlopen
ZC = fw.CFG["centrais"]["cunha"]["zoho"]
toks = [novo_fw().zoho_token(ZC) for _ in range(12)]   # 12 processos (plano + 11 zoho-criar) na mesma rodada
arq = os.path.join(tmpd, "zoho_token.json")
ok("Zoho: 12 chamadas na rodada = 1 pedido de token", len(pedidos) == 1 and set(toks) == {"T1"} and oct(os.stat(arq).st_mode & 0o777) == "0o600", {"pedidos": pedidos, "toks": toks})
j = json.load(open(arq)); j["em"] = time.time() - 51 * 60; json.dump(j, open(arq, "w"))
t = novo_fw().zoho_token(ZC)
ok("Zoho: token com mais de 50 min é renovado", len(pedidos) == 2 and t == "T2", {"pedidos": pedidos, "t": t})
m = novo_fw(); env = []
m.zoho_req = lambda z, tok, met, path, body=None: (env.append(tok), (401, {}) if tok == "T2" else (200, {"data": [{"success": True, "post_id": "555"}]}))[1]
af = os.path.join(tmpd, "acao.json")
json.dump({"redes": ["instagram"], "quando": FUT, "aut": "A1", "esperado": {"rev": 1}, "corpo": {}, "claim": {"plat": {"instagram": {"tent": 1}}}}, open(af, "w"))
res = m.zoho_criar("cunha", af)
ok("Zoho: token recusado (401) é renovado uma vez e o envio segue", res["ok"] and env == ["T2", "T3"] and len(pedidos) == 3, {"res": res, "env": env})
urllib.request.urlopen = urlopen0
shutil.rmtree(tmpd)

# 14. Metricool fora do ar: mantém aguardando, não marca falha nas peças
r = roda("marcelao", {"x": {"aprov": APR, "aut": aut(), "plat": pl}}, None, PEC, ["--sem-conexao", "timeout"])
ok("Sem resposta da plataforma: nada muda nas peças", not r["acoes"] and not r["marcas"] and r["status_plataforma"]["ok"] is False, r)

# 14. Zoho: post agendado fora do fluxo com hora diferente da Central (caso 16/10: data sem hora saiu à meia-noite)
import datetime as _dt
fw2 = novo_fw() if "novo_fw" in dir() else fw
FUTMS = lambda q: int(_dt.datetime.strptime(q, "%Y-%m-%dT%H:%M").replace(tzinfo=fw2.SP).timestamp() * 1000)
LEG = "Legenda da peça com texto longo o bastante para identificar o post no Zoho."
PH = {"h": {"tipo": "post", "rev": 1, "data": "2026-12-02", "hora": "12h", "legenda": LEG}}
ag = [{"post_id": "900", "schedule_time": FUTMS("2026-12-02T00:00"), "messages": [{"message": "TITULO\n" + LEG}]},
      {"post_id": "901", "schedule_time": FUTMS("2026-12-02T08:00"), "messages": [{"message": "Reel sem peça na Central"}]}]
av = []
r = fw2.zoho_conferir_horarios(fw2.CFG["centrais"]["cunha"], PH, {"h": {"aprov": APR}}, ag, set(), av)
ok("Zoho: hora diferente da Central só avisa, nunca muda o que já está agendado (regra 8, 21/10); reel sem peça não é tocado",
   not r and len(av) == 1 and "900" not in av[0] and "h:" in av[0], (r, av))
av = []
r = fw2.zoho_conferir_horarios(fw2.CFG["centrais"]["cunha"], PH, {"h": {"aprov": APR}}, [dict(ag[0], schedule_time=FUTMS("2026-12-03T14:00"))], set(), av)
ok("Zoho: data diferente da Central só gera aviso", not r and av, (r, av))
r = fw2.zoho_conferir_horarios(fw2.CFG["centrais"]["cunha"], PH, {"h": {"aprov": APR}}, ag, {"900"}, [])
ok("Zoho: post do próprio fluxo não entra na conferência", not r, r)

# 15. Instagram com legenda acima de 2.200 (regra do Deilson, 30/10): corrige sozinho em vez de falhar
par = lambda i: f"Parágrafo {i} " + "texto do corpo " * 12
PL = {"legenda": "\n\n".join(["Gancho do post."] + [par(i) for i in range(14)] + ["Salve e mande para quem precisa.", "Conteúdo informativo. Cada caso migratório exige análise individual."]), "hashtags": "#a #b"}
t, como = fw2.texto_ig(PL["legenda"] + "\n\n#a #b", PL)
ok("Instagram: legenda longa é encurtada em parágrafos inteiros, com gancho, aviso legal e hashtags",
   como == "ajustada" and fw2._tam(t) <= 2200 and t.startswith("Gancho") and "Conteúdo informativo" in t and t.endswith("#a #b") and "Salve" not in t, (como, fw2._tam(t)))
t, como = fw2.texto_ig("X" * 2300, {"legenda": "Legenda nova curta.", "hashtags": "#a"})
ok("Instagram: snap longo usa a legenda atual da peça quando ela cabe", como == "atual" and t == "Legenda nova curta.\n\n#a", (como, t))
ok("Instagram: legenda que cabe não muda", fw2.texto_ig("curta", PL) == ("curta", None), None)

print("\n%d cenário(s) com falha" % len(falhas) if falhas else "\nTodos os cenários passaram.")
sys.exit(1 if falhas else 0)
