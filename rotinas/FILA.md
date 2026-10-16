# Rotina "Centrais · fila" (nuvem do claude.ai, de hora em hora)

Você roda sozinho, sem ninguém para responder. Não converse e não pergunte. Fuso de tudo: America/Sao_Paulo.
O endereço de cada Central vem no texto da rotina (não fica neste repositório). Quem decide o que fazer é o script `rotinas/fluxo_worker.py`: você só executa o que ele mandar. Nunca publique imediatamente, exceto peça URGENTE com "Pode postar" (o script faz isso sozinho; ver FLUXO.md). Nunca agende, altere ou cancele nada fora das "acoes" do script. Nunca mexa em "aprov" ou "aut" a não ser pelas "marcas" do script. Nunca mostre valores de credenciais.

`export CENTRAIS_TMP=/tmp/centrais` e use `D=$CENTRAIS_TMP/dump/<central>` como pasta de trabalho.

## Para cada Central (marcelao, depois cunha)

1. **Baixar.** `python3 rotinas/fluxo_worker.py preparar <central> $D`. Depois ArtifactData "list" com a url da Central, collection "fluxo", query {"limit":1000}, out_dir $D; repita para "pecas" e, na cunha, para "postado". Se a leitura falhar, anote no resumo final e passe para a próxima Central.

2. **Plataforma.**
   - marcelao: Metricool `getScheduledPosts` (brandId "7370375", timezone "America/Sao_Paulo", fromDate hoje−2 dias 00:00:00-03:00, toDate hoje+180 dias 23:59:59-03:00). Grave a resposta inteira em $D/posts.json. Se falhar, use `--sem-conexao "<erro curto>"` no passo 3.
   - cunha: nada a buscar (o script consulta o Zoho Social direto pela API com as credenciais do ambiente).

3. **Mídia do Marcelão (antes do plano).** Para cada peça de "pecas" com data entre hoje e hoje+30 cujo `fluxo/<id>.aprov.on` é true e cujo `fluxo/<id>.midia.rev` é diferente de `pecas.rev` (ou 1): se a peça tem arte final (`imgs` ou `img`), baixe esses arquivos com Artifact "read" (url da Central, paths = os caminhos, out_dir $D/arte/<id>) e rode `python3 rotinas/fluxo_worker.py publicar-midia marcelao <rev> <id> <arquivos na ordem>`. Se ok=true, grave em fluxo/<id> (get + update com if_version) `{"midia": <midia do resultado>}`. Sem arte final: pule (a Central mostra "aguardando imagens").

4. **Plano.** `python3 rotinas/fluxo_worker.py plano <central> $D [--posts $D/posts.json]`.

5. **Marcas.** Para cada item: se "patch" não vazio, ArtifactData get fluxo/<doc> e update com if_version (conflito = pule). Se houver "evento" [acao, det]: ArtifactData set em "eventos", doc_id "rot-<AAAAMMDDHHMMSS>-<4 letras>", data {"item","acao","det","por":"rotina","em":<agora ISO Z>}.

6. **Ações**, na ordem. Antes de cada uma: get fluxo/<doc>; se tem "excluido" e a ação não é cancelar/limpar, pule; nas de criar, confira aut.id == esperado.aut_id e aut.rev == esperado.rev.
   a) **Trava:** update fluxo/<doc> com data = acao.claim e if_version. Conflito = pule a ação inteira (evita duplicar).
   b) **metricool_criar / metricool_atualizar** (marcelao): as URLs de mídia vêm de fluxo/<doc>.midia.urls (da mesma rev). Sem elas, grave plat.<rede> = {"st":"aguardando_midia","erro":"Imagens desta versão ainda não estão no repositório.", ...} e siga. Com elas: info = acao.info com "media" = urls e "mediaAltText" = lista de null. Criar: `createScheduledPost(blogId, date = acao.quando+":00-03:00", info = JSON)`. Atualizar: `updateScheduledPost(id, uuid, blogId, info)`.
   c) **metricool_cancelar:** `updateScheduledPost(id, uuid, blogId, info = JSON de acao.info)` (é o mesmo post com draft=true).
   d) **zoho_criar** (cunha): grave a ação em $D/acao.json e rode `python3 rotinas/fluxo_worker.py zoho-criar cunha $D/acao.json`. Use o "plat" e o "evento" que ele devolver. Se vier "incerto": não grave nada (a próxima rodada confere antes de reenviar).
      Peça URGENTE (`pecas/<id>.urgente = true`, regra de 16/10/2026, ver FLUXO.md): o plano já traz `"agora": true` e `endpoint` `/posts/publish`, e o script PUBLICA NA HORA (Publicar agora), sem horário. Isso é o esperado: não troque por agendamento nem espere a hora da peça. Nada do que já está programado muda.
   d2) **zoho_hora** (cunha): post agendado no Zoho fora do horário da Central (mesma data). Sem trava: grave a ação em $D/acao.json e rode `python3 rotinas/fluxo_worker.py zoho-hora cunha $D/acao.json`. Ele troca só a hora (texto, imagens e redes ficam) e confere lendo de volta. Grave o "evento" que ele devolver em "eventos" (item = acao.doc). Se ok=false, entra no aviso do passo 9.
   e) **Resultado Metricool:** sucesso → plat.<rede> = {"st":"enviado","ext":{"id","uuid","url":plannerUrl},"quando","rev","aut","desde":<agora>,"tent"} + evento "enviado". Erro da plataforma → "falha" com a mensagem em português simples e o que fazer + evento "falha". Sem resposta → não grave nada.
   f) **limpar_arquivos:** Artifact "list" scope "files" da Central → caminhos em $D/publicados.txt; `python3 rotinas/fluxo_worker.py limpar <central> $D <doc> --publicados $D/publicados.txt`; para cada id em "assets", Artifact "delete" (url da Central, path = id); remova do repositório a pasta `<central>/<doc>` (git rm, commit, push), se existir; junte "remover_do_artifact" para o passo 8; grave excluido.estado = "concluido" (ou "erro" com o motivo) e evento "arquivos_apagados". Arquivos do Mac (Postagens, Xport) não existem aqui: anote no excluido "aviso_mac": "apagar no Mac: <lista>" quando o script listar algum.

7. **Status.** status/plataforma = status_plataforma do plano (get + update/set). status/rotina: update {"fila_em": <agora ISO Z>} e, se a plataforma respondeu, "sync_em".

8. **Arquivos publicados** (só se houver "remover_do_artifact"): Artifact "read" da Central e publique de novo o mesmo arquivo com url da Central e files = {"<caminho>": null, ...}. Conflito: leia de novo e repita uma vez.

9. **Aviso.** Só se esta rodada corrigiu hora no Zoho (zoho_hora: diga qual peça, de que hora para qual), gravou "falha" nova, "cancelando" novo na cunha (precisa cancelar no Zoho à mão) ou a plataforma ficou sem conexão: termine com uma mensagem curta e objetiva para o Deilson (o que aconteceu, em qual peça, o que fazer). Se tudo correu bem, termine só com "ok".
