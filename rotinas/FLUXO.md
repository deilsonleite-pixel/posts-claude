# Fluxo único das Centrais (vale para toda thread, chat, rotina e skill)

Regra do Deilson, 15 e 16/10/2026. Este arquivo é a fonte única: as rotinas, as threads e as skills seguem o que está aqui, sem interpretação própria. Se outro texto contradisser este, vale este.

## Dois caminhos

| | URGENTE | AGENDADO |
|---|---|---|
| Quando | O Deilson diz que o assunto é "para hoje", "urgente" ou "publicar agora" (em qualquer thread, chat ou na Central) | Todo o resto: grade de 30 dias, rotina de sexta, pauta normal |
| Marcação na peça | `pecas/<id>.urgente = true`, `data` = hoje, `hora` = horário sugerido (só referência) | sem `urgente` (ou `false`), `data` e `hora` da grade |
| Produção | Na hora, com prioridade, completa (arte, copy, fontes) | Pelo planejamento (30 dias; sexta produz a semana seguinte) |
| Aprovação | O Deilson aprova na Central e clica "Pode postar" | O Deilson aprova na Central e clica "Pode postar" |
| Plataforma | **Publicar agora**: Zoho `POST /posts/publish` (`type: "publish"`, sem horário), Instagram e Facebook, assim que houver "Pode postar" | Semana atual: agenda na hora do clique, na data e hora da peça (`POST /posts/schedules`). Semana seguinte: a rotina de sexta libera e agenda |
| Programação existente | Nunca altera, substitui nem empurra o que já está programado. Urgente é ADICIONAL | O que já está agendado fica como está |

Princípio: urgente aprovado = publicação imediata. Programado = publicação na data prevista.

## Regras comuns
1. Toda peça nova (post ou carrossel) entra na Central da Cunha Law em `pecas/<id>` + `fluxo/<id>`, status "proposta", com slides, legenda, hashtags e fontes oficiais. Reels nunca: são do Deilson.
2. Aprovar NÃO publica nem agenda. Só o "Pode postar" do Deilson, na Central, autoriza (`fluxo/<id>.aut`).
3. Nenhuma thread, rotina ou skill aprova, dá "Pode postar", agenda ou publica por conta própria.
4. Post e carrossel vão sempre para Instagram E Facebook.
5. Pedido de alteração vai para `fluxo/<id>.alt` e para a fila (ALTERACOES.md). Urgente com alteração: o executor trata primeiro, mantém `urgente = true`, e a peça volta para aprovação.
6. Quem executa o "Pode postar" é o script `fluxo_worker.py` (FILA.md): ele decide sozinho entre Publicar agora (peça urgente) e agendar (as outras).
7. Horário da peça = Orlando; a Central converte para Brasília. Confira o dia da semana no calendário antes de dar data.
8. Status e aprovação vivem só na Central.
