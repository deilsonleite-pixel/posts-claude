#!/usr/bin/env python3
"""Rotina das Centrais (Marcelão / Cunha Law): decide o que precisa ir para a plataforma.

Não fala com a internet. Quem chama o Metricool, o Drive e o banco da Central é a tarefa
agendada do Claude (ver ../tarefas/fila.md); este script só lê os arquivos baixados e diz,
de forma determinística, o que fazer, para que duas rodadas nunca dupliquem um agendamento.

Uso:
  fluxo_worker.py plano   <central> <dump_dir> [--posts posts.json | --sem-conexao "msg"]
  fluxo_worker.py midia   <central> <dump_dir> <doc_id>          copia a mídia da peça para o Drive
  fluxo_worker.py limpar  <central> <dump_dir> <doc_id> [--executar]   arquivos exclusivos da peça excluída
  fluxo_worker.py migrar  <central> <dump_dir> [--posts posts.json]    cria fluxo/<id> para peças antigas
  fluxo_worker.py zoho-hora <central> <acao.json>                     troca só a hora de um post do Zoho (só quando o Deilson pedir)
  fluxo_worker.py midia-cunha cunha <doc> <atualizado> <arquivos...>   sobe a arte da Central para cunhalaw/<doc>/ (JPG)

dump_dir contém pecas/*.json e fluxo/*.json (ArtifactData list com out_dir).
posts.json é a resposta crua de getScheduledPosts do Metricool ({"data":[...]}) ou a lista.
Datas: tudo em America/Sao_Paulo ("AAAA-MM-DDTHH:MM").
"""
import json, os, re, sys, glob, shutil, subprocess, time, unicodedata, datetime as dt
from zoneinfo import ZoneInfo

AQUI = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(AQUI, "config.json")) if os.path.exists(os.path.join(AQUI, "config.json")) else open(os.path.join(AQUI, "..", "config.json")))
SP = ZoneInfo("America/Sao_Paulo")
AGORA = dt.datetime.now(SP)
MAX_TENT = 3
ZOHO_ESPERAS = (10, 30, 60, 120, 300)   # segundos entre tentativas de falha temporária (cerca de 9 min no total)
ZOHO_TEMPORARIO = (0, 408, 429, 500, 502, 503, 504)
ESPERA_ENVIO_MIN = 20          # "enviando" mais velho que isso = resultado incerto: consultar antes de repetir
SYNC_REFRESH_H = 6             # reescreve "sync" de um agendado confirmado no máximo a cada 6 h

def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def q_dt(q):
    return dt.datetime.strptime(q[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=SP)

def parse_iso(s):
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def norm(s):
    s = unicodedata.normalize("NFC", s or "")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def nfc(s):
    return unicodedata.normalize("NFC", s)

def load_dir(d):
    out = {}
    for f in glob.glob(os.path.join(d, "*.json")):
        try:
            out[os.path.basename(f)[:-5]] = json.load(open(f))
        except Exception:
            pass
    # Peças publicadas direto pela API do Instagram (16/10) gravaram plat.<rede>.ext como o link do post (texto)
    for d_ in out.values():
        plat = d_.get("plat") if isinstance(d_, dict) else None
        for e in (plat or {}).values() if isinstance(plat, dict) else ():
            if isinstance(e, dict) and isinstance(e.get("ext"), str):
                e["ext"] = {"url": e["ext"]}
    return out

def load_posts(path):
    if not path:
        return []
    d = json.load(open(path))
    if isinstance(d, dict):
        d = d.get("data", [])
    return d or []

def rev_of(doc_id, pecas, fx):
    if doc_id in pecas:
        return int(pecas[doc_id].get("rev") or 1)
    return int((fx or {}).get("crev") or 1)

def aprov_ok(f, rev):
    a = f.get("aprov") or {}
    return bool(a.get("on")) and int(a.get("rev") or 1) == rev

def aut_ok(f, rev):
    a = f.get("aut")
    return a if a and aprov_ok(f, rev) and int(a.get("rev") or 0) == rev and a.get("redes") else None

# ---------------- Metricool ----------------
IG_TYPE = {"post": "POST", "carrossel": "POST", "reel": "REEL"}
FB_TYPE = {"post": "POST", "carrossel": "POST", "reel": "REEL"}

def post_dt(p):
    pd = p.get("publicationDate") or {}
    s, tz = pd.get("dateTime", ""), pd.get("timezone") or "America/Sao_Paulo"
    try:
        d = dt.datetime.strptime(s[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=ZoneInfo(tz))
        return d.astimezone(SP).strftime("%Y-%m-%dT%H:%M")
    except Exception:
        return ""

def post_redes(p):
    return {pr.get("network"): pr for pr in (p.get("providers") or [])}

def find_post(posts, uuid):
    for p in posts:
        if str(p.get("uuid")) == str(uuid):
            return p
    return None

def match_post(posts, quando, texto, usados):
    """Agendamento já existente para este conteúdo (mesmo horário + mesmo começo de texto)."""
    t = norm(texto)[:60]
    for p in posts:
        if str(p.get("uuid")) in usados or p.get("draft"):
            continue
        if post_dt(p) == quando and t and norm(p.get("text"))[:60] == t:
            return p
    return None

def build_info(snap, redes, quando, midia_urls, formato):
    info = {
        "autoPublish": True, "draft": False, "descendants": [], "firstCommentText": "",
        "hasNotReadNotes": False, "media": midia_urls, "mediaAltText": [None] * len(midia_urls),
        "providers": [{"network": r} for r in redes], "shortener": False,
        "smartLinkData": {"ids": []}, "text": (snap.get("yt_texto") or snap.get("texto", "")) if redes == ["youtube"] else snap.get("texto", ""),
        "publicationDate": {"dateTime": quando + ":00", "timezone": "America/Sao_Paulo"},
    }
    if "instagram" in redes:
        info["instagramData"] = {"type": IG_TYPE.get(formato, "POST"), "showReelOnFeed": True, "isAiGenerated": False, "collaborators": []}
    if "facebook" in redes:
        info["facebookData"] = {"type": FB_TYPE.get(formato, "POST")}
    if "youtube" in redes:
        info["youtubeData"] = {"title": snap.get("yt_titulo") or snap.get("titulo", "")[:95], "type": "short" if formato == "reel" else "video",
                               "privacy": "public", "madeForKids": False, "tags": snap.get("yt_tags") or []}
    return info

def info_from_post(p, **over):
    keep = ["autoPublish", "descendants", "draft", "firstCommentText", "hasNotReadNotes", "media", "mediaAltText", "shortener",
            "smartLinkData", "text", "publicationDate", "twitterData", "facebookData", "instagramData", "youtubeData", "tiktokData"]
    info = {k: p[k] for k in keep if k in p}
    info["providers"] = [{"network": pr.get("network")} for pr in p.get("providers") or []]
    info.setdefault("smartLinkData", {"ids": []})
    info.setdefault("descendants", [])
    info.update(over)
    return info

def verifica(p, quando, rede, snap, formato):
    """Confere o registro na plataforma. Retorna lista de divergências (vazia = agendado de verdade)."""
    erros = []
    if p.get("draft"):
        erros.append("está como rascunho")
    if p.get("autoPublish") is False:
        erros.append("está como notificação (sem publicação automática)")
    if post_dt(p) != quando:
        erros.append(f"horário na plataforma {post_dt(p) or '?'} ≠ {quando}")
    pr = post_redes(p).get(rede)
    if not pr:
        erros.append(f"{rede} não está entre as redes do agendamento")
    elif (pr.get("status") or "").upper() in ("ERROR", "FAILED", "REJECTED"):
        erros.append(f"{rede}: {pr.get('detailedStatus') or pr.get('status')}")
    if snap.get("texto") is not None and norm(p.get("text")) != norm(snap.get("texto")):
        erros.append("legenda diferente da versão autorizada")
    n = snap.get("midia_n")
    if n is not None and len(p.get("media") or []) != n:
        erros.append(f"{len(p.get('media') or [])} mídia(s) na plataforma, esperado {n}")
    if rede == "instagram":
        tipo = ((p.get("instagramData") or {}).get("type") or "POST").upper()
        if tipo != IG_TYPE.get(formato, "POST"):
            erros.append(f"formato {tipo} ≠ {IG_TYPE.get(formato)}")
    return erros

# ---------------- plano ----------------
def plat_entry(st, **kw):
    e = {"st": st, "ext": None, "quando": None, "rev": None, "aut": None, "sync": None, "erro": None, "erro_cod": None, "desde": None, "tent": 0}
    e.update(kw)
    return e

def plano(central, dump, posts_path=None, sem_conexao=None):
    c = CFG["centrais"][central]
    pecas = load_dir(os.path.join(dump, "pecas"))
    fluxo = load_dir(os.path.join(dump, "fluxo"))
    posts = load_posts(posts_path)
    conectadas = set(c.get("redes_conectadas") or [])
    nome = c["plataforma_nome"]
    acoes, marcas, avisos = [], [], []
    usados = set()
    for f in fluxo.values():
        for e in (f.get("plat") or {}).values():
            if e and e.get("ext") and e["ext"].get("uuid"):
                usados.add(str(e["ext"]["uuid"]))

    if c["plataforma"] == "instagram_rotina":
        return plano_rotina_instagram(central, c, pecas, fluxo, dump)
    if c["plataforma"] == "zoho":
        return plano_zoho(central, c, pecas, fluxo, dump, sem_conexao)
    if c["plataforma"] == "zoho":
        status = {"ok": False, "msg": c.get("zoho_msg"), "acao": c.get("zoho_acao"), "em": now_iso(), "plataforma": nome}
    elif sem_conexao:
        status = {"ok": False, "msg": f"O {nome} não respondeu: {sem_conexao}", "acao": "A rotina tenta de novo em 10 min. Se continuar, reconecte o Metricool nos conectores do Claude.", "em": now_iso(), "plataforma": nome}
    else:
        status = {"ok": True, "msg": "", "acao": "", "em": now_iso(), "plataforma": nome, "redes": sorted(conectadas)}
    plataforma_ok = status["ok"]

    for doc, f in sorted(fluxo.items()):
        rev = rev_of(doc, pecas, f)
        plat = f.get("plat") or {}
        exc = f.get("excluido")
        aut = None if exc else aut_ok(f, rev)
        snap = (aut or {}).get("snap") or {}
        formato = snap.get("formato") or (pecas.get(doc, {}).get("tipo")) or ("post" if doc in pecas else "reel")
        want = {}
        if aut:
            for r, q in aut["redes"].items():
                want[r] = q
        patch_plat = {}

        def mark(r, e, motivo):
            patch_plat[r] = e
            avisos.append(f"{doc} · {r}: {motivo}")

        # 1) o que já existe na plataforma para este item
        grupos_exist = {}   # uuid -> {post, redes:set}
        for r, e in plat.items():
            if not e:
                continue
            uuid = (e.get("ext") or {}).get("uuid")
            if uuid and e.get("st") in ("agendado", "enviado", "enviando", "cancelando", "divergente"):
                grupos_exist.setdefault(str(uuid), {"post": find_post(posts, uuid), "redes": set(), "e": e})["redes"].add(r)

        if not plataforma_ok:
            if c["plataforma"] == "zoho":
                for r, q in want.items():
                    e = plat.get(r) or {}
                    if not (e.get("st") == "falha" and e.get("aut") == aut["id"] and e.get("erro_cod") == "sem_conexao"):
                        mark(r, plat_entry("falha", quando=q, rev=rev, aut=aut["id"], erro=f"{nome} sem conexão: nada foi enviado. {c.get('zoho_acao')}", erro_cod="sem_conexao", desde=now_iso()), "zoho sem conexão")
            if patch_plat:
                marcas.append({"doc": doc, "patch": {"plat": patch_plat}})
            continue

        # 2) agendamentos existentes que não deveriam existir (ou mudaram) -> cancelar / ajustar
        for uuid, g in grupos_exist.items():
            p = g["post"]
            e = g["e"]
            if p is None:
                # sumiu da lista de agendados
                q = e.get("quando")
                if e.get("st") == "enviando":
                    continue  # tratado abaixo (consulta antes de repetir)
                for r in g["redes"]:
                    if q and q_dt(q) <= AGORA + dt.timedelta(minutes=2):
                        mark(r, plat_entry("concluido", ext=e.get("ext"), quando=q, rev=e.get("rev"), aut=e.get("aut"), sync=now_iso()), "saiu da fila no horário")
                    elif e.get("st") == "cancelando":
                        mark(r, plat_entry("cancelado", ext=e.get("ext"), quando=q, rev=e.get("rev"), sync=now_iso()), "cancelamento confirmado (não está mais na fila)")
                    else:
                        mark(r, plat_entry("cancelado_ext", ext=e.get("ext"), quando=q, rev=e.get("rev"), sync=now_iso()), "sumiu da plataforma antes do horário")
                        if aut and r in want:
                            want.pop(r, None)
                            marcas.append({"doc": doc, "patch": {"aut": None}, "evento": ("cancelado_ext", f"{r}: agendamento removido direto no {nome}; autorização encerrada")})
                continue
            redes_post = set(post_redes(p).keys())
            quer = {r for r in redes_post if want.get(r) == post_dt(p)} if not p.get("draft") else set()
            if p.get("draft"):
                for r in g["redes"]:
                    if e.get("st") == "cancelando" or r not in want:
                        mark(r, plat_entry("cancelado", ext=e.get("ext"), quando=e.get("quando"), rev=e.get("rev"), sync=now_iso(), erro="Ficou como rascunho no Metricool (dá para apagar lá)."), "cancelado (rascunho)")
                    else:
                        mark(r, plat_entry("cancelado_ext", ext=e.get("ext"), quando=e.get("quando"), rev=e.get("rev"), sync=now_iso()), "virou rascunho na plataforma")
                        want.pop(r, None)
                        marcas.append({"doc": doc, "patch": {"aut": None}, "evento": ("cancelado_ext", f"{r}: agendamento virou rascunho no {nome}; autorização encerrada")})
                continue
            if not quer:
                acoes.append({"tipo": "metricool_cancelar", "doc": doc, "uuid": uuid, "id": p.get("id"),
                              "blogId": c.get("metricool_blog_id"), "info": info_from_post(p, draft=True),
                              "claim": {"plat": {r: dict(e, st="cancelando", desde=now_iso()) for r in redes_post if r in plat}},
                              "motivo": "não está mais autorizado" if not aut else "rede/horário mudou"})
                continue
            if quer != redes_post:
                novas = sorted(quer)
                acoes.append({"tipo": "metricool_atualizar", "doc": doc, "uuid": uuid, "id": p.get("id"), "blogId": c.get("metricool_blog_id"),
                              "info": info_from_post(p, providers=[{"network": r} for r in novas]),
                              "claim": {"plat": {r: dict(plat.get(r) or {}, st="cancelando", desde=now_iso()) for r in redes_post - quer if r in plat}},
                              "motivo": "tirar redes que não estão mais autorizadas: " + ", ".join(sorted(redes_post - quer))})
            # conferir cada rede autorizada deste post
            for r in quer:
                erros = verifica(p, want[r], r, snap, formato)
                e0 = plat.get(r) or {}
                if not erros:
                    last = parse_iso(e0.get("sync") or "")
                    if not (e0.get("st") == "agendado" and e0.get("aut") == aut["id"] and e0.get("quando") == want[r] and last and (dt.datetime.now(dt.timezone.utc) - last).total_seconds() < SYNC_REFRESH_H * 3600):
                        mark(r, plat_entry("agendado", ext={"uuid": uuid, "id": p.get("id"), "url": (e0.get("ext") or {}).get("url")}, quando=want[r], rev=rev, aut=aut["id"], sync=now_iso(), tent=e0.get("tent", 0)), "agendamento confirmado")
                        if e0.get("st") != "agendado" or e0.get("aut") != aut["id"]:
                            marcas.append({"doc": doc, "patch": {}, "evento": ("agendado", f"{r} · {want[r]} · {nome} uuid {uuid}")})
                    want.pop(r, None)
                else:
                    if (e0.get("tent") or 0) >= MAX_TENT:
                        mark(r, plat_entry("falha", ext={"uuid": uuid, "id": p.get("id")}, quando=want[r], rev=rev, aut=aut["id"], erro="Registro na plataforma não confere: " + "; ".join(erros), erro_cod="divergente", sync=now_iso(), tent=e0.get("tent")), "divergente após tentativas")
                    else:
                        acoes.append({"tipo": "metricool_atualizar", "doc": doc, "uuid": uuid, "id": p.get("id"), "blogId": c.get("metricool_blog_id"),
                                      "info": build_info(snap, sorted(quer), want[r], [], formato), "precisa_midia": True, "redes": sorted(quer), "quando": want[r], "snap": snap, "formato": formato,
                                      "claim": {"plat": {rr: dict(plat.get(rr) or {}, st="enviando", aut=aut["id"], desde=now_iso(), tent=(plat.get(rr) or {}).get("tent", 0) + 1) for rr in quer}},
                                      "motivo": "corrigir: " + "; ".join(erros)})
                    want.pop(r, None)
                    break

        # 3) redes autorizadas ainda sem agendamento -> adotar existente ou criar
        grupos = {}
        for r, q in want.items():
            grupos.setdefault(q, []).append(r)
        for q, redes in sorted(grupos.items()):
            redes = sorted(redes)
            fora = [r for r in redes if r not in conectadas]
            for r in fora:
                e0 = plat.get(r) or {}
                if not (e0.get("st") == "falha" and e0.get("aut") == aut["id"] and e0.get("erro_cod") == "rede_nao_conectada"):
                    mark(r, plat_entry("falha", quando=q, rev=rev, aut=aut["id"], erro=f"{c['redes'].get(r, r)} não está conectado ao {nome}. Conecte o perfil no {nome} para esta rede poder ser agendada.", erro_cod="rede_nao_conectada", desde=now_iso()), "rede não conectada")
            redes = [r for r in redes if r in conectadas]
            if not redes:
                continue
            if q_dt(q) <= AGORA + dt.timedelta(minutes=5):
                for r in redes:
                    e0 = plat.get(r) or {}
                    if e0.get("erro_cod") != "horario_passou" or e0.get("aut") != aut["id"]:
                        mark(r, plat_entry("falha", quando=q, rev=rev, aut=aut["id"], erro=f"O horário {q.replace('T', ' ')} já passou sem confirmação. Defina nova data nos Detalhes: nada sai imediatamente.", erro_cod="horario_passou", desde=now_iso()), "horário passou")
                continue
            adot = match_post(posts, q, snap.get("texto", ""), usados)
            if adot and set(redes) <= set(post_redes(adot).keys()):
                usados.add(str(adot.get("uuid")))
                for r in redes:
                    e0 = plat.get(r) or {}
                    erros = verifica(adot, q, r, snap, formato)
                    if erros:
                        mark(r, plat_entry("enviado", ext={"uuid": str(adot.get("uuid")), "id": adot.get("id")}, quando=q, rev=rev, aut=aut["id"], desde=now_iso(), tent=e0.get("tent", 0)), "encontrado na plataforma; será corrigido na próxima conferência")
                    else:
                        mark(r, plat_entry("agendado", ext={"uuid": str(adot.get("uuid")), "id": adot.get("id")}, quando=q, rev=rev, aut=aut["id"], sync=now_iso(), tent=e0.get("tent", 0)), "agendamento existente adotado e conferido")
                marcas.append({"doc": doc, "patch": {}, "evento": ("agendado", f"{', '.join(redes)} · {q} · já existia no {nome} (uuid {adot.get('uuid')}); nenhum envio repetido")})
                continue
            # já mandamos e ainda não apareceu?
            pend = [plat.get(r) or {} for r in redes]
            enviando = [e for e in pend if e.get("st") in ("enviando", "enviado") and e.get("aut") == aut["id"]]
            if enviando:
                idade = min(((dt.datetime.now(dt.timezone.utc) - (parse_iso(e.get("desde") or "") or dt.datetime.now(dt.timezone.utc))).total_seconds() / 60) for e in enviando)
                tent = max(e.get("tent") or 0 for e in enviando)
                if idade < ESPERA_ENVIO_MIN:
                    continue  # aguardando: não repetir
                if tent >= MAX_TENT:
                    for r in redes:
                        mark(r, plat_entry("falha", quando=q, rev=rev, aut=aut["id"], erro=f"{tent} envios sem o agendamento aparecer no {nome}. Confira o {nome} e depois retire e dê a aprovação de novo para reenviar.", erro_cod="sem_confirmacao", desde=now_iso(), tent=tent), "sem confirmação após tentativas")
                    continue
            else:
                tent = max((e.get("tent") or 0) for e in pend) if pend else 0
                if any(e.get("st") == "falha" and e.get("aut") == aut["id"] for e in pend):
                    continue  # falha registrada para esta autorização: espera ação do usuário
                if any(e.get("aut") != aut["id"] for e in pend):
                    tent = 0
            acoes.append({"tipo": "metricool_criar", "doc": doc, "blogId": c.get("metricool_blog_id"), "redes": redes, "quando": q,
                          "snap": snap, "formato": formato, "aut": aut["id"], "precisa_midia": True,
                          "info": build_info(snap, redes, q, [], formato),
                          "claim": {"plat": {r: plat_entry("enviando", quando=q, rev=rev, aut=aut["id"], desde=now_iso(), tent=tent + 1) for r in redes}},
                          "esperado": {"aut_id": aut["id"], "rev": rev}})
        if patch_plat:
            marcas.append({"doc": doc, "patch": {"plat": patch_plat}})

        # 4) exclusão: cancelar antes, limpar depois
        if exc and exc.get("estado") not in ("concluido",):
            ativos = [r for r, e in plat.items() if e and e.get("st") in ("agendado", "enviando", "enviado", "cancelando") and r not in patch_plat]
            ativos += [r for r, e in patch_plat.items() if e.get("st") in ("agendado", "enviando", "enviado", "cancelando")]
            publicado = any(e and e.get("st") == "concluido" for e in list(plat.values()) + list(patch_plat.values()))
            if ativos or any(a["doc"] == doc and a["tipo"] == "metricool_cancelar" for a in acoes):
                if exc.get("estado") != "cancelando":
                    marcas.append({"doc": doc, "patch": {"excluido": dict(exc, estado="cancelando", publicado=publicado)}})
            elif exc.get("estado") in ("cancelando", "pendente", "limpando", "erro"):
                acoes.append({"tipo": "limpar_arquivos", "doc": doc, "arquivos": exc.get("arquivos") or [], "publicado": publicado})

    return {"central": central, "plataforma": c["plataforma"], "agora": AGORA.strftime("%Y-%m-%dT%H:%M"),
            "status_plataforma": status, "acoes": acoes, "marcas": marcas, "avisos": avisos}

# ---------------- Cunha Law: publicação direta no Instagram por rotina do claude.ai ----------------
def _get(url):
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Cache-Control": "no-cache"}), timeout=15) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except Exception as e:
        return getattr(e, "code", 0) or 0, ""

def plano_rotina_instagram(central, c, pecas, fluxo, dump):
    """Até zoho_ate: agendado no Zoho pela equipe (sem acesso para conferir).
    Depois: a rotina do claude.ai publica no horário da peça; "agendado" = autorizado + imagens da versão certa no repositório."""
    postado = set(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(dump, "postado", "*.json")))
    nome = c["plataforma_nome"]
    marcas, avisos = [], []
    for doc, f in sorted(fluxo.items()):
        if f.get("excluido"):
            continue
        p = pecas.get(doc)
        rev = rev_of(doc, pecas, f)
        aut = aut_ok(f, rev)
        plat = f.get("plat") or {}
        e0 = plat.get("instagram") or {}
        if not aut or "instagram" not in aut["redes"]:
            if e0.get("st") in ("agendado", "externo", "enviado"):
                marcas.append({"doc": doc, "patch": {"plat": {"instagram": plat_entry("cancelado", quando=e0.get("quando"), rev=e0.get("rev"), sync=now_iso(), erro="Autorização retirada: a rotina de publicação não publica mais esta peça.")}}})
            continue
        q = aut["redes"]["instagram"]
        if "p_" + doc in postado:
            novo = plat_entry("concluido", quando=q, rev=rev, aut=aut["id"], sync=e0.get("sync") or now_iso())
        elif not p:
            continue
        elif (p.get("data") or "") <= c.get("zoho_ate", "") and doc not in (c.get("rotina_inclui") or []):
            novo = plat_entry("externo", quando=q, rev=rev, aut=aut["id"], sync=now_iso(), erro="Agendado no Zoho Social pela equipe; a Central não tem acesso ao Zoho para conferir.")
        else:
            base = c["repo_raw"] + doc + "/"
            n = len(p.get("slides") or []) or 1
            st, ver = _get(base + "versao.txt")
            ok = st == 200 and ver.strip() == (p.get("atualizado") or "").strip() and all(_get(base + f"{i:02d}.jpg")[0] == 200 for i in range(1, n + 1))
            if ok:
                novo = plat_entry("agendado", ext={"url": base, "id": c.get("rotina_publicacao")}, quando=q, rev=rev, aut=aut["id"], sync=now_iso())
            else:
                novo = plat_entry("enviado", quando=q, rev=rev, aut=aut["id"], desde=e0.get("desde") or now_iso(), erro=None)
        if any(e0.get(k) != novo.get(k) for k in ("st", "quando", "aut", "rev", "erro")):
            marcas.append({"doc": doc, "patch": {"plat": {"instagram": novo}}})
            avisos.append(f"{doc}: {novo['st']}")
    status = {"ok": True, "msg": "", "acao": "", "em": now_iso(), "plataforma": nome, "redes": ["instagram"]}
    return {"central": central, "plataforma": c["plataforma"], "agora": AGORA.strftime("%Y-%m-%dT%H:%M"), "status_plataforma": status, "acoes": [], "marcas": marcas, "avisos": avisos}

# ---------------- Cunha Law: Zoho Social (API v2) ----------------
# Credenciais só no ambiente da nuvem "Cunha Law.": ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN.
# A API documenta criar agendamento (POST /posts/schedules) e consultar status por rede (GET /posts/publish/{post_id});
# NÃO documenta listar nem cancelar agendamentos: cancelamento é pedido ao usuário no Zoho e conferido pelo status.
ZOHO_TOKEN_MIN = 50            # o token de acesso do Zoho vale 60 min; reaproveita por 50 (o Zoho limita pedidos de token)

def zoho_token_arq():
    import tempfile
    return os.path.join(os.environ.get("CENTRAIS_TMP") or os.path.join(tempfile.gettempdir(), "centrais"), "zoho_token.json")

def zoho_token(z, renovar=False):
    """Token de acesso reaproveitado na rodada inteira (plano + cada zoho-criar): guardado em $CENTRAIS_TMP/zoho_token.json."""
    import urllib.request, urllib.parse, hashlib, time
    arq = zoho_token_arq()
    cli = hashlib.sha256(os.environ["ZOHO_CLIENT_ID"].encode()).hexdigest()[:16]
    if not renovar:
        try:
            j = json.load(open(arq))
            if j.get("cli") == cli and j.get("accounts") == z["accounts"] and time.time() - float(j["em"]) < ZOHO_TOKEN_MIN * 60 and j.get("access_token"):
                return j["access_token"]
        except Exception:
            pass
    data = urllib.parse.urlencode({"refresh_token": os.environ["ZOHO_REFRESH_TOKEN"], "client_id": os.environ["ZOHO_CLIENT_ID"],
                                   "client_secret": os.environ["ZOHO_CLIENT_SECRET"], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request(z["accounts"] + "/oauth/v2/token", data=data), timeout=30) as r:
        j = json.load(r)
    if "access_token" not in j:
        raise RuntimeError("Zoho recusou o login: " + str(j.get("error")))
    try:
        os.makedirs(os.path.dirname(arq), exist_ok=True)
        tmp = arq + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump({"access_token": j["access_token"], "em": time.time(), "cli": cli, "accounts": z["accounts"]}, fh)
        os.replace(tmp, arq)
    except Exception:
        pass  # sem cache: funciona, só pede token de novo na próxima chamada
    return j["access_token"]

def zoho_req(z, tok, method, path, body=None):
    import urllib.request
    req = urllib.request.Request(z["api"] + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Zoho-oauthtoken " + tok, "portal_id": z["portal_id"], "brand_id": z["brand_id"], "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except Exception as e:
        code = getattr(e, "code", 0) or 0
        try:
            txt = e.read().decode()
        except Exception:
            txt = str(e)
        try:
            return code, json.loads(txt)
        except Exception:
            return code, {"erro": txt[:300]}

def jpeg_wh(b):
    i = 2
    while i < len(b) - 9:
        if b[i] != 0xFF:
            i += 1; continue
        m = b[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(b[i + 7:i + 9], "big"), int.from_bytes(b[i + 5:i + 7], "big")
        i += 2 + int.from_bytes(b[i + 2:i + 4], "big")
    return 1080, 1350

def zoho_midia(c, doc, p):
    """Imagens da versão autorizada no repositório (cunhalaw/<id>/NN.jpg + versao.txt == atualizado)."""
    import urllib.request
    base = c["repo_raw"] + doc + "/"
    n = len(p.get("slides") or []) or 1
    st, ver = _get(base + "versao.txt")
    if st != 200 or ver.strip() != (p.get("atualizado") or "").strip():
        return None
    out = []
    for i in range(1, n + 1):
        u = base + f"{i:02d}.jpg"
        try:
            with urllib.request.urlopen(u, timeout=30) as r:
                b = r.read()
        except Exception:
            return None
        w, h = jpeg_wh(b)
        out.append({"file_path": u, "name": f"{doc}-{i:02d}.jpg", "type": "image", "format": "jpg", "size": len(b), "width": w, "height": h})
    return out

ZOHO_MAX_PAG = 50

def zoho_agendados(z, tok):
    """Agendamentos do Zoho por GET /posts/schedules?cursor=N (sem documentação oficial; 10 por página).
    Devolve a lista completa, ou None se alguma página falhar (lista incompleta não serve para decidir reenvio)."""
    out, path, vistos = [], "/posts/schedules", set()
    for _ in range(ZOHO_MAX_PAG):
        code, js = zoho_req(z, tok, "GET", path)
        if code != 200 or not isinstance(js, dict):
            return None
        pag = js.get("data") or []
        out += pag
        cur = js.get("cursor")
        if cur in (None, "") or not pag or str(cur) in vistos:
            return out
        vistos.add(str(cur))
        path = f"/posts/schedules?cursor={cur}"
    return None

def zoho_texto(p):
    return " ".join((m.get("message") or m.get("text") or m.get("content") or "") for m in (p.get("messages") or []) if isinstance(m, dict))

def zoho_redes_do_post(x):
    """Redes citadas no item da lista (qualquer chave "network", em qualquer nível)."""
    out = set()
    if isinstance(x, dict):
        for k, v in x.items():
            if k == "network" and isinstance(v, str):
                out.add(v)
            else:
                out |= zoho_redes_do_post(v)
    elif isinstance(x, list):
        for v in x:
            out |= zoho_redes_do_post(v)
    return out

def zoho_achar(agendados, quando, texto, usados, rede_z):
    """Post já existente no Zoho para este conteúdo e esta rede (mesmo horário + mesmo começo de texto).
    Instagram e Facebook da mesma peça são posts separados com o mesmo horário e texto: só adota o da rede certa.
    Devolve (post, None), (None, None) se não existe, ou (None, motivo) se não dá para saber com segurança."""
    ms = int(q_dt(quando).timestamp() * 1000)
    t = norm(texto)[:60]
    incertos = 0
    for p in agendados:
        pid = str(p.get("post_id") or "")
        try:
            st = int(p.get("schedule_time") or 0)
        except Exception:
            continue
        if not (pid and pid not in usados and t and abs(st - ms) < 60000 and norm(zoho_texto(p)).startswith(t)):
            continue
        redes = zoho_redes_do_post(p)
        if rede_z in redes:
            return p, None
        if not redes:
            incertos += 1
    if incertos:
        return None, "há post no mesmo horário e texto, mas a lista do Zoho não diz a rede"
    return None, None

def cunha_midia_acao(doc, p):
    """Ação para a fila subir a arte da versão atual da Central para cunhalaw/<doc>/ (JPG + versao.txt = "atualizado").
    Arte nova fica nos assets da Central (pecas.arte[].id); a antiga, nos arquivos exp/<doc>/NN.png."""
    n = len(p.get("slides") or []) or 1
    arte = [a.get("id") for a in (p.get("arte") or []) if a and a.get("id")]
    return {"tipo": "cunha_midia", "doc": doc, "atualizado": p.get("atualizado") or "",
            "assets": arte if len(arte) == n else [], "arquivos": [] if len(arte) == n else [f"exp/{doc}/{i:02d}.png" for i in range(1, n + 1)]}

def limite_semana(hoje=None):
    """Último dia que o "Pode postar" agenda na hora: o domingo da semana atual. De sexta em diante, a semana
    seguinte já foi liberada pela rodada de sexta, então vale o domingo seguinte (regra do Deilson, 21/10/2026)."""
    d = (hoje or AGORA).date()
    fim = d + dt.timedelta(days=6 - d.weekday())
    if d.weekday() >= 4:
        fim += dt.timedelta(days=7)
    return fim.strftime("%Y-%m-%d")

def plano_zoho(central, c, pecas, fluxo, dump, sem_conexao=None):
    z = c["zoho"]
    nome = c["plataforma_nome"]
    postado = set(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(dump, "postado", "*.json")))
    marcas, acoes, avisos = [], [], []
    midia_doc = set()
    zl = {}   # lista de agendamentos do Zoho, buscada uma vez e só se algum envio ficou incerto
    usados_z = {str((e.get("ext") or {}).get("id")) for f in fluxo.values() for e in (f.get("plat") or {}).values() if e and (e.get("ext") or {}).get("id")}
    try:
        tok = None if sem_conexao else zoho_token(z)
    except Exception as e:
        tok, sem_conexao = None, str(e)
    if not tok:
        return {"central": central, "plataforma": "zoho", "agora": AGORA.strftime("%Y-%m-%dT%H:%M"), "acoes": [], "marcas": [], "avisos": [],
                "status_plataforma": {"ok": False, "msg": f"{nome} não respondeu: {sem_conexao}", "acao": "A rotina tenta de novo na próxima hora. Se continuar, confira as credenciais do Zoho no ambiente Cunha Law. do claude.ai.", "em": now_iso(), "plataforma": nome}}
    for doc, f in sorted(fluxo.items()):
        p = pecas.get(doc)
        rev = rev_of(doc, pecas, f)
        exc = f.get("excluido")
        aut = None if exc else aut_ok(f, rev)
        plat = f.get("plat") or {}
        want = dict(aut["redes"]) if aut else {}
        patch = {}
        # 1) o que já foi mandado ao Zoho: consultar o status de verdade
        vistos = {}
        for r, e in plat.items():
            if not e:
                continue
            pid = (e.get("ext") or {}).get("id")
            if pid and e.get("st") in ("enviado", "agendado", "cancelando", "divergente"):
                if pid not in vistos:
                    vistos[pid] = zoho_req(z, tok, "GET", f"/posts/publish/{pid}")
                code, js = vistos[pid]
                rede_z = z["redes"].get(r, r)
                linha = next((x for x in (js.get("data") or []) if x.get("network") == rede_z), None)
                stz = (linha or {}).get("status")
                quer = r in want and want[r] == e.get("quando") and e.get("aut") == (aut or {}).get("id") and e.get("rev") == rev
                if code == 404 or (code == 200 and not linha):
                    novo = plat_entry("cancelado" if e.get("st") == "cancelando" else "cancelado_ext", ext=e.get("ext"), quando=e.get("quando"), rev=e.get("rev"), sync=now_iso())
                    if novo["st"] == "cancelado_ext" and quer:
                        marcas.append({"doc": doc, "patch": {"aut": None}, "evento": ("cancelado_ext", f"{r}: agendamento não existe mais no {nome}; autorização encerrada")})
                        want.pop(r, None)
                elif stz == "published":
                    novo = plat_entry("concluido", ext=e.get("ext"), quando=e.get("quando"), rev=e.get("rev"), aut=e.get("aut"), sync=now_iso())
                    if exc:
                        marcas.append({"doc": doc, "patch": {"excluido": dict(exc, publicado=True)}})
                elif stz == "scheduled":
                    if quer:
                        novo = plat_entry("agendado", ext=e.get("ext"), quando=e.get("quando"), rev=rev, aut=aut["id"], sync=now_iso(), tent=e.get("tent", 0))
                        if e.get("st") != "agendado":
                            marcas.append({"doc": doc, "patch": {}, "evento": ("agendado", f"{r} · {e.get('quando')} · {nome} post {pid} (status scheduled)")})
                    else:
                        novo = dict(e, st="cancelando", desde=e.get("desde") if e.get("st") == "cancelando" else now_iso(),
                                    erro=f"Cancele no {nome}: Publicações › Agendadas › post de {str(e.get('quando') or '').replace('T', ' ')} (a API do Zoho não permite cancelar). A Central confere sozinha.")
                elif stz == "unpublished":
                    err = (linha or {}).get("error") or {}
                    novo = plat_entry("falha", ext=e.get("ext"), quando=e.get("quando"), rev=e.get("rev"), aut=e.get("aut"), sync=now_iso(), erro=f"{nome}: {err.get('message') or 'não publicado'}", erro_cod=str(err.get("code") or "unpublished"))
                else:
                    continue  # resposta incerta: não muda nada, confere na próxima hora
                if any(novo.get(k) != e.get(k) for k in ("st", "aut", "rev", "erro")) or (novo.get("st") == "agendado" and not e.get("sync")):
                    patch[r] = novo
                if r in want and novo["st"] in ("agendado", "concluido", "falha"):
                    want.pop(r, None)
        # 2) autorizado e ainda sem agendamento no Zoho
        if want and p:
            # peça sem data (ex.: post fixado): vale a data do "Pode postar"
            data = p.get("data") or min(want.values())[:10]
            # URGENTE (regra do Deilson, 16/10/2026): peça marcada "urgente" com Pode postar é publicada NA HORA
            # (Publicar agora: POST /posts/publish, sem schedule_time). Não mexe em nada que já está programado.
            urgente = bool(p.get("urgente")) and data == AGORA.strftime("%Y-%m-%d")
            adot_doc = set()
            texto = (aut.get("snap") or {}).get("texto") or ((p.get("legenda") or "") + ("\n\n" + p["hashtags"] if p.get("hashtags") else ""))
            for r, q in sorted(want.items()):
                e0 = plat.get(r) or {}
                if "p_" + doc in postado:
                    if e0.get("st") != "concluido" or e0.get("aut") != aut["id"]:
                        patch[r] = plat_entry("concluido", quando=q, rev=rev, aut=aut["id"], sync=now_iso())
                    continue
                # semana seguinte ou depois: espera a rodada de sexta (regra do Deilson, 21/10/2026)
                if not urgente and q[:10] > limite_semana():
                    continue
                # legado: só autorizações de antes da Central (até 15/10/2026); Pode postar novo sempre agenda
                if data <= c.get("zoho_ate", "") and doc not in (c.get("rotina_inclui") or []) and (aut.get("em") or "") < "2026-10-16":
                    if e0.get("st") != "externo" or e0.get("aut") != aut["id"]:
                        patch[r] = plat_entry("externo", quando=q, rev=rev, aut=aut["id"], sync=now_iso(), erro=f"Agendado no {nome} pela equipe antes da Central; sem identificador para conferir.")
                    continue
                if r not in c.get("redes_conectadas", []):
                    if e0.get("erro_cod") != "rede_nao_conectada":
                        patch[r] = plat_entry("falha", quando=q, rev=rev, aut=aut["id"], erro=f"{r} não está configurado na integração do {nome}.", erro_cod="rede_nao_conectada", desde=now_iso())
                    continue
                if not urgente and q_dt(q) <= AGORA + dt.timedelta(minutes=10):
                    if e0.get("erro_cod") != "horario_passou" or e0.get("aut") != aut["id"]:
                        patch[r] = plat_entry("falha", quando=q, rev=rev, aut=aut["id"], erro=f"O horário {q.replace('T', ' ')} passou sem agendamento. Defina nova data nos Detalhes: nada sai imediatamente.", erro_cod="horario_passou", desde=now_iso())
                    continue
                if e0.get("st") == "enviando" and e0.get("aut") == aut["id"]:
                    idade = (dt.datetime.now(dt.timezone.utc) - (parse_iso(e0.get("desde") or "") or dt.datetime.now(dt.timezone.utc))).total_seconds() / 60
                    if idade < 50 or (e0.get("tent") or 0) >= MAX_TENT:
                        if (e0.get("tent") or 0) >= MAX_TENT and e0.get("erro_cod") != "sem_confirmacao":
                            patch[r] = dict(e0, st="falha", erro=f"Envio ao {nome} sem resposta clara após {e0.get('tent')} tentativas. Confira no {nome} se o post existe antes de reautorizar.", erro_cod="sem_confirmacao")
                        continue
                    # resultado incerto e sem id: antes de reenviar, procura o post no Zoho (evita duplicar)
                    if "l" not in zl:
                        zl["l"] = zoho_agendados(z, tok)
                    if zl["l"] is None:
                        avisos.append(f"{doc} · {r}: lista de agendamentos do {nome} indisponível; não reenvia nesta rodada")
                        continue
                    achado, duvida = zoho_achar(zl["l"], q, texto, usados_z, z["redes"].get(r, r))
                    if duvida:
                        avisos.append(f"{doc} · {r}: {duvida}; não reenvia (confira no {nome})")
                        continue
                    if achado:
                        pid = str(achado["post_id"])
                        usados_z.add(pid)
                        patch[r] = plat_entry("enviado", ext={"id": pid, "url": "https://social.zoho.com"}, quando=q, rev=rev, aut=aut["id"], desde=now_iso(), tent=e0.get("tent") or 0)
                        marcas.append({"doc": doc, "patch": {}, "evento": ("enviado", f"{r} · {q} · já existia no {nome} (post {pid}); nenhum envio repetido")})
                        avisos.append(f"{doc} · {r}: post {pid} encontrado no {nome}; adotado em vez de reenviar")
                        continue
                if e0.get("st") == "falha" and e0.get("aut") == aut["id"]:
                    continue
                # antes de criar: se o Zoho já tem post igual (mesma rede, hora e texto), adota em vez de duplicar
                if not urgente and e0.get("st") != "enviando":
                    if "l" not in zl:
                        zl["l"] = zoho_agendados(z, tok)
                    if zl["l"] is None:
                        avisos.append(f"{doc} · {r}: lista de agendamentos do {nome} indisponível; não cria nesta rodada")
                        continue
                    # um post do Zoho pode ter IG e FB juntos (feito à mão): a mesma peça pode adotá-lo nas duas redes
                    achado, duvida = zoho_achar(zl["l"], q, texto, usados_z - adot_doc, z["redes"].get(r, r))
                    if duvida:
                        avisos.append(f"{doc} · {r}: {duvida}; não cria (confira no {nome})")
                        continue
                    if achado:
                        pid = str(achado["post_id"])
                        usados_z.add(pid)
                        adot_doc.add(pid)
                        patch[r] = plat_entry("enviado", ext={"id": pid, "url": "https://social.zoho.com"}, quando=q, rev=rev, aut=aut["id"], desde=now_iso(), tent=0)
                        marcas.append({"doc": doc, "patch": {}, "evento": ("enviado", f"{r} · {q} · já estava no {nome} (post {pid}); adotado, sem duplicar")})
                        continue
                med = zoho_midia(c, doc, p)
                if not med:
                    if e0.get("st") != "aguardando_midia":
                        patch[r] = plat_entry("aguardando_midia", quando=q, rev=rev, aut=aut["id"], desde=now_iso(), erro="Subindo as imagens desta versão; o agendamento sai logo em seguida.")
                    # Regra do Deilson (21/10/2026): nada espera rodada. A própria fila sobe a imagem da Central agora
                    # e roda o plano de novo, em vez de esperar a rotina de imagens.
                    if doc not in midia_doc:
                        midia_doc.add(doc)
                        acoes.append(cunha_midia_acao(doc, p))
                    continue
                msgs = [{"message": texto, "has_media": "image", "medias": med,
                         "channels": [{"network": z["redes"].get(r, r), "brand_id": z["brand_id"]}]}]
                if urgente:
                    corpo, endpoint = {"post": {"type": "publish", "messages": msgs}}, "/posts/publish"
                else:
                    corpo, endpoint = {"post": {"type": "schedule", "schedule_time": int(q_dt(q).timestamp() * 1000), "messages": msgs}}, "/posts/schedules"
                acoes.append({"tipo": "zoho_criar", "doc": doc, "redes": [r], "quando": q, "corpo": corpo, "aut": aut["id"],
                              "endpoint": endpoint, "agora": urgente,
                              "esperado": {"aut_id": aut["id"], "rev": rev},
                              "claim": {"plat": {r: plat_entry("enviando", quando=q, rev=rev, aut=aut["id"], desde=now_iso(), tent=(e0.get("tent") or 0) + 1 if e0.get("aut") == aut["id"] else 1)}}})
        if patch:
            marcas.append({"doc": doc, "patch": {"plat": patch}})
        if exc and exc.get("estado") != "concluido":
            ativos = [r for r, e in {**plat, **patch}.items() if e and e.get("st") in ("agendado", "enviado", "enviando", "cancelando")]
            if not ativos:
                acoes.append({"tipo": "limpar_arquivos", "doc": doc, "arquivos": exc.get("arquivos") or []})
            elif exc.get("estado") != "cancelando":
                marcas.append({"doc": doc, "patch": {"excluido": dict(exc, estado="cancelando")}})
    # 3) conferência de horário: todo post ainda agendado no Zoho tem de sair no horário da Central
    if "l" not in zl:
        zl["l"] = zoho_agendados(z, tok)
    if zl["l"] is None:
        avisos.append(f"lista de agendamentos do {nome} indisponível; conferência de horário fica para a próxima rodada")
    else:
        acoes += zoho_conferir_horarios(c, pecas, fluxo, zl["l"], usados_z, avisos)
    status = {"ok": True, "msg": "", "acao": "", "em": now_iso(), "plataforma": nome, "redes": c.get("redes_conectadas")}
    return {"central": central, "plataforma": "zoho", "agora": AGORA.strftime("%Y-%m-%dT%H:%M"), "status_plataforma": status, "acoes": acoes, "marcas": marcas, "avisos": avisos}

def hora_central(c, p):
    """Horário da peça na Central (hora de Orlando) convertido para Brasília, ou None se a peça não tem hora."""
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*h", p.get("hora") or "")
    if not (p.get("data") and m):
        return None
    tzl = ZoneInfo(c.get("fuso_legado_grade") or "America/Sao_Paulo")
    local = dt.datetime.strptime(p["data"], "%Y-%m-%d").replace(hour=int(m.group(1)), minute=int(m.group(2) or 0), tzinfo=tzl)
    return local.astimezone(SP).strftime("%Y-%m-%dT%H:%M")

def zoho_conferir_horarios(c, pecas, fluxo, agendados, usados_z, avisos):
    """Posts agendados no Zoho fora do fluxo da Central (feitos à mão ou antes da Central) não têm hora conferida pelo
    passo 1. Aqui cada um é ligado à sua peça pelo texto e, se o horário não bate com a Central (mesma data), vira
    aviso (desde 21/10/2026 nada muda sozinho no Zoho). Data diferente, peça sem hora ou texto ambíguo: só aviso.
    Origem: 16/10/2026 posts agendados com data sem hora saíram à 00:00 de Brasília."""
    acoes = []
    chaves = {}
    for doc, p in pecas.items():
        f = fluxo.get(doc) or {}
        if f.get("excluido") or not (f.get("aprov") or {}).get("on"):
            continue
        t = norm(p.get("legenda") or "")[:60]
        if len(t) >= 30:
            chaves[doc] = t
    for x in agendados:
        pid = str(x.get("post_id") or "")
        try:
            ms = int(x.get("schedule_time") or 0)
        except Exception:
            continue
        if not pid or pid in usados_z or not ms:
            continue
        atual = dt.datetime.fromtimestamp(ms / 1000, SP)
        if atual <= AGORA + dt.timedelta(minutes=15):
            continue
        texto = norm(zoho_texto(x))
        docs = [d for d, t in chaves.items() if t in texto]
        if len(docs) != 1:
            continue  # reel, post sem peça na Central ou texto que serve a mais de uma peça: não mexe
        doc = docs[0]
        p = pecas[doc]
        q = hora_central(c, p)
        de = atual.strftime("%Y-%m-%dT%H:%M")
        if not q:
            avisos.append(f"{doc}: peça sem hora na Central; o {c['plataforma_nome']} está em {de.replace('T', ' ')} (Brasília). Defina a hora na Central.")
            continue
        if q == de:
            continue
        if q[:10] != de[:10]:
            avisos.append(f"{doc}: {c['plataforma_nome']} em {de.replace('T', ' ')} e Central em {q.replace('T', ' ')} (Brasília), datas diferentes; nada foi mudado, confira no {c['plataforma_nome']}.")
            continue
        if q_dt(q) <= AGORA + dt.timedelta(minutes=15):
            avisos.append(f"{doc}: horário da Central ({q.replace('T', ' ')}) já passou; o post continua em {de.replace('T', ' ')}.")
            continue
        # Regra do Deilson (21/10/2026, item 8 do Fluxo): o que já está agendado no Zoho fica como está; ninguém muda
        # hora por conta própria. A divergência só vira aviso (zoho-hora continua existindo para quando ele pedir).
        avisos.append(f"{doc}: {c['plataforma_nome']} em {de.replace('T', ' ')} e Central em {q.replace('T', ' ')} (Brasília); nada foi mudado (regra: o que está no {c['plataforma_nome']} fica como está).")
    return acoes

def zoho_hora(central, acao_path):
    """Executa uma ação zoho_hora: lê o post do Zoho, troca só o schedule_time (mesmo texto, imagens e redes) e confere."""
    z = CFG["centrais"][central]["zoho"]
    a = json.load(open(acao_path))
    tok = zoho_token(z)
    code, js = zoho_req(z, tok, "GET", f"/posts/schedules/{a['post_id']}")
    d = (js or {}).get("data") if code == 200 else None
    if not d:
        return {"ok": False, "msg": f"post {a['post_id']} não encontrado no Zoho (HTTP {code}); nada mudou"}
    if int(d.get("schedule_time") or 0) == a["schedule_time"]:
        return {"ok": True, "msg": "já estava no horário da Central", "evento": ["hora_ok", f"{a['post_id']} · {a['para']}"]}
    msgs = [{"message": m.get("message"), "has_media": m.get("has_media") or "image",
             "medias": [{k: v for k, v in md.items() if k != "preview_url"} for md in (m.get("medias") or [])],
             "channels": [{"network": ch["network"], "brand_id": ch["brand_id"]} for ch in (m.get("channels") or [])]}
            for m in d.get("messages") or []]
    corpo = {"post": {"type": "schedule", "schedule_time": a["schedule_time"], "messages": msgs}}
    code, js = zoho_req(z, tok, "PUT", f"/posts/schedules/{a['post_id']}", corpo)
    code2, js2 = zoho_req(z, tok, "GET", f"/posts/schedules/{a['post_id']}")
    lido = int(((js2 or {}).get("data") or {}).get("schedule_time") or 0) if code2 == 200 else 0
    if lido == a["schedule_time"]:
        return {"ok": True, "evento": ["hora_corrigida", f"{a['doc']} · Zoho post {a['post_id']} · {a['de']} → {a['para']} (Brasília)"]}
    return {"ok": False, "msg": f"Zoho não confirmou a troca de hora (HTTP {code}): {str(js)[:200]}",
            "evento": ["falha", f"{a['doc']}: não consegui mudar a hora no Zoho de {a['de']} para {a['para']}; ajuste à mão"]}

def zoho_criar(central, acao_path):
    """Executa uma ação zoho_criar (depois da trava gravada pela rotina). Imprime o resultado para gravar em plat."""
    c = CFG["centrais"][central]
    z = c["zoho"]
    a = json.load(open(acao_path))
    tok = zoho_token(z)
    endpoint = a.get("endpoint") or "/posts/schedules"   # /posts/publish = Publicar agora (peça urgente)
    r0 = a["redes"][0]
    msg0 = ((a["corpo"].get("post") or {}).get("messages") or [{}])[0]
    rede_z = ((msg0.get("channels") or [{}])[0]).get("network") or r0
    # Regra do Deilson (21/10/2026): "Pode postar" tenta até agendar. Falha temporária (rede, tempo esgotado,
    # 5xx, 429) repete com espera crescente; antes de repetir uma sem resposta, confere se o post já foi criado.
    for n in range(len(ZOHO_ESPERAS) + 1):
        code, js = zoho_req(z, tok, "POST", endpoint, a["corpo"])
        if code == 401:  # token guardado foi invalidado: o post não foi criado; pede um novo e tenta uma vez
            tok = zoho_token(z, renovar=True)
            code, js = zoho_req(z, tok, "POST", endpoint, a["corpo"])
        if code not in ZOHO_TEMPORARIO or n == len(ZOHO_ESPERAS):
            break
        time.sleep(ZOHO_ESPERAS[n])
        if code != 429 and not a.get("agora"):
            lista = zoho_agendados(z, tok)
            achado, _ = zoho_achar(lista or [], a["quando"], msg0.get("message") or "", set(), rede_z)
            if achado:
                code, js = 200, {"data": [{"success": True, "post_id": achado["post_id"]}]}
                break
    item = ((js.get("data") or [{}]) or [{}])[0] if isinstance(js, dict) else {}
    ok = code == 200 and item.get("success") and item.get("post_id")
    if ok:
        e = plat_entry("enviado", ext={"id": str(item["post_id"]), "url": "https://social.zoho.com"}, quando=a["quando"], rev=a["esperado"]["rev"], aut=a["aut"], desde=now_iso(), tent=a["claim"]["plat"][r0]["tent"])
        if item.get("is_approval_needed"):
            e["erro"] = "O Zoho marcou o post como dependente de aprovação interna: aprove no Zoho para ele ficar agendado."
        modo = "publicado agora (urgente)" if a.get("agora") else a["quando"]
        return {"ok": True, "plat": {r: e for r in a["redes"]}, "evento": ["enviado", f"{', '.join(a['redes'])} · {modo} · Zoho post {item['post_id']}"]}
    if code in ZOHO_TEMPORARIO:
        return {"ok": False, "incerto": True, "avisar": True,
                "aviso": f"{a['doc']} · {', '.join(a['redes'])} · {a['quando']}: o Zoho não respondeu depois de {len(ZOHO_ESPERAS) + 1} tentativas (HTTP {code}). Rode a fila da cunha de novo; ela confere no Zoho antes de reenviar, sem duplicar.",
                "msg": f"Zoho sem resposta depois de {len(ZOHO_ESPERAS) + 1} tentativas (HTTP {code}). Deixe 'enviando'; a próxima rodada confere antes de reenviar."}
    # falha que repetir não resolve (credencial/conexão vencida, mídia ou legenda recusada): a Central mostra FALHA NO AGENDAMENTO
    msg = item.get("message") or js.get("message") or js.get("erro") or str(js)[:200]
    if code in (401, 403):
        msg = f"conexão com o Zoho recusada ({msg}). Confira as credenciais ZOHO_* do ambiente e a conexão do Instagram/Facebook no Zoho."
    e = plat_entry("falha", quando=a["quando"], rev=a["esperado"]["rev"], aut=a["aut"], desde=now_iso(), erro=f"FALHA NO AGENDAMENTO. Zoho recusou: {msg}", erro_cod=f"http_{code}", tent=a["claim"]["plat"][r0]["tent"])
    return {"ok": False, "avisar": True, "aviso": f"FALHA NO AGENDAMENTO: {a['doc']} · {', '.join(a['redes'])} · {a['quando']}. Zoho recusou: {msg}",
            "plat": {r: e for r in a["redes"]}, "evento": ["falha", f"FALHA NO AGENDAMENTO. Zoho recusou: {msg}"]}

# ---------------- mídia ----------------
def slug_of(doc):
    s = re.sub(r"^est-(reserva-|\d{4}-\d{2}-\d{2}-)", "", doc)
    return s

def simpl(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)

def arquivos_peca(central, doc, peca):
    """Arquivos finais (JPG) da peça na pasta Postagens."""
    c = CFG["centrais"][central]
    pasta = c.get("pasta_artes")
    data = (peca or {}).get("data") or ""
    if not pasta or not os.path.isdir(pasta):
        return None
    alvo = simpl(slug_of(doc))
    alvo2 = simpl((peca or {}).get("titulo") or "")
    out = []
    for f in sorted(os.listdir(pasta)):
        if f.startswith("._") or not f.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        nome = nfc(f)
        if data and not nome.startswith(data):
            continue
        resto = simpl(re.sub(r"\s\d{2}\.(jpe?g|png)$", "", nome[10:], flags=re.I).rsplit(".", 1)[0])
        if resto and (resto == alvo or resto == alvo2):
            out.append(os.path.join(pasta, f))
    return out

def video_reel(central, arq, data):
    c = CFG["centrais"][central]
    base = c.get("pasta_reels")
    if not base or not os.path.isdir(base):
        return None
    alvo = simpl(arq)
    dia = os.path.join(base, "## POSTAGEM", data[5:7], data[8:10]) if data else None
    cand = []
    for raiz in ([dia] if dia and os.path.isdir(dia) else []) + [base]:
        for p in glob.glob(os.path.join(raiz, "**", "*.mp4"), recursive=True):
            if simpl(os.path.basename(p)[:-4]) == alvo:
                cand.append(p)
        if cand:
            break
    return cand[:1]

def midia(central, dump, doc):
    """Publica a mídia final da peça no repositório GitHub de mídia e devolve URLs públicas (raw)."""
    pecas = load_dir(os.path.join(dump, "pecas"))
    fluxo = load_dir(os.path.join(dump, "fluxo"))
    f = fluxo.get(doc, {})
    snap = ((f.get("aut") or {}).get("snap")) or {}
    c = CFG["centrais"][central]
    m = c.get("midia") or {}
    if doc in pecas:
        locais = arquivos_peca(central, doc, pecas[doc])
    else:
        locais = video_reel(central, snap.get("video") or snap.get("titulo", ""), snap.get("data") or "")
    if locais is None:
        return {"ok": False, "erro": "Disco das artes/vídeos não está conectado.", "erro_cod": "disco"}
    if not locais:
        return {"ok": False, "erro": "Arquivo final da peça não encontrado na pasta de artes/vídeos.", "erro_cod": "sem_arquivo"}
    n = snap.get("midia_n")
    if n and len(locais) != n and doc in pecas:
        return {"ok": False, "erro": f"Achei {len(locais)} arquivo(s) final(is), mas a peça autorizada tem {n}.", "erro_cod": "midia_divergente", "locais": locais}
    repo, clone = m.get("repo"), os.path.expanduser(m.get("clone_local") or "")
    if not repo or not clone or not os.path.isdir(os.path.join(clone, ".git")):
        return {"ok": False, "erro": "Hospedagem de mídia no GitHub indisponível nesta rodada (a rotina na nuvem não conseguiu enviar ao repositório posts-claude). Nada foi enviado.", "erro_cod": "midia_nao_configurada"}
    pasta = os.path.join(m.get("pasta") or central, doc)
    os.makedirs(os.path.join(clone, pasta), exist_ok=True)
    rel = []
    for i, p in enumerate(locais, 1):
        nome = f"{i:02d}{os.path.splitext(p)[1].lower()}"
        dst = os.path.join(clone, pasta, nome)
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(p):
            shutil.copy2(p, dst)
        rel.append(os.path.join(pasta, nome))
    g = lambda *a: subprocess.run(["git", "-C", clone] + list(a), capture_output=True, text=True)
    g("add", "--", *rel)
    if g("diff", "--cached", "--quiet").returncode != 0:
        r = g("commit", "-m", f"midia {doc}")
        if r.returncode != 0:
            return {"ok": False, "erro": "Falha ao registrar a mídia no repositório: " + r.stderr[-300:], "erro_cod": "git"}
    r = g("push", "origin", m.get("branch") or "main")
    if r.returncode != 0:
        return {"ok": False, "erro": "Falha ao enviar a mídia ao GitHub (acesso?): " + r.stderr[-300:], "erro_cod": "git_push"}
    base = f"https://raw.githubusercontent.com/{repo}/{m.get('branch') or 'main'}/"
    return {"ok": True, "urls": [base + x.replace(" ", "%20") for x in rel], "locais": locais, "repo_paths": rel}

def publicar_midia(central, rev, doc, arquivos, versao=None, jpg=False):
    """Na nuvem: copia os arquivos finais da peça para o repositório (pasta <central>/<doc>/NN.ext), grava versao.txt,
    faz commit e push e devolve as URLs públicas (raw). Roda dentro do checkout do posts-claude."""
    c = CFG["centrais"][central]
    m = c.get("midia") or {}
    repo = m.get("repo")
    clone = os.path.abspath(os.path.expanduser(m.get("clone_local") or "."))
    pasta = os.path.join(m.get("pasta") or central, doc)
    destino = os.path.join(clone, pasta)
    if os.path.isdir(destino):
        for f in os.listdir(destino):
            os.remove(os.path.join(destino, f))
    os.makedirs(destino, exist_ok=True)
    rel = []
    for i, p in enumerate(arquivos, 1):
        if jpg:  # Zoho (Cunha) recebe JPEG
            from PIL import Image
            nome = f"{i:02d}.jpg"
            Image.open(p).convert("RGB").save(os.path.join(destino, nome), "JPEG", quality=90)
        else:
            nome = f"{i:02d}{os.path.splitext(p)[1].lower() or '.png'}"
            shutil.copy2(p, os.path.join(destino, nome))
        rel.append(os.path.join(pasta, nome))
    # Cunha: versao.txt = campo "atualizado" da peça (é o que zoho_midia confere antes de agendar)
    open(os.path.join(destino, "versao.txt"), "w").write(versao if versao is not None else f"rev {rev}\n")
    g = lambda *a: subprocess.run(["git", "-C", clone] + list(a), capture_output=True, text=True)
    g("add", "-A", "--", pasta)
    if g("diff", "--cached", "--quiet").returncode != 0:
        r = g("-c", "user.name=Claude", "-c", "user.email=noreply@anthropic.com", "commit", "-m", f"midia {central}/{doc} rev {rev}")
        if r.returncode != 0:
            return {"ok": False, "erro": r.stderr[-300:]}
    r = g("push", "origin", "HEAD:" + (m.get("branch") or "main"))
    if r.returncode != 0:
        g("pull", "--rebase", "origin", m.get("branch") or "main")
        r = g("push", "origin", "HEAD:" + (m.get("branch") or "main"))
        if r.returncode != 0:
            return {"ok": False, "erro": "push: " + r.stderr[-300:]}
    base = f"https://raw.githubusercontent.com/{repo}/{m.get('branch') or 'main'}/"
    urls = [base + x for x in rel]
    falta = [u for u in urls if _get(u)[0] != 200]
    return {"ok": not falta, "urls": urls, "falta": falta, "midia": {"rev": rev, "urls": urls, "em": now_iso()}}

# ---------------- limpeza ----------------
def lixeira(path):
    """Move para a Lixeira do Mac (recuperável até esvaziar)."""
    r = subprocess.run(["osascript", "-e", f'tell application "Finder" to delete (POSIX file "{path}" as alias)'], capture_output=True, text=True)
    return r.returncode == 0

def base_stem(path):
    n = os.path.basename(path).rsplit(".", 1)[0]
    return re.sub(r"(-v\d+|-real|-final)+$", "", n)

def limpar(central, dump, doc, executar=False, publicados=None):
    pecas = load_dir(os.path.join(dump, "pecas"))
    fluxo = load_dir(os.path.join(dump, "fluxo"))
    exc = (fluxo.get(doc) or {}).get("excluido") or {}
    c = CFG["centrais"][central]
    # referências de outras peças ativas (não apagar arquivo compartilhado)
    usados = set()
    for pid, p in pecas.items():
        if pid == doc or (fluxo.get(pid) or {}).get("excluido"):
            continue
        for k in ("img",):
            if p.get(k):
                usados.add(p[k])
        for u in p.get("imgs") or []:
            usados.add(u)
        for s in p.get("slides") or []:
            for k in ("img", "png"):
                if s.get(k):
                    usados.add(s[k])
    artifact, assets, locais, manter = [], [], [], []
    for a in exc.get("arquivos") or []:
        tipo = a.get("tipo") if isinstance(a, dict) else "artifact"
        path = a.get("path") if isinstance(a, dict) else a
        if tipo == "asset":
            assets.append(path)
        elif path in usados:
            manter.append(path)
        else:
            artifact.append(path)
    # versões intermediárias publicadas (mesmo nome-base, ex.: x-01.png, x-01-v2.png), se ninguém mais usa
    if publicados:
        stems = {base_stem(p) for p in artifact}
        for p in publicados:
            if p in artifact or p in usados or p == "index.html":
                continue
            if base_stem(p) in stems and not any(base_stem(u) == base_stem(p) for u in usados):
                artifact.append(p)
    # arquivos no disco: JPG finais + cópias no Drive
    fake = {"data": exc.get("data") or "", "titulo": exc.get("titulo") or ""}
    if exc.get("src") == "peca" or doc.startswith("est-") or re.match(r"^\d{4}-\d{2}-\d{2}-", doc) or doc.startswith("post-"):
        m = re.match(r"^(?:est-)?(\d{4}-\d{2}-\d{2})", doc)
        if m:
            fake["data"] = fake["data"] or m.group(1)
        fs = arquivos_peca(central, doc, fake) or []
        locais += fs
    if exc.get("src") == "reel" and exc.get("video") and exc.get("data") and c.get("pasta_reels"):
        dia = os.path.join(c["pasta_reels"], "## POSTAGEM", exc["data"][5:7], exc["data"][8:10])
        if os.path.isdir(dia):
            alvo = simpl(exc["video"])
            locais += [os.path.join(dia, f) for f in os.listdir(dia) if f.lower().endswith(".mp4") and simpl(f[:-4]) == alvo]
    repo_dir = None
    m = c.get("midia") or {}
    if m.get("clone_local"):
        repo_dir = os.path.join(os.path.expanduser(m["clone_local"]), m.get("pasta") or central, doc)
    feitos, falhas = [], []
    if executar:
        for p in locais:
            (feitos if lixeira(p) else falhas).append(p)
        if repo_dir and os.path.isdir(repo_dir):
            clone = os.path.expanduser(m["clone_local"])
            g = lambda *a: subprocess.run(["git", "-C", clone] + list(a), capture_output=True, text=True)
            g("rm", "-r", "-q", "--", os.path.relpath(repo_dir, clone))
            g("commit", "-m", f"remove midia {doc}")
            (feitos if g("push", "origin", m.get("branch") or "main").returncode == 0 else falhas).append("github:" + os.path.relpath(repo_dir, clone))
    return {"doc": doc, "remover_do_artifact": artifact, "assets": assets, "locais": locais, "mantidos_compartilhados": manter,
            "executado": executar, "na_lixeira": feitos, "falhas": falhas,
            "repo_dir": repo_dir, "aviso": "Mídia já enviada ao Metricool fica no servidor deles; a API não permite apagar. O histórico do git guarda versões antigas do repositório." if central == "marcelao" else ""}

# ---------------- migração ----------------
def migrar(central, dump, posts_path=None):
    """Cria fluxo/<id> para as peças antigas, sem inventar aprovação nem autorização.
    - aprovação: só o que o usuário já tinha aprovado na central antiga (status "aprovado") vira aprov.on, marcado como legado.
    - ajuste pedido: vira alteração registrada.
    - "pode postar" antigo NÃO vira autorização, exceto quando a peça já está de fato agendada na plataforma
      (aí a autorização legada é registrada para não cancelar um agendamento real).
    """
    c = CFG["centrais"][central]
    pecas = load_dir(os.path.join(dump, "pecas"))
    fluxo = load_dir(os.path.join(dump, "fluxo"))
    posts = load_posts(posts_path)
    tzl = ZoneInfo(c.get("fuso_legado_grade") or "America/Sao_Paulo")
    out = []
    usados = set()
    for pid, p in sorted(pecas.items()):
        if pid in fluxo:
            continue
        f = {"migrado_em": now_iso()}
        st = p.get("status")
        em = p.get("atualizado") or now_iso()
        f["aprov"] = {"on": st == "aprovado", "rev": 1, "por": "legado", "em": em}
        if st == "ajuste" and p.get("nota"):
            f["alt"] = {"estado": "registrada", "texto": p.get("nota"), "em": p.get("pedido_em") or em, "por": "legado", "rev_base": 1,
                        "anexos": p.get("anexos") or [], "anexos_uso": p.get("anexos_uso") or []}
        # horário: converte de verdade do fuso da grade antiga para Brasília
        hora = (p.get("hora") or "")
        m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*h?", hora)
        data = p.get("data")
        if data and m:
            h, mi = int(m.group(1)), int(m.group(2) or 0)
            local = dt.datetime.strptime(data, "%Y-%m-%d").replace(hour=h, minute=mi, tzinfo=tzl)
            q = local.astimezone(SP).strftime("%Y-%m-%dT%H:%M")
            redes = c["padrao_redes"].get(p.get("tipo"), ["instagram"])
            f["agenda"] = {"redes": redes, "quando": {r: q for r in redes}, "origem": f"{hora} ({'Orlando' if central == 'cunha' else 'Brasília'})"}
            if p.get("postar") and st == "aprovado" and posts:
                txt = (p.get("legenda") or "")
                cand = [x for x in posts if post_dt(x) == q and not x.get("draft") and str(x.get("uuid")) not in usados
                        and (norm(x.get("text"))[:40] == norm(txt)[:40] or (norm(txt)[:25] and norm(txt)[:25] in norm(x.get("text"))))]
                if len(cand) == 1:
                    x = cand[0]
                    usados.add(str(x.get("uuid")))
                    rs = [r for r in post_redes(x) if r in c["redes"]]
                    f["aut"] = {"id": "legado-" + str(x.get("uuid")), "rev": 1, "redes": {r: q for r in rs}, "por": "legado", "em": p.get("postar_em") or em,
                                "legado": True, "snap": {"titulo": p.get("titulo"), "texto": None, "midia_n": len(x.get("media") or []), "formato": p.get("tipo"), "data": data}}
                    f["agenda"] = {"redes": rs, "quando": {r: q for r in rs}, "origem": f["agenda"]["origem"]}
                    f["plat"] = {r: plat_entry("enviado", ext={"uuid": str(x.get("uuid")), "id": x.get("id")}, quando=q, rev=1, aut=f["aut"]["id"], desde=now_iso()) for r in rs}
        out.append({"doc": pid, "data": f, "pecas_patch": {"rev": 1} if not p.get("rev") else None,
                    "legado_postar": bool(p.get("postar")), "agendado_encontrado": "aut" in f})
    return {"central": central, "migrar": out}

def main():
    a = sys.argv[1:]
    if len(a) < 3:
        print(__doc__)
        sys.exit(2)
    cmd, central, dump = a[0], a[1], a[2]
    opt = {}
    i = 3
    rest = []
    while i < len(a):
        if a[i].startswith("--"):
            k = a[i][2:]
            if k in ("executar",):
                opt[k] = True
                i += 1
            else:
                opt[k] = a[i + 1]
                i += 2
        else:
            rest.append(a[i])
            i += 1
    if cmd == "preparar":
        # limpa o download anterior desta central (a pasta é só cache da rodada)
        alvo = os.path.realpath(dump)
        base = os.path.realpath(os.environ.get("CENTRAIS_TMP") or os.path.join(AQUI, "..", "estado"))
        if alvo.startswith(base + os.sep) and os.path.isdir(alvo):
            shutil.rmtree(alvo)
        os.makedirs(alvo, exist_ok=True)
        print(json.dumps({"ok": True, "pasta": alvo}))
        return
    if cmd == "plano":
        r = plano(central, dump, opt.get("posts"), opt.get("sem-conexao"))
    elif cmd == "zoho-criar":
        r = zoho_criar(central, dump)
    elif cmd == "zoho-hora":
        r = zoho_hora(central, dump)
    elif cmd == "publicar-midia":
        # publicar-midia <central> <rev> <doc> arquivo1 arquivo2 ...
        r = publicar_midia(central, int(dump), rest[0], rest[1:])
    elif cmd == "midia-cunha":
        # midia-cunha cunha <doc> <atualizado> arquivo1 arquivo2 ...   (da raiz do repositório)
        r = publicar_midia(central, 0, dump, rest[1:], versao=rest[0], jpg=True)
    elif cmd == "midia":
        r = midia(central, dump, rest[0])
    elif cmd == "limpar":
        pub = [l.strip() for l in open(opt["publicados"])] if opt.get("publicados") else None
        r = limpar(central, dump, rest[0], bool(opt.get("executar")), pub)
    elif cmd == "migrar":
        r = migrar(central, dump, opt.get("posts"))
    else:
        print(__doc__)
        sys.exit(2)
    print(json.dumps(r, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
