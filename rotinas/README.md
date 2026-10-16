# Rotinas das Centrais (Marcelão e Cunha Law)

Código e instruções das rotinas do claude.ai que levam o que foi aprovado e autorizado ("Pode postar") nas Centrais
para o Metricool (Marcelão) e o Zoho Social (Cunha Law), conferem o agendamento, cancelam e limpam exclusões.

- `FLUXO.md` — regra única urgente x agendado (vale para toda thread, rotina e skill).
- `fluxo_worker.py` — lógica determinística (não guarda credenciais; o Zoho usa as variáveis do ambiente da nuvem).
- `test_fluxo.py` — cenários: `python3 rotinas/test_fluxo.py`.
- `FILA.md`, `ALTERACOES.md`, `SEMANAL.md` — instruções lidas por cada rotina.
- Os endereços das Centrais ficam só no texto das rotinas, não neste repositório público.
