# Regras de diagramação e de imagem · Cunha Law

Versão de 04/11/2026, pedida pelo Deilson ("revise todo o conhecimento de diagramação do designer" e "revise os critérios de seleção e aplicação de imagens"). Vale para todo post e capa de carrossel, em qualquer thread, rotina, skill ou Executor. Tudo o que tem código (H1, I4...) é medido por `render.js`. Arte que falha não vai para a Central.

## Como usar (obrigatório antes de entregar qualquer arte)

1. Monte a arte pelo modelo oficial `modelo-post-noticia.html` (post com foto) ou pela Central (`slide()`). Se fizer uma "diagramação própria", ela precisa ter `.sl` 1080x1350 e a manchete em `h4` (ou com `data-headline`).
2. Foto: rode `python3 foco.py foto.jpg <altura da área da foto> --recortar foto-rec.jpg`. Ele põe o rosto no lugar certo e avisa se falta resolução.
3. Renderize com `node render.js <html> <peca.json|-> <saida> [--pessoa]` (`--pessoa` quando a notícia é sobre uma pessoa pública). Ele ajusta a manchete sozinho (`fit-headline.js`), confere tudo (`checar.js` e `checar_imagem.py`) e gera a versão de celular (`_celular.png`, com 540 px).
4. Só entregue com **OK**. Se der FALHA, corrija o que a linha diz e rode de novo.
5. Olhe a `_celular.png` antes de subir. O script não julga se a foto conta a história.

## Manchete

| Código | Regra | Por quê |
|---|---|---|
| H1 | Nenhuma linha com uma palavra só (vale para manchete de 3 palavras ou mais) | "O TEXAS / VIROU" e "NINGUÉM APROVOU / ANISTIA" deixam uma palavra solta |
| H2 | Nenhuma linha termina em palavra fraca (o, a, de, do, em, para, que, com...) | quebra a leitura |
| H3 | Linhas equilibradas: a mais curta tem pelo menos 60% da mais longa | bloco de texto com forma limpa |
| H4 | A linha mais longa ocupa no mínimo 85% da largura do texto. A fonte sai da largura, não de um número fixo | texto pequeno no meio de espaço vazio |
| H5 | Fonte mínima de 96 px (48 px no celular). Se não cabe, enxugue a manchete ou divida em duas frases | leitura no celular |
| H6 | No máximo 3 linhas (4 quando são duas frases) | — |
| H7 | Um destaque laranja só: a palavra-chave ou a frase do impacto, com no máximo 60% das palavras. Nunca a manchete inteira. O destaque fica na mesma linha das outras palavras quando cabe; ele não vira linha própria | "dar um destaque diferente" |
| H8 | Frase que termina (. ? !) fecha a linha. Duas frases = dois blocos, cada um preenchendo a largura | "Donalds vence na Flórida. / Parceria com o ICE continua" |

- Os 144 px de 30/10 deixam de ser um tamanho fixo. A fonte é a maior que preenche a largura, entre 96 e 200 px. Manchete curta fica maior que 144 px; manchete longa vai em duas frases.
- Uma linha só é o melhor quando dá pelo menos 96 px. Exemplo: "TALARICO VIRA O TEXAS".
- Manchete continua seguindo a copy: nomeia o assunto, sem número solto, fato com fonte.

## Texto e margens

- M1: todo texto fica a pelo menos 80 px das laterais, 96 px da borda de baixo e 60 px do topo. A exceção é o avatar do rodapé do modelo antigo.
- Texto de apoio: 40 a 52 px, até 3 linhas. Aviso: "Conteúdo informativo." ou "Conteúdo informativo. Cada caso é um caso.", com 26 a 32 px.
- Equilíbrio (DNA, 04/11): não deixar bloco no topo, vazio no meio e bloco no pé. No modelo, a foto ocupa todo o espaço acima do texto.

## Imagem

**Pesquisa e fonte (nesta ordem)**
1. Foto enviada pelo Deilson: é para usar.
2. **Pessoa pública na notícia (quem ganhou, quem falou, quem decidiu): sempre a foto real da pessoa, nunca prédio, bandeira ou paisagem.** Prefira a cena do momento (campanha, discurso, comício, chegada, evento), com expressão e gesto. Retrato oficial de estúdio só se não houver outra. Onde procurar:
   - Wikimedia Commons, pela API (`generator=search` com `filetype:bitmap`; tem muita foto de evento, como as de Gage Skidmore, em CC BY-SA);
   - Flickr oficial do político, da campanha ou do governo (domínio público ou CC);
   - site oficial e sala de imprensa (house.gov, senate.gov, whitehouse.gov, sites de campanha);
   - foto de agência/jornal (og:image da matéria) só quando o Deilson autorizar o risco ([[imagem-rapido-pratico]]), sempre com crédito.
3. Assunto sem pessoa: imagem que se entende de relance (DNA 27/10), de bancos livres (Unsplash, Wikimedia) ou frames dos vídeos dele.
4. Nunca pare na primeira foto boa (Deilson, 04/11). Monte uma folha com 4 a 6 candidatas de campanha, discurso ou evento e escolha a de rosto grande e expressivo, com contexto (plateia, bandeira, microfone), luz no rosto e fundo que não briga com o texto.
5. Crédito sempre na arte: "Foto: autor (licença)". Confira o autor na página do arquivo. Não invente.

**Qualidade e aplicação**

| Código | Regra |
|---|---|
| I1 | Resolução: a foto não pode ser ampliada mais de 1,3x. Baixe o arquivo grande (Commons `width=2400`, Unsplash `w=2400`), nunca a miniatura |
| I2 | Nunca esticar: só `object-fit: cover` (ou recorte). Proporção original sempre |
| I3 | A foto preenche: vai de borda a borda na largura e ocupa no mínimo 45% da arte. No modelo, ela vai do topo até 140 px abaixo do início do texto, com um degradê por baixo. Nada de retrato pequeno numa caixa |
| I4 | Nenhum texto, etiqueta ou avatar sobre o rosto (com folga) |
| I5 | Rosto inteiro: sem corte pela borda da arte nem pela borda da foto |
| I6 | Pessoa pública: rosto com no mínimo 11% da altura da arte (cerca de 150 px). O `foco.py --recortar` busca cerca de 33% da área da foto, em meio corpo, como foto de imprensa |
| I7 | Exposição: até 2% de pixels estourados na foto. Nunca clarear a foto. Para mostrar mais a foto, reduza a camada azul ([[design-regras-foto]]) |

- Enquadramento: o rosto fica a cerca de 60% da largura (o avatar está à esquerda) e a cerca de 46% da altura da área da foto. É isso que o `foco.py` faz.
- Sem recorte de objeto nem montagem de duas fotos ([[design-sem-recorte-montagem]]).

## O que o script não mede (olhar na prévia de celular)

- Se a foto conta a história da manchete.
- Se a expressão combina com o tom (golpe e ICE pedem tensão, conquista pede vitória).
- Se a pessoa da foto é mesmo a pessoa da notícia.
