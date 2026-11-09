# Conferência diária anti-duplicidade (Cunha Law)

Regra do Deilson (09/11/2026): "para que não haja mais problemas e erros de duplicidade".
Roda 2x por dia (4h47 e 16h47 Orlando = 6h47 e 18h47 Brasília) numa sessão nova. Não apaga nada, nunca.

1. `git pull` do main. `D=/tmp/centrais/dump/cunha`.
2. Rode o FILA.md SÓ para a cunha (passos 1 a 9, com o mLabs do passo 4). Isso marca Publicado o que já saiu
   e põe o status da Central em dia (regra 6 do fluxo).
3. `python3 rotinas/fluxo_worker.py conferir cunha $D --mlabs $D/mlabs.json > $D/conferencia.json`
4. Leia o resultado:
   - `ok: true` e nada em `publicado_2x`: termine com "ok" (sem aviso).
   - `duplicatas_agendadas`: a mesma peça está agendada 2x na mesma rede (Zoho e/ou mLabs).
   - `agendado_ja_publicado`: vai sair de novo algo que já saiu.
   - `publicado_2x`: saiu 2x na mesma rede nos últimos 14 dias.
   - `resumo_semana.ok: false` (só às segundas): o carrossel Resumo da semana de hoje não existe na Central.
   - `falhas`: alguma fonte não respondeu (a conferência não vale; diga qual).
5. Qualquer item do passo 4 que não seja "ok": aviso URGENTE ao Deilson (skill aviso-urgente,
   título "⚠️ URGENTE – Duplicidade Cunha Law") com, por item: a peça (título), a rede, onde está cada cópia
   (Zoho post id / mLabs link https://publish.mlabs.io/schedule/<id>/edit / link do post) e os horários em
   Brasília. Diga qual cópia manter (a da Central, no horário da Central) e qual excluir. NÃO exclua nada:
   excluir só com OK escrito dele.
