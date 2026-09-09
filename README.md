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
| Combate | como lutar (stand/chase/kite), tecla de atacar, kite, combo de magia, lista de monstros |
| Loot | ir no corpo e clicar, tecla de saque, fila de corpos |
| Rota | marcas do mapa, rota gravada, tecla de parar de andar |
| Autocast | até 4 teclas em intervalo fixo (pá, comida, buff) |
| Setup | título do projetor, tecla de parada, intervalo do loop |

### Loot

`ENABLE_LOOT`, na aba **Loot** — aba própria, porque saquear não é parte de como
lutar: acontece **depois** da briga e é **igual** em stand, chase e kite. O modo
de luta muda de onde se parte, não o que se faz com o corpo.

O gesto cabe numa frase: **chegar no corpo e clicar nele com o botão direito.**
No Tibia o direito sobre um corpo saqueia — sabendo que clicou nele, está feito,
e não há o que conferir depois. O esquerdo só manda o personagem andar para lá.

A tecla de saque (`LOOT_USA_TECLA`) fica **desligada** por padrão. Ela vinha
depois do clique mirando o cursor em nove pontos: trabalho para confirmar o que
já estava confirmado. Continua disponível como reforço para quem quiser.

**Não sabendo onde o corpo caiu, o bot larga o corpo** (`LOOT_SO_SE_ACHOU`).
Clicar em volta esperando acertar não é saquear — clique de botão direito em
chão vazio abre menu de contexto e não pega nada. Medido: 1 clique em 1 ponto
por corpo, contra 1 clique mais 24 apertadas espalhadas em 9 pontos.

**O corpo é procurado NA TELA, não estimado.** A posição vinda da odometria erra
por 1 SQM com facilidade, e cobrir esse erro varrendo o anel em volta é
tentativa e erro. Existe um sinal direto: o quadrado onde o bicho estava **muda**
quando ele morre (sprite de bicho → sprite de corpo), e o quadrado vizinho que
nunca teve bicho continua igual. Quem mudou é onde caiu.

Não é reconhecimento de sprite de corpo — isso mudaria de espécie para espécie e
precisaria de uma tabela por bicho, com um passo de aprendizado. É "este quadrado
ficou diferente", que vale para qualquer bicho, inclusive um que o bot nunca viu.
O quadro da última leitura com o bicho vivo é guardado junto com a posição, e a
comparação alinha os dois quadros pelo tanto que o personagem andou — o viewport
acompanha o personagem, então o mesmo lugar do mundo aparece deslocado.

Medido em cenário sintético: corpo aparecendo muda **16,7** por pixel, chão
parado **0,0**, chão inteiro trocado (o pior caso de água/fogo) **10,1**. Daí
`LOOT_DIFF_MIN = 12`. Há uma segunda defesa, `LOOT_DIFF_MARGEM`: o vencedor tem
de mudar 1,5× mais que o segundo colocado, senão o bot **diz que não sabe** e cai
no palpite com a varredura. Dois bichos morrendo em quadrados diferentes, ou tudo
mudando ao mesmo tempo, dão empate e não viram chute.

Os números reais aparecem no log de cada morte (`mudou N por pixel, segundo M`)
— é por eles que se calibra o limiar na sua caverna, já que os meus vêm de
cenário sintético.

Depois do clique sai um `esc` (`LOOT_FECHA_MENU`): sem *classic control* o
clique direito abre menu de contexto, que fica na frente e engole o que vier
depois.

A comparação usa o quadro **mais recente** em que o bicho ainda constava da
battle list. A janela de quadros para de crescer quando a lista esvazia, então o
último item é o instante logo antes de ele **sair da lista** — a posição mais
fresca e, para comparar a tela, o quadro mais perto no tempo, com menos coisa
tendo mudado por outro motivo. Era o item mais velho da janela, cinco leituras
atrás.

**Dois anéis com o mesmo desenho e razões opostas.** O anel da *varredura* de
tecla é chutar em volta; o anel da *busca* na tela é medir. Eles compartilhavam
a mesma função, e desligar a varredura encolheu a busca para um quadrado só — o
do palpite, justamente o erro que a busca existe para corrigir. São funções
separadas agora, com teste próprio.

**A fila é de vários corpos** (`LOOT_MAX_CORPOS`). Guardar um só deixava no chão
todo bicho da briga menos o último, e numa caverna se mata em grupo.

**O corpo é guardado em coordenada absoluta do odômetro, não em offset.** O
corpo não anda: quem anda é o personagem, e offset guardado envelhece a cada
passo. Corrigir esse envelhecimento a cada leitura foi a origem de dois bugs
seguidos — o offset do corpo e depois o da fila de varredura. Posição absoluta
não precisa de correção nenhuma: a conta é sempre a mesma subtração.

**Por que esperar a battle list limpar**, em vez de saquear a cada morte: no
cliente, clique no mapa ou na tela durante o ataque troca o modo de luta de
*chase* para *stand*; parado em cima do corpo com bicho vivo em volta o
personagem apanha de graça; e corpo no Tibia dura minutos, então não há pressa.

**O prazo conta de quando o bot chega naquele corpo**, não da morte. Contado da
morte, uma briga de três bichos condenava os dois últimos: eles morrem no mesmo
instante e o prazo deles vencia enquanto o primeiro era saqueado. Medido: de
três corpos na fila, um era largado sem receber um clique. Passado
`LOOT_VALIDADE` desde a morte o corpo é largado sem tentativa — ele ficou para
trás na rota e ir atrás dele é sair do caminho por nada.

**O `-` de cima e o `-` do numpad são teclas diferentes.** Para o Windows e para
o cliente, um é `VK_OEM_MINUS` e o outro é `VK_SUBTRACT`. Com a hotkey no numpad
e o bot apertando a de cima, não acontecia nada — e o log não acusava, porque do
lado do bot a tecla tinha sido apertada com sucesso. Agora ele manda **as duas**
(`LOOT_HOTKEY_NUMPAD`): tecla que o cliente não usa não faz nada.

**A tecla age sobre o que está debaixo do cursor**, então o bot mira o mouse no
quadrado antes de apertar. Sem isso ela saía com o mouse onde quer que ele
tivesse ficado — em geral sobre o minimapa, do último clique de rota.

A fila de apertadas é em **rodadas do anel inteiro**, não em blocos por
quadrado, e tem teto (`LOOT_MAX_APERTADAS`). Em blocos, o teto cortaria os
últimos quadrados sem nenhuma tentativa — e o quadrado certo pode ser justamente
um deles. O teto existe porque 9 quadrados × 3 apertadas × 2 teclas dava 54
ações em ~4 s, muito acima do que uma pessoa faz.

Não pegou nada na caçada? Dois diagnósticos, e eles respondem perguntas
diferentes:

- `python main.py --corpo` mostra a **corrente**: para o bot saber onde caiu o
  corpo, a entrada na battle list e a barra de vida na tela do jogo têm de
  aparecer na **mesma leitura**. Uma sem a outra é o que faz o bot não ir no
  corpo, e o log da caçada não separa os dois casos — eles se consertam em
  lugares diferentes. Ele conta as leituras e diz qual é o elo fraco.
- `python main.py --loot` confere o **gesto**: tecla, clique e geometria da
  tela, com um corpo do lado, e diz como ler cada resultado.

**Limitação conhecida:** com vários bichos na tela, o corpo marcado é o do mais
perto na leitura em que a lista ainda o tinha — e com dois igualmente colados,
esse pode ser o sobrevivente. A varredura em volta cobre o caso comum; separar
de verdade exigiria seguir a identidade de cada criatura entre quadros.

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

**Comparar quadrado é por correlação, não por diferença de pixel.** Medido nos
98 quadrados da captura da caverna: com a folga de 22 que estava em uso, **35%
dos pares de quadrados diferentes** passavam por iguais — um único lugar
aprendido bloqueava 7 dos 8 lados e o bot ficava paralisado ao lado do bicho
(`7 lado(s) fora (0 por parede)` no log). Baixar a folga não resolve: o chão muda
de brilho com a luz. Por correlação, quadrados diferentes ficam em 0,04 de
mediana e o mesmo quadrado escurecido até 50% dá 1,000 — acima de 0,95 só 0,06%
dos pares casam por acidente. Depois da troca: **1 de 98** quadrados casa com o
aprendido, e ele continua reconhecido escurecido.

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

### Paralisia

No Tibia a paralisia derruba a velocidade a quase zero, e sai de duas formas:
qualquer **magia de cura** remove, e **haste** (utani hur) sobrepõe a
velocidade. Os bichos desta cave — bonelord, gazer — paralisam.

O bot **não precisa reconhecer ícone** para saber: paralisado, ele manda o passo
e não sai do lugar, que do ponto de vista dele é idêntico a bater na pedra. O
que separa os dois é **quantos lados falham** — pedra é de um lado, paralisia é
de todos. Dois sinais, e basta um:

- `PARALISIA_FALHAS` passos **seguidos** sem sair do lugar, em pelo menos dois
  lados — o sinal rápido, que dispara em 3 leituras;
- `PARALISIA_LADOS` lados bloqueados ao mesmo tempo — o lento, para quando o
  bot alternou de lado antes.

Detectada, ele conjura `PARALISIA_HOTKEY` e **limpa os bloqueios**: eles eram da
paralisia, não de pedra, e deixá-los de pé faria o bot passar os segundos
seguintes achando que está cercado de parede.

A contrapartida, dita com honestidade: encurralado de verdade — num canto, com
bicho fechando os lados — dá o mesmo sinal, e o bot conjura sem precisar.
Conjurar a mais custa mana; não conjurar deixa o personagem parado apanhando.

### Cura

A emergência tem **cooldown próprio**. Compartilhando o da cura normal, uma cura
que acabou de sair travava a emergência por `HEAL_COOLDOWN` inteiro — medido: a
vida passou do limite forte na leitura 3 e a emergência só saía na 5. Passar do
limite forte é justamente quando não se pode esperar.

Abaixo do limite forte, o bot **alterna** as duas: a emergência tem prioridade e,
enquanto ela está em cooldown, a cura normal sai. Mais cura por segundo quando o
personagem está em perigo — gasta as duas poções, e é de propósito.

**Curar não descarta a leitura.** Havia um `continue` ali, e começando com a vida
abaixo do limite o bot passava a leitura toda curando: medido, 7 curas e só 3
ataques em 40 leituras. Cura e ataque são teclas diferentes e não brigam — a cura
sai primeiro, que é a prioridade, e o resto da leitura continua.

## Decisões que vieram de erro medido

O código está comentado com o *porquê* de cada uma delas.

- **Tentativa e erro é sinal de que falta um sinal.** O bot varria os 9
  quadrados em volta do corpo porque a posição vinha de odometria e errava por
  1 SQM. A pergunta certa não era "como varrer melhor" e sim "o que na tela diz
  onde o corpo está" — e a resposta não exigia reconhecer sprite de corpo, que
  precisaria de uma tabela por espécie: o quadrado que **mudou** desde a última
  leitura com o bicho vivo é o corpo, e o vizinho que nunca teve bicho continua
  igual. De 48 ações por corpo para 6.

- **Dependência escondida vale por defeito.** O loot era chamado dentro do
  `if ENABLE_WALK:`, e o odômetro só era criado com esse mesmo interruptor
  ligado. Resultado: com o andar desligado o bot não saqueava **nada**, nos três
  modos de luta, e nada no log dizia por quê. Medido rodando o laço nas seis
  combinações de modo × andar: antes, 0 miradas e 0 saques nas três com o andar
  desligado; depois, gesto idêntico nas seis. Nenhuma dessas duas amarras tinha
  a ver com saquear.

- **Um teste que reprova a decisão certa não mede o bot, mede o próprio ruído.**
  O cenário da caverna em C com brigas vinha reprovando: passava em 3 de 12
  sementes, e várias "falhas" tinham a varredura completa e correta.
  Instrumentando os cliques, **todos** eram perfeitos — destino certo, erro
  zero. O culpado era o mundo simulado: o empurrão do bicho arrastava o
  personagem uma mediana de meia bandeira por briga (6,9 unidades de arco, com
  15 entre bandeiras), com briga nova a cada ~12 quadros enquanto andar uma
  perna leva 8. Nenhum algoritmo vence um mundo que o move mais depressa do que
  ele anda. Com empurrão físico: 20 de 20 sementes. E como afrouxar um teste é
  suspeito por construção, existe o `testa_briga_dentes.py`: ele roda os mesmos
  cenários com a regra de ouro **deliberadamente quebrada** e exige reprovação —
  8 de 8. Teste que nunca reprova é teste que não existe.

- **O `config.json` só valia dentro da GUI.** Nenhuma linha do `main.py` lia o
  arquivo: rodando pela linha de comando o bot usava os valores padrão do
  código. Isso envenenava justamente os modos de diagnóstico — `--loot` conferia
  a tecla `-` mesmo com outra configurada, e `--teclas` media as diagonais
  padrão. Diagnóstico que mede outra configuração que não a sua responde a
  pergunta errada, e com toda a confiança.

- **Tecla apertada com sucesso não é tecla que chegou.** O bot não pegava nenhum
  loot e o log não tinha um único sinal de erro: ele mirava certo e apertava
  certo, só que o `-` que ele mandava (`VK_OEM_MINUS`, a fileira de cima) não é
  o `-` do numpad (`VK_SUBTRACT`), onde a hotkey podia estar. O teste do loot
  não pegava porque `pyautogui.press` era substituído por um espião — do lado do
  bot, tudo passava. Toda simulação que troca a saída por um espião mede que a
  decisão está certa, e nunca que ela chegou.

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
python testes/roda_tudo.py             # a suíte inteira, com o estado sem enfeite
python testes/roda_tudo.py loot        # só os que casam com "loot"
```

O runner existe porque ler a suíte a olho já deu errado duas vezes: um teste
imprime **dois** vereditos (o `testa_grudado` roda outro cenário dentro de si) e
um grep pelo primeiro `OK` escondia um `FALHOU` na mesma saída; outro imprime um
traceback de propósito, para provar que o laço aguenta erro, e parecia quebrado.
As regras são explícitas: qualquer `FALHOU` reprova o arquivo mesmo que outro
verdito diga OK; `PULADO` é uma terceira categoria e **não** é sucesso; saída
sem nenhum veredito conta como erro, não como sucesso silencioso.

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
python testes/testa_teclas_config.py  # trocar as teclas das diagonais não derruba
python testes/testa_erro_no_laco.py   # erro isolado não mata a caçada
python testes/testa_loot.py           # vai até o corpo, clica, varre, esvazia a fila
python testes/testa_loot_no_laco.py   # o loot no laço inteiro: morreu -> marcou -> saqueou
python testes/testa_loot_modos.py     # o mesmo saque em stand/chase/kite, com e sem rota
python testes/testa_acha_corpo.py     # acha o quadrado do corpo na tela, e admite quando não dá
python testes/testa_gui.py            # o painel cabe na tela e tudo nele é alcançável
python testes/testa_sem_console.py    # o painel escreve no log sem console (pythonw)
python testes/testa_config.py         # o config.json vale também fora da GUI
python testes/testa_briga_dentes.py   # os cenários de rota reprovam um bot quebrado?
python testes/testa_heal.py           # cura começando com vida baixa; emergência na frente
python testes/testa_paralisia.py      # separa pedra de paralisia e conjura a cura
python testes/testa_kite_no_laco.py   # kita no laço do bot, mesmo com o andar desligado
```

`testa_kite.py` usa `tela_cave.png`, uma captura de dentro da cave que vai no
repositório (696 KB): é ela que prova a detecção de criatura contra pixel de
verdade.
`testa_bars.py` e `testa_moribundo.py` precisam de amostras `.npy` que não vão.
`png.py` ali do lado é um leitor de PNG em numpy — o projeto não usa Pillow, e o
mss escreve PNG mas não lê.

## Uma leitura ruim não mata a caçada

Um `KeyError` numa leitura derrubou o bot no meio de uma cave — e o personagem
fica lá, parado, sendo comido. Agora cada volta do laço é protegida: erro
isolado entra no log com o traceback e a volta seguinte tenta de novo; depois de
`ERROS_SEGUIDOS_MAX` erros em sequência ele para, porque aí algo mudou de
verdade (janela fechada, layout diferente) e insistir é chutar.

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
