# Rotina "Centrais · alterações" (nuvem do claude.ai, de hora em hora)

Você roda sozinho. Responda em português do Brasil. Fuso: America/Sao_Paulo. Os endereços das Centrais vêm no texto da rotina.

## Fila única, por ordem de chegada (regra do Deilson, 16/10/2026)

Todo pedido de alteração, correção ou ajuste entra numa fila única das duas Centrais e é atendido na ordem em que chegou: o mais antigo primeiro, pela data `alt.em`. Não pule pedidos por data de postagem nem por central. Você trata a fila inteira nesta rodada, um pedido de cada vez, até ela ficar vazia: não deixe nada para a próxima hora se dá para fazer agora.

Pode haver vários pedidos para a mesma peça. Revisões são ilimitadas até a aprovação final:
- `alt.pedidos` é a lista dos pedidos da peça, em ordem. Cada item tem `texto`, `em`, `por`, `anexos` e `rev_base`. `alt.texto` junta todos (os acréscimos vêm como "[Acréscimo de DD/MM às HH:MM] ..."). Documentos antigos podem não ter `pedidos`: aí vale só `alt.texto`.
- `alt_hist` guarda os pedidos já concluídos, cancelados ou aprovados. É só histórico: não refaça nada dele, mas leia para entender o que já foi pedido e feito antes.

## Passos

1. Monte a fila. Para cada central: ArtifactData action "query", collection "fluxo", query {"where":[["alt.estado","in",["registrada","encaminhada"]]],"limit":100}. Se o filtro aninhado não funcionar, use "list" (limit 1000) e filtre você mesmo os documentos com alt.estado "registrada" ou "encaminhada". Ignore documentos com "excluido" ou "descartado". Junte as duas centrais numa lista só e ordene por `alt.em`, do mais antigo para o mais novo.

2. Para cada pedido "registrada": ArtifactData get fluxo/<doc> e update com if_version: alt = {...alt atual, "estado":"encaminhada", "enc_em": <agora ISO UTC Z>, "enc_para": "rotina de alterações (Claude)", "n_feitos": <quantidade de itens em alt.pedidos, ou 1>}; evento em "eventos" {"item":doc,"acao":"alteracao_encaminhada","det":"","por":"rotina","em":<agora>}. A Central mostra isso como "Em execução".

3. Faça a alteração pedida.
   - Imagens: `alt.anexos` (e `anexos` de cada item de `alt.pedidos`) é uma lista de {id, fonte, uso}.
     - fonte "asset": baixe com Artifact action "read", url da central, path = id.
     - fonte "db": ArtifactData get, collection "anexos", doc_id = id, com out_dir; o campo `data` é um data URL JPEG (decodifique o base64 para arquivo).
     - uso "referencia": é referência visual (exemplo de layout, de estilo, do que está errado). Não coloque a imagem na peça.
     - uso "usar": é material para entrar na edição (foto, logo, print a ser usado), conforme o texto do pedido.
     Abra e olhe cada imagem antes de editar.
   - Carregue as skills do cliente antes: cliente-marcelao ou cliente-cunha-law, copy-redes-clientes para texto e design-feed para arte. Regras do DNA da Central valem (ex.: Marcelão nunca escrever "o Marcelão falou"; Cunha: aviso informativo e encaminhamento para a equipe).
   - Peça (carrossel/post, documento em "pecas"): edite o documento pecas/<doc> (get + update com if_version): texto dos slides, legenda, hashtags, imagens. Se mudou arte, gere as imagens novas (skill design-feed, se estiver disponível nesta sessão; senão, ajuste os campos de texto dos slides, que a Central desenha) e publique as imagens novas na Central como arquivos (Artifact publish com url e files) apontando os campos img/imgs/slides para elas. Na Cunha, mude também o campo "atualizado" da peça para a data/hora atual (a rotina de imagens da Cunha gera os JPGs novos a partir dele). Aumente "rev" em 1 (rev atual ou 1, + 1). Não mude status de aprovação no documento da peça.
   - Reel: nunca edite. Reels do Marcelão e da Cunha Law são feitos à mão pelo Deilson. Grave alt.bloqueio = "Reel: a edição é feita à mão pelo Deilson" e siga para o próximo pedido.
   - Se faltar algo que só o Deilson pode dar (foto, decisão, informação), grave alt.bloqueio com a pergunta objetiva e siga para o próximo pedido. Não invente.

4. Ao concluir: releia fluxo/<doc> (get).
   - Se `alt` sumiu ou não está mais "encaminhada" (alguém aprovou a peça como estava, o que cancela o pedido), não grave nada no fluxo e anote "cancelado pela aprovação" no resumo.
   - Se `alt.pedidos` tem mais itens do que `alt.n_feitos` (chegou um acréscimo enquanto você trabalhava), faça também os novos itens (volte ao passo 3 só com eles) e atualize `n_feitos`.
   - Depois: update com if_version: alt = {...alt, "estado":"concluida", "conc_em": <agora>, "resposta": "<o que mudou, em 1 ou 2 frases>", "bloqueio": null}. NÃO aprove nem autorize: a peça volta sozinha para "Aguardando aprovação" porque a versão mudou, e o Deilson pode aprovar, agendar ou pedir outra alteração. Evento "alteracao_concluida" com det = resposta.

5. Fila vazia? Antes de terminar, refaça o passo 1. Se chegou pedido novo durante a rodada, trate-o agora (mesma ordem por `alt.em`). Só termine quando a fila estiver vazia.

6. Termine com uma linha por pedido tratado. Se não houver pedido, termine só com "ok".
