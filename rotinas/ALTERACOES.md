# Rotina "Centrais · alterações" (nuvem do claude.ai, de hora em hora)

Você roda sozinho. Responda em português do Brasil. Fuso: America/Sao_Paulo. Os endereços das Centrais vêm no texto da rotina.

1. Para cada central: ArtifactData action "query", collection "fluxo", query {"where":[["alt.estado","in",["registrada","encaminhada"]]],"limit":100}. Se o filtro aninhado não funcionar, use "list" (limit 1000) e filtre você mesmo os documentos com alt.estado "registrada" ou "encaminhada". Ignore documentos com "excluido".
   Prioridade: primeiro os que têm meta.urgente = true, depois pela data mais próxima.

2. Para cada pedido "registrada": ArtifactData get fluxo/<doc> e update com if_version: alt = {...alt atual, "estado":"encaminhada", "enc_em": <agora ISO UTC Z>, "enc_para": "rotina de alterações (Claude)"}; evento em "eventos" {"item":doc,"acao":"alteracao_encaminhada","det":"","por":"rotina","em":<agora>}. Isso é o "encaminhado" que a Central mostra.

3. Faça a alteração pedida (alt.texto; anexos em alt.anexos são ids de imagens: baixe com Artifact action "read", url da central, path = id). Carregue as skills do cliente antes: cliente-marcelao ou cliente-cunha-law, copy-redes-clientes para texto e design-feed para arte. Regras do DNA da Central valem (ex.: Marcelão nunca escrever "o Marcelão falou"; Cunha: aviso informativo e encaminhamento para a equipe).
   - Peça (carrossel/post, documento em "pecas"): edite o documento pecas/<doc> (get + update com if_version): texto dos slides, legenda, hashtags, imagens. Se mudou arte, gere as imagens novas (skill design-feed, se estiver disponível nesta sessão; senão, ajuste os campos de texto dos slides, que a Central desenha) e publique as imagens novas na Central como arquivos (Artifact publish com url e files) apontando os campos img/imgs/slides para elas. Na Cunha, mude também o campo "atualizado" da peça para a data/hora atual (a rotina de imagens da Cunha gera os JPGs novos a partir dele). Aumente "rev" em 1 (rev atual ou 1, + 1). Não mude status de aprovação no documento da peça.
   - Reel: o vídeo é editado no Premiere (skill da edição do cliente). Reel é editado no Premiere, no Mac: grave alt.bloqueio = "Reel: a edição é feita no Premiere (Mac)" e termine com uma mensagem curta para o Deilson.
   - Se faltar algo que só o Deilson pode dar (foto, decisão, informação), grave alt.bloqueio com a pergunta objetiva e termine com essa pergunta numa mensagem curta para o Deilson. Não invente.

4. Ao concluir: fluxo/<doc> (get + update com if_version): alt = {...alt, "estado":"concluida", "conc_em": <agora>, "resposta": "<o que mudou, em 1 ou 2 frases>", "bloqueio": null}. Para reel, grave também "crev": <crev atual ou 1> + 1. NÃO aprove nem autorize: a peça volta sozinha para "Aguardando aprovação" porque a versão mudou. Evento "alteracao_concluida" com det = resposta.

5. Termine com uma linha por pedido tratado. Se não houver pedido, termine só com "ok".
