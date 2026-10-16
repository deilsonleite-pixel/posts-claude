# Fluxo único das Centrais (vale para toda thread, chat, rotina e skill)

Regra do Deilson, 15 e 16/10/2026. Este arquivo é a fonte única: as rotinas, as threads e as skills seguem o que está aqui, sem interpretação própria. Se outro texto contradisser este, vale este.

## Item 4 do projeto (texto final do Deilson, 16/10/2026 19h20 UTC)

Nenhum thread aprova, dá "Pode postar" nem agenda por conta própria. Quem aprova é o Deilson na Central. Existe um único botão, "Pode postar", e o sistema decide o que fazer pela marca e pela data da peça:
a) Peça marcada "urgente" (para hoje/agora): publica na hora no Instagram e no Facebook, sem agendar. O cartão mostra "URGENTE: sai na hora ao clicar Pode postar".
b) Data próxima (até o fim da semana atual): vai na hora para o Zoho Social, agendada na data e hora da peça.
c) Semana seguinte: a rotina de sexta agenda.
Urgente é adicional: nunca altera nem substitui o que já está programado. A marca "urgente" só muda por pedido de alteração.

## Como cada caso é executado

| | a) URGENTE | b) DATA PRÓXIMA | c) SEMANA SEGUINTE |
|---|---|---|---|
| Marca na peça | `pecas/<id>.urgente = true`, `data` = hoje | sem `urgente`, data até o domingo da semana atual | sem `urgente`, data a partir da segunda seguinte |
| Ao clicar "Pode postar" | Zoho `POST /posts/publish` (`type: "publish"`, sem horário), IG e FB, na hora | Zoho `POST /posts/schedules` na data e hora da peça, na hora do clique | `fluxo/<id>.fila`; a rotina de sexta libera e agenda |
| Quem executa | `fluxo_worker.py` (FILA.md), decide sozinho pela marca | `fluxo_worker.py` | rotina "agendamento da semana seguinte" + `fluxo_worker.py` |

Quem pede "para hoje", "urgente" ou "publicar agora" (em qualquer thread, chat ou na Central) gera peça com `urgente = true`. Não existe outro botão nem outro caminho.

## Regras comuns
1. Toda peça nova (post ou carrossel) entra na Central da Cunha Law em `pecas/<id>` + `fluxo/<id>`, status "proposta", com slides, legenda, hashtags e fontes oficiais. Reels nunca: são do Deilson.
2. Aprovar NÃO publica nem agenda. Só o "Pode postar" do Deilson, na Central, autoriza (`fluxo/<id>.aut`).
3. Nenhuma thread, rotina ou skill aprova, dá "Pode postar", agenda ou publica por conta própria.
4. Post e carrossel vão sempre para Instagram E Facebook.
5. Pedido de alteração vai para `fluxo/<id>.alt` e para a fila (ALTERACOES.md). Urgente com alteração: o executor trata primeiro, mantém `urgente = true`, e a peça volta para aprovação.
6. Quem executa o "Pode postar" é o script `fluxo_worker.py` (FILA.md): ele decide sozinho entre Publicar agora (peça urgente) e agendar (as outras).
7. Horário da peça = Orlando; a Central converte para Brasília. Confira o dia da semana no calendário antes de dar data.
8. Status e aprovação vivem só na Central.
