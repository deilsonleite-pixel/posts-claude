# Rotina "Centrais · rodada semanal" (nuvem do claude.ai, segunda 8h)

Responda em português do Brasil. Fuso: America/Sao_Paulo. Os endereços das Centrais vêm no texto da rotina.

Objetivo: manter 30 dias de conteúdo preparado em cada Central, revisar o que já está na grade e repor o que falta. Você NÃO aprova, NÃO autoriza e NÃO agenda nada: isso é só do Deilson na Central. Peças urgentes (`urgente = true`) são publicadas na hora pelo fluxo da fila: não mexa nelas nem conte-as como grade (ver FLUXO.md).

Centrais:
- marcelao (skills: cliente-marcelao, copy-redes-clientes, design-feed)
- cunha (skills: cliente-cunha-law, copy-redes-clientes, design-feed)

1. Baixe "pecas" e "fluxo" de cada Central (ArtifactData list, limit 1000, out_dir em /tmp/centrais/semanal/<central>).
2. Revise as peças com data entre hoje e hoje+30 que ainda não estão agendadas:
   - "Com data" (meta.prazo = "data": notícia, boletim, atualização, evento): confira nas fontes oficiais se a informação continua válida (Cunha: USCIS, State Dept/Visa Bulletin, DOL, Federal Register, tribunais). Se mudou, abra você mesmo um pedido de alteração (fluxo/<doc>.alt = {"estado":"registrada","texto":"Rodada semanal: <o que mudou e a fonte>","em":<agora>,"por":"rotina","rev_base":<rev>}) e retire a aprovação dessa versão (aprov.on=false) — nunca deixe uma versão desatualizada aprovada.
   - "Sem prazo" (meta.prazo = "livre"): confira se ainda faz sentido; ajuste por pedido de alteração se precisar.
   - Peças sem meta.prazo: classifique (update fluxo/<doc>.meta.prazo = "livre" ou "data") pelo conteúdo.
3. Conte os dias sem nenhum conteúdo entre hoje e hoje+30. Para repor, produza propostas novas seguindo as skills do cliente e grave cada uma em pecas/<id novo> com "status":"proposta", "rev":1, data, hora (Marcelão "IG 12:00"; Cunha horário de Orlando como "15h"), titulo, por_que, legenda, hashtags, slides, fontes, e fluxo/<id> com {"meta":{"prazo":"livre"|"data"}}. Priorize conteúdo sem prazo para preencher a base e use "com data" só quando houver data real. Não repita tema que está em "descartes" (consulte só os títulos e aprendizados de lá).
4. Termine com um resumo curto para o Deilson: "Rodada semanal: Marcelão X novas propostas, Y revisadas; Cunha ... Aprove na Central." e os dias que continuam vazios.
