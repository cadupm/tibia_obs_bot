# tibia_obs_bot

Cave bot para Tibia que **lê a tela pelo projetor do OBS** e manda teclas e
cliques para o cliente. Cura, poção de mana, ataque com combo de magia, autocast
e rota pelas marcas do mapa — tudo por um painel.

![aba Rota do painel](docs/gui-rota.png)

## Por que o OBS

A janela do Tibia devolve **preto** em captura de janela: o cliente desenha pela
GPU e usa BattlEye, e nenhum dos caminhos comuns (`PrintWindow`, `BitBlt`) vê o
conteúdo. A saída é abrir um **projetor** no OBS ("Captura de jogo" → botão
direito na fonte → Projetor em janela) e ler os pixels dele.

O arranjo em uso:

1. o projetor fica *sempre visível*, mostrando o jogo;
2. a janela do Tibia fica **na frente e transparente** (`python opacity.py 1`),
   recebendo teclas e cliques;
3. o bot lê do projetor e escreve no jogo.

Se o jogo abrir preto, veja *Problemas conhecidos* no fim.

## Instalação

```
pip install mss numpy pyautogui pygetwindow keyboard
python gui.py
```

Windows apenas: o posicionamento de janelas, a opacidade e o clique usam
`user32` direto.

## Como usar

1. abra o Tibia e o **projetor** do OBS, maximizado, na mesma resolução;
2. `python opacity.py 1` deixa a janela do jogo transparente;
3. `python gui.py` abre o painel. `Iniciar` põe o foco no jogo e começa;
4. `Ctrl+Alt+S` para a qualquer momento, mesmo sem foco.

Clicar no painel tira o foco do jogo e o bot pausa sozinho — é proposital,
serve de freio de mão.

### Abas

| aba | o que tem |
| --- | --- |
| Healing | vida/mana máximas, cura, cura de emergência, poção de mana |
| Combate | como lutar (stand/chase/kite), tecla de atacar, combo de magia, lista de monstros |
| Rota | marcas do mapa, rota gravada, tecla de parar de andar |
| Autocast | até 4 teclas em intervalo fixo (pá, comida, buff) |
| Setup | título do projetor, tecla de parada, intervalo do loop |

### Como lutar: stand, chase ou kite

`ATTACK_MODE`, na aba Combate. O cliente tem o modo de luta dele nos botões; o
que se escolhe aqui é o que **o bot** faz enquanto luta:

| modo | o bot |
| --- | --- |
| `stand` | manda a tecla de parada ao engajar e não sai do lugar |
| `chase` | **não** manda a tecla de parada — o `esc` cancelaria o follow do cliente junto com o ataque. Só para de clicar no mapa e deixa o cliente perseguir |
| `kite` | anda de seta para ficar **sempre** a `KITE_DIST` SQM do bicho mais perto: recua se ele chega, **persegue se ele corre** |

No kite, o bot acha as criaturas pela **moldura da barrinha de vida** que o
cliente desenha sobre cada uma. Medida na captura de dentro da cave, ela é
assim:

```
###############################     <- 31 px de preto puro
#VVVVVVVVVVVVVVVVVVVVVVVVVVVVV#     <- 2 linhas de preenchimento colorido
#VVVVVVVVVVVVVVVVVVVVVVVVVVVVV#
###############################     <- preto puro nas quatro bordas
```

Procurar só "faixa fina e saturada" **não serve** no viewport: ali há textura,
efeito de magia e item por tudo, e o bot dizia ver 42, 90, até 202 criaturas na
tela. Exigindo a moldura preta em cima, embaixo e nas duas pontas, sobram só as
barras de verdade. A moldura **não encurta** com o dano — só o preenchimento —
então a detecção funciona igual com o bicho quase morto, que é justamente quem
está perto. A barra de vida **e a de mana** do próprio personagem caem no
quadrado do meio do viewport e são descartadas.

A distância tem **dois lados**. Perto demais é perigo; longe demais é perder o
bicho. A nota de cada posição é, em ordem: está na distância ou mais → o quanto
desvia da distância → a soma das distâncias **em linha reta**. Esse terceiro
nível não é detalhe: o Tibia mede distância pelo maior eixo, e por essa conta
sair de (1,0) para (1,1) não melhora nada — continua colado. Em linha reta
melhora, e é esse passo que no seguinte abre de verdade. Sem ele o bot ficava
plantado quando o único lado que aumentava a distância estava bloqueado por
escada. O desempate vale só quando está perto demais: na distância certa ele
fica parado, senão andaria em círculo por centésimos de diagonal.

### Bicho que corre

Fechar 6 quadrados de seta são 6 teclas a `KITE_COOLDOWN` cada, e cada seta
esbarra sozinha em cada pedra do caminho — era por isso que ele demorava a ir
atrás de quem fugia. A partir de `KITE_DIST + KITE_CLIQUE` de distância o bot
**clica no mapa**: anda o trecho inteiro com o desvio de parede do próprio
cliente, e o clique é calculado para parar exatamente a `KITE_DIST` do bicho. De
perto ele volta para a seta, que é o que dá controle fino.

Isso vale só no modo kite: ali as setas já forçam *stand* no cliente, então o
clique não troca modo de luta nenhum.

**O clique tem de terminar.** Clique no mapa é um trajeto inteiro, e clicar de
novo no meio dele **cancela** o anterior: clicando a cada `KITE_COOLDOWN` o
personagem re-rotava sem parar e andava aos centímetros — era por isso que a
perseguição não saía do lugar. Então só se clica com o personagem **parado**
(como a rota faz) ou depois de `KITE_CLIQUE_ESPERA` se ele travou no caminho.

Limite medido: o viewport tem 15×11 quadrados, então a tela alcança **7 SQM na
horizontal e 5 na vertical**. Bicho que corre além disso não aparece — não há o
que perseguir. Nesse caso o log avisa: `N na battle list e nenhum bicho na tela`.

### O tempo de reação importa

Cada leitura do kite acontece a todo passo, e o tempo ali é atraso de reação —
meio passo atrás de um bicho que corre é nunca alcançar. Por isso as contas da
detecção são medidas, não escritas do jeito mais óbvio:

| conta | jeito óbvio | medido | como ficou |
| --- | --- | --- | --- |
| máximo dos canais | `img.max(axis=2)` | **9,0 ms** | `np.maximum(np.maximum(r,g),b)` → **0,6 ms** |
| achar as molduras | varrer 748 linhas em Python | **61 ms** | pré-filtro em numpy → **14 ms** |

O pré-filtro precisou de cuidado: numa caverna **36% dos pixels são preto puro**,
então procurar só "fileira de preto" dá 212 mil candidatos e não filtra nada. O
que é raro é **cor** — 2% dos pixels. Exigindo fileira de preto em cima, outra
igual três linhas abaixo, e cor no meio das duas, sobram **16** candidatos, e só
esses passam pela conferência detalhada.

### Parede

O kite esbarrava na pedra e ficava martelando a mesma tecla: nada na tela mudava
para ele decidir diferente. A solução **não** é reconhecer parede na tela — é
medir o resultado. Depois de cada passo, se o personagem não saiu do lugar
(`KITE_FALHAS` vezes seguidas, porque um passo leva 250-400 ms e a leitura pode
chegar no meio), aquele lado fica fora por um tempo que **cresce a cada nova
falha** (`KITE_BLOQUEIO` dobrando até `KITE_BLOQUEIO_MAX`). Um passo que dá certo
naquele lado zera a conta.

A espera crescente é o que separa parede de obstáculo sem precisar distinguir
nada: parede continua falhando e vai ficando de fora por mais tempo; caixa e
bicho saem do caminho, o passo seguinte dá certo e a conta zera. Medido em
simulação com parede à esquerda: 6 tentativas na pedra contra 18 passos bons em
24 passos, e nenhuma tentativa no último terço.

Tentei também esquecer o bloqueio ao andar alguns quadrados — "parede à esquerda
não diz nada 3 quadrados adiante" — e ficou **pior**: andando rente a uma parede
o personagem muda de lugar a cada passo, o bot redescobria a mesma pedra a cada
dois quadrados e gastava 10 dos 24 passos nisso. A regra ficou sendo só o tempo.

### Escada, buraco, portal

Cair de andar fugindo de bicho é queda sem volta automática, e o lugar onde se
cai pode estar cheio. Duas camadas:

**O minimapa não ajuda aqui, e vale registrar.** Medi a paleta dele: 292 cores,
das quais o vermelho (254,51,0) parecia marcar escada. Não marca — os 574 pixels
dessa cor formam 111 blocos espalhados que acompanham os prédios: é **telhado**.
O minimapa do Tibia não distingue piso que muda de andar, então identificação
"de graça", sem nunca ter descido, não existe por esse caminho.

O que existe são duas formas de aprender:

**Aprender caindo, uma vez** — quando o alarme detecta a mudança de andar, o bot
guarda o retrato do quadrado que ele acabou de pisar em `evitar.json` e não pisa
mais nele. Cai uma vez em cada escada, nunca duas.

**Ensinar sem cair** — você ensina os quadrados em que não se pisa:

```
python main.py --evitar
```

Clique em cada escada, buraco ou portal na tela do jogo (clique no **projetor**,
que não mexe no personagem). Cada quadrado é recortado, reduzido a uma
assinatura de um pixel a cada 4 e guardado em `evitar.json`; no kite, o bot
deixa de andar para qualquer lado cujo quadrado de destino se pareça com um
deles. Não sobrando lado nenhum, ele fica parado — melhor que cair.

**Chão já pisado** — empatando o resto, o bot prefere o lado por onde o
personagem **já andou**. Aquele chão está provado: não tem parede, porque ele
passou por ali, e não tem escada, porque ele não mudou de andar ali. É de graça,
não depende de reconhecer nada na tela, e serve às duas coisas de uma vez. Vale
só como desempate — nunca acima da distância do bicho.

**Alarme** — se mesmo assim mudar de andar, o bot **para**. Andando pelo mesmo
andar o minimapa apenas rola, e o que sobra de diferença depois de alinhar é
pouco; trocar de andar troca o mapa todo e esse resto dispara. A comparação é
com a **mediana dos restos recentes**, não com um número fixo: cada cave tem sua
textura, e o que interessa é a mudança brusca. Desligável em
`PARAR_SE_MUDAR_ANDAR`.

As **diagonais** vêm desligadas e **não estão confirmadas**: no cliente testado
elas não movem o personagem — de um log inteiro de kite, o único passo que andou
foi um `right`, e as dezenas de `num9` não saíram do lugar. Por isso as teclas
delas são **configuráveis** (`KITE_DIAGONAIS_TECLAS`, na ordem cima-esquerda,
cima-direita, baixo-esquerda, baixo-direita): no Tibia 13 dá para amarrar as
diagonais a qualquer tecla nos controles do cliente — `q,e,z,c`, por exemplo — e
aí basta escrever essas aqui. Meça no seu:

```
python main.py --teclas
```

Ele aperta cada tecla configurada, lê no minimapa se o personagem saiu do lugar
e volta para o ponto de partida. Nenhuma diagonal andando, ele diz o que tentar,
nessa ordem: ligar o NumLock e repetir; amarrar as diagonais a teclas suas nos
controles do cliente e escrevê-las em `KITE_DIAGONAIS_TECLAS`; ou seguir sem
elas.

Sem diagonais o kite funciona — perde só um caso: com um bicho à esquerda e
outro em cima, nenhum dos quatro lados retos aumenta a distância do mais perto,
e só a diagonal aumenta.

O kite é comportamento de **combate**, não de rota: funciona com `ENABLE_WALK`
desligado, para quem liga o bot só para lutar.

Antes de confiar no kite, confira a geometria no seu layout:

```
python main.py --kite
```

Ele imprime as criaturas em SQM e salva `kite_visto.png` com a grade desenhada:
o quadrado **ciano** tem de cair no personagem e os **vermelhos** nos bichos. Se
não caírem, ajuste `GAME_VIEW` e `TILE_PX` (medidos no cliente 1920×1009:
viewport em (221, 61), grade de 15×11 quadrados de 68 px).

### Rota: dois modos

**Ordem gravada** — você clica nas marcas do minimapa na sequência que quer e o
bot segue essa ordem, recomeçando no fim. Dá conta de percurso que não é
círculo: descer um ramo, voltar passando pela entrada e ir ao outro. A gravação
traz o projetor para a frente, então clicar nele **não move o personagem**;
clicando na janela do jogo ele anda até a marca. A lista mostra o desenho de
cada marca para reordenar na mão.

**Regra de ouro** (sem rota gravada) — vai sempre para a marca visível mais
próxima que **ainda não visitou**; não havendo nenhuma nova, a visitada há mais
tempo entre as alcançáveis; a de onde veio só como última opção. O bot aprende
andando **quais marcas se ligam a quais** e onde **não há caminho**, então não
fica batendo numa parede porque a marca do outro braço da caverna está perto em
linha reta.

Nos dois modos o alvo só muda ao **chegar** na marca, conferido por pixel: a
cruz do personagem tem de estar debaixo dela.

## Decisões que vieram de erro medido

O código está comentado com o *porquê* de cada uma delas.

- **Barras de vida/mana por saturação**, não por cor: a barra de HP do Tibia 13
  é verde e muda de cor com o dano.
- **Coordenadas medidas passam na frente da detecção automática** no tamanho de
  cliente conhecido: entre as duas barras há 30 px de separador cinza que a
  detecção somava ao HP — vida cheia lia 89,6% e o bot curava sem parar.
- **Battle list pela coluna das barras (âncora)**: com a coluna conhecida, uma
  barra de 2 px conta como entrada. Sem isso o bicho quase morto sumia da
  leitura e o bot trocava de alvo a um golpe de matá-lo.
- **Só troca de alvo quando a entrada sumir da battle list.** 1 de vida é vivo.
  Guarda-se o sprite e *quantas* entradas iguais havia, porque sprite não
  distingue dois Bonelords — "eram 2, agora é 1" significa que um morreu.
- **Sprite igual mesmo com outro brilho.** Com o bicho quase morto o cliente
  **escurece** o sprite dele na lista. Comparando só por diferença média de
  pixel, o sprite escuro deixava de casar — e aí o bot dava o bicho por morto,
  trocava de alvo a um golpe de matá-lo e voltava a clicar no mapa. Além da
  diferença média, agora vale a **correlação** (média descontada e escala
  normalizada), que ignora brilho: medido, o mesmo sprite a 20% de brilho ainda
  casa, e Bonelord escurecido continua não casando com Gazer.
- **Parar de andar é por tecla, não por clique.** O clique era no próprio
  quadrado do personagem; com zoom out um pixel vale 2 SQM e o clique de "pare"
  cai longe, mandando ele *andar*.
- **Nenhum clique no mapa enquanto há QUALQUER entrada na battle list.** No
  cliente, clique no mapa ou tecla de direção durante o ataque troca o modo de
  luta de *chase* para *stand*. Não basta olhar as entradas "atacáveis": bicho
  ainda não aprendido, ou com o sprite escurecido, também é bicho vivo do lado
  do personagem. A exceção é a lista que já provou não responder ao ataque
  (NPC, player) — essa nunca morre e travaria o cave. Ainda por cima, o trajeto
  só volta depois de a lista ficar limpa por várias leituras seguidas: uma
  leitura ruim no meio da briga não pode virar clique.
- **O ataque sai depois da parada**, com um respiro: a tecla de parada do
  cliente solta o alvo, e mandada depois mataria o ataque recém-dado.
- **Odometria tirada das próprias marcas**, não da correlação do minimapa: na
  briga o personagem se move mais rápido que o raio da correlação, a posição
  derivava e o bot perdia o alvo. A posição é reancorada a cada chegada e
  corrigida a cada leitura pelo desenho do conjunto de marcas.
- **`SW_RESTORE` não serve** para restaurar a janela: ela volta
  *não-maximizada*, o cliente muda de tamanho e todas as coordenadas quebram.
  Usa-se `GetWindowPlacement` + `SW_MAXIMIZE`.
- **`pyautogui.click` não tem efeito no cliente**; o que funciona é
  `mouse_event` com coordenada absoluta e pausa entre down e up.

## Arquivos

```
main.py         o bot: leitura de tela, combate, rota, modos de linha de comando
gui.py          o painel
opacity.py      opacidade da janela do jogo
config.json     o que o painel salva
monstros.json   sprites de battle list aprendidos
evitar.json     quadrados de nao pisar: escada, buraco, portal
rotas/          rotas gravadas (em SQM, sobrevivem à troca de zoom)
testes/         simulações do comportamento de rota e da leitura de tela
```

Modos de linha de comando úteis: `--bars` (só lê vida/mana), `--battle`
(diagnóstico da battle list), `--calib` (coordenada e cor sob o mouse),
`--zoom` (mede px por SQM no zoom em uso), `--marcas` (grava a ordem da rota),
`--kite` (criaturas na tela em SQM, com a grade desenhada num PNG), `--teclas`
(mede quais teclas de movimento andam no cliente), `--evitar` (ensina por clique
os quadrados de não pisar).

## Testes

As simulações em `testes/` rodam sem o jogo aberto: elas substituem a leitura de
tela e o clique por um mundo de mentira, com brigas, empurrões, travadas e
detecção falhando de propósito.

```
python testes/testa_caverna_c.py       # caverna em ramo: varre um lado, volta, varre o outro
python testes/testa_grampo.py          # dois braços colados com pedra no meio
python testes/testa_rota_ordem.py      # rota gravada: segue a ordem, começando do meio
python testes/testa_trava_alvo.py      # não troca de alvo até o bicho sumir da lista
python testes/testa_ordem_parada.py   # para antes de atacar; não clica no mapa lutando
python testes/testa_kite.py           # acha as criaturas na tela e sabe para onde fugir
python testes/testa_kite_distancia.py # recua, persegue, e não pisa na escada
python testes/testa_kite_parede.py    # desiste do lado que não anda e acha outro
python testes/testa_kite_perseguicao.py  # clique de longe, seta de perto
python testes/testa_andar.py          # percebe a queda, aprende o quadrado, não repete
python testes/testa_kite_no_laco.py   # kita no laço do bot, mesmo com o andar desligado
```

`testa_kite.py` usa `tela_cave.png`, uma captura de dentro da cave que vai no
repositório (696 KB): é ela que prova a detecção de criatura contra pixel de
verdade.
`testa_bars.py` e `testa_moribundo.py` precisam de amostras `.npy` que não vão.
`png.py` ali do lado é um leitor de PNG em numpy — o projeto não usa Pillow, e o
mss escreve PNG mas não lê.

## Problemas conhecidos

- **Jogo abre preto.** A captura de jogo do OBS injeta uma DLL no cliente;
  derrubando o jogo com o hook ativo, a janela volta preta. Ordem que resolve:
  fechar o cliente, abrir o **OBS primeiro**, abrir o Tibia, e só então a
  opacidade. Persistindo, troque a fonte de "Captura de jogo" para "Captura de
  tela" — ela não injeta nada.
- **O painel é topmost.** Deixado no topo da tela ele cobre a faixa das barras
  de vida/mana, que ocupam a tela inteira, e o bot lê vida 0%. Ele se posiciona
  sozinho abaixo dessa faixa.
- **Escala do minimapa é manual** (`MINIMAP_PX_SQM`): 2.0 no zoom padrão, 0.5
  com zoom out. Meça com `--zoom` e ajuste ao trocar de zoom.
- Automatizar o cliente vai contra os termos de uso do Tibia. Use por sua conta
  e risco.
