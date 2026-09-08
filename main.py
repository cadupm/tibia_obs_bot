"""
main.py - Base de cave bot (auto heal + ataque + andar por waypoints).

Uso:
    python main.py              # inicia o loop do bot
    python main.py --bars       # so mostra HP/mana lidos (nao pressiona tecla nenhuma)
    python main.py --calib      # mostra posicao/cor do pixel sob o mouse

Seguranca:
    - Nada e enviado se a janela do Tibia nao estiver em foco.
    - Ctrl+Alt+S (ou Ctrl+C no terminal) para parar a qualquer momento.

ATENCAO: a leitura e por pixel da TELA e a janela do Tibia NAO e capturavel:
com estilo layered (o que o opacity.py aplica) e conteudo desenhado pela GPU, a
captura da propria janela sai toda preta - testado, media 1.8 de 255. Por isso o
bot le do PROJETOR do OBS (Ferramentas > Projetor de fonte), que mostra o jogo
normalmente. OBS_MODE ja vem ligado por causa disso.

Como o bot arruma a tela: projetor e jogo viram "sempre visivel" e so o jogo
recebe foco, ficando jogo (transparente) sobre projetor (mostrando o jogo) sobre
o resto. Assim as teclas vao para o jogo e os pixels vem do projetor. No fim,
tudo e devolvido ao estado anterior.
"""

import argparse
import traceback
import ctypes
import json
import os
import random
import ctypes.wintypes as wt
import time

import keyboard
import mss
import numpy as np
import pygetwindow as gw
import pyautogui

pyautogui.PAUSE = 0  # controlamos os delays manualmente

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

# Sem argtypes o ctypes manda -1 (HWND_TOPMOST) como int de 32 bits e o Windows
# responde ERROR_INVALID_WINDOW_HANDLE (1400): HWND e ponteiro de 64 bits.
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.SetWindowPos.restype = wt.BOOL

# ---------------------------------------------------------------- CONFIGURACAO
# As barras sao DETECTADAS em tempo de execucao (ver detect_bars), entao o bot
# funciona em qualquer resolucao e com o painel lateral em qualquer largura.
# Nao use fracao da resolucao aqui: a barra tem altura fixa de 12px e a largura
# e "janela - paineis fixos", que nao e uma porcentagem constante.
AUTO_DETECT_BARS = True
BAR_SEARCH_ROWS = 80       # quantas linhas do topo do cliente varrer
BAR_MIN_WIDTH = 200        # largura minima para algo ser considerado barra
BAR_TEXT_GAP = 80          # vao maximo tolerado dentro da barra (o texto "155/155")
BAR_NOISE = 20             # runs menores que isto sao respingo (icones, overlay)
BAR_MAX_HEIGHT = 30        # barra de status e fina (~12px); mais que isto nao e barra
BAR_DETECT_TRIES = 8       # tentativas de deteccao (a tela pode estar redesenhando)
DARK_ROW_FRAC = 0.6        # fracao de linhas escuras para a coluna ser trilho vazio
FALLBACK_CLIENT = (1920, 1009)   # tamanho onde HP_BAR/MANA_BAR foram medidos

# Fallback se a deteccao falhar: medido no cliente 1920x1009 de 'Tibia - Caprininho'.
# Offsets RELATIVOS a AREA DE CLIENTE: (dx, dy, largura, altura).
HP_BAR = (12, 5, 769, 12)
MANA_BAR = (811, 5, 745, 12)

# Hotkeys conforme a barra do personagem (verificado em 04/09/2026):
#   F1 = magia (precisa de alvo)          F2 = exura infir (cura, confirmada no chat)
#   F3 = pocao de mana (roxa)             F5 = pocao vermelha
#   F11 = corda, F12 = pa (nao usar como atalho do bot!)
# Interruptores por funcao: cada parte do bot liga e desliga sozinha.
ENABLE_HEAL = True
ENABLE_MANA = True
ENABLE_SPELL = True
ENABLE_ATTACK = True

# Vida e mana maximas do personagem. Com elas preenchidas os limites abaixo
# valem em NUMERO de pontos; deixe None para usar fracao da barra.
# ATUALIZE ao subir de level: um maximo velho desloca todos os limites.
HP_MAX = 155
MANA_MAX = 60

# Convencao dos limites: valor <= 1 e fracao da barra (0.70 = 70%), valor > 1 e
# numero de pontos (110 = 110 de vida). A barra tem 5.0 px por ponto de vida e
# 12.8 px por ponto de mana, entao numero e tao preciso quanto fracao.
HEAL_HOTKEY = "f2"
HEAL_THRESHOLD = 150            # cura (magia) quando a vida cair a 110 ou menos
HEAL_COOLDOWN = 1.0
HEAL_WARN_AFTER = 5             # curas seguidas sem a vida subir antes de avisar

HEAL_STRONG_HOTKEY = "f5"       # emergencia: pocao vermelha
HEAL_STRONG_THRESHOLD = 100      # abaixo de 60 de vida

MANA_HOTKEY = "f3"
MANA_THRESHOLD = 20             # bebe pocao de mana abaixo de 30 de mana
MANA_COOLDOWN = 1.2

# Autocast: teclas repetidas em intervalo fixo (haste, comida, buff, anel...).
# Cada slot tem tecla e intervalo proprios. Intervalo em segundos.
ENABLE_AUTOCAST = True
AUTOCAST_MANA_FLOOR = 18       # nao conjura abaixo disto (pontos ou fracao)
AUTOCAST = [
    {"ativo": False, "tecla": "f7", "intervalo": 30.0},
    {"ativo": False, "tecla": "f8", "intervalo": 60.0},
    {"ativo": False, "tecla": "f9", "intervalo": 120.0},
    {"ativo": False, "tecla": "f10", "intervalo": 300.0},
]

# Ataque: no cliente do usuario, SPACE = atacar a proxima criatura (confirmado:
# engajou o alvo em 0.5s, moldura vermelha na battle list). F1 e magia e precisa
# de alvo ja selecionado, por isso nao servia aqui.
ATTACK_HOTKEY = "space"
# curto de proposito: assim que o alvo morre (moldura vermelha sai) o bot pega o
# proximo bicho quase na hora. Apertar demais nao e problema: a checagem do
# vermelho impede reataque enquanto ha alvo vivo.
ATTACK_COOLDOWN = 0.6

# Combo: com o alvo engajado, a magia entra entre os turnos de ataque. O ataque
# (space) so engaja; o dano corpo a corpo sai por turno sozinho, e a magia entra
# no intervalo. Cada magia tem cooldown proprio - 1s e o default, ajuste aqui.
SPELL_HOTKEY = "f1"
SPELL_COOLDOWN = 1.0
SPELL_MANA_FLOOR = 18      # nao conjura abaixo disto: mana reservada para a cura
SPELL_DELAY_AFTER_ATTACK = 0.25   # s de espera entre a tecla de ataque e a
                                  # magia, para a magia nao comer o turno do
                                  # ataque que acabou de sair

# Battle List: geometria medida no cliente 1920x1009 (entradas de 22px de passo,
# barra de vida de 3px e caixa de sprite de 20x17 a esquerda da barra).
BATTLE_PANEL_W = 200        # largura da coluna do painel direito a varrer
BATTLE_SEARCH_Y = (300, 900)  # faixa vertical onde a lista pode estar (evita o minimapa)
# A barra da entrada encurta com o dano e a parte vazia dela e o MESMO cinza do
# fundo do painel (medido: sat 1, bright 64..76) - nao ha trilho escuro para
# medir o total, como nas barras de status. Por isso o limiar e baixo e quem
# identifica a entrada e o sprite ao lado: com 80px aqui, um bicho abaixo de
# ~62% de vida desaparecia da leitura, o alvo virava "False" e o bot trocava de
# alvo com o bicho ainda vivo.
BATTLE_BAR_MIN_W = 8        # largura minima do pedaco preenchido da barra
BATTLE_BAR_MIN_FRACO = 2    # ... e o minimo quando a coluna das barras ja e
                            # conhecida: o bicho quase morto tem 1-2px de barra
BATTLE_BAR_HEALTHY = 100    # barra "saudavel": ensina a coluna das barras (ancora)
BATTLE_BAR_MAX_H = 6        # a barra da entrada e fina (3px); mais grosso e botao
BATTLE_FRAME_RED = 0.25     # fracao vermelha na moldura para "este e o alvo"
MONSTERS_FILE = "monstros.json"   # sprites aprendidos da battle list
MONSTER_DIFF_MAX = 12             # diferenca media maxima para considerar igual
MONSTER_CORR_MIN = 0.90           # ... ou a mesma forma com outro brilho: o
                                  # cliente escurece o sprite do bicho quase
                                  # morto, e ele nao pode deixar de ser ele
ONLY_KNOWN_MONSTERS = False       # True = so ataca sprite que esta na lista
AUTO_LEARN = False                # aprende sozinho o sprite do bicho que engajar

BATTLE_SPRITE_MIN = 20      # pixels coloridos na caixa do sprite (medido: 34..119
                            # numa entrada de verdade, 0 nas barras do widget Skills)
BATTLE_BAR_MIN_BRIGHT = 80  # brilho minimo do preenchimento da barra. Barra de
                            # bicho vivo e CLARA (verde 0,181,0 medido); quando
                            # o bicho morre o Tibia deixa a barra escura, e sem
                            # este criterio a barra escura passava por "cheia" e
                            # o bot ficava achando que tinha alvo vivo.
BATTLE_SPRITE_TOP_MIN = 8   # coloridos na METADE DE CIMA da caixa. O sprite da
                            # criatura sobe acima da barra (medido 13..44); o
                            # icone das barras de skill fica centralizado na
                            # linha da barra e da 0 ali. Sem isto, "Magic",
                            # "Fist" e "Club" do widget Skills entravam como
                            # bicho na lista - com a battle list vazia.
WALK_RESUME_READS = 5       # leituras seguidas de battle list limpa antes de
                            # voltar a clicar no mapa. Clique durante o ataque
                            # troca chase/stand no cliente, entao aqui se paga
                            # meio segundo para nao arriscar isso.
TARGET_GONE_READS = 3       # leituras seguidas SEM a entrada do bicho para dar
                            # ele por morto. Uma leitura ruim nao vale: enquanto
                            # o bot acha que ha bicho, ele nao anda nem clica no
                            # mapa - clique durante o ataque troca chase/stand.
TARGET_LOST_MAX = 4.0       # s segurando o ataque quando a moldura do alvo some
                            # mas a entrada dele continua na battle list. Passado
                            # isso, assume-se leitura ruim de verdade e reengaja.
ATTACK_CONFIRM = 3          # leituras seguidas sem alvo antes de reengajar: uma
                            # leitura ruim sozinha nao faz o bot trocar de bicho
ATTACK_GIVEUP = 3           # pressionadas sem engajar antes de concluir que a
                            # lista atual nao e atacavel (NPC ou player)

# Selecionar alvo clicando na primeira linha da Battle List (coords de cliente).
# DESLIGADO de proposito: a battle list tambem lista PLAYERS, e clicar nela pode
# fazer voce atacar gente (PK) em vez de monstro.
ENABLE_TARGET_CLICK = False
# ancorado na BORDA DIREITA do cliente (o painel lateral tem largura fixa),
# entao continua valendo em outra resolucao: (dx_da_direita, dy_do_topo)
BATTLE_LIST_FIRST_ENTRY = (-120, 412)

# ---- Waypoints ------------------------------------------------------------
# O trajeto e feito clicando no MINIMAPA: o pathfinding e do proprio cliente,
# que desvia de parede. Contar setas as cegas quebra no primeiro obstaculo.
# Geometria medida no cliente 1920x1009 e escala confirmada na tela: 3 passos
# ao norte deslocaram o minimapa 6px, ou seja 2 px por SQM.
ENABLE_WALK = False
MINIMAP = (1752, 3, 108, 110)   # offsets de cliente: x, y, largura, altura
MINIMAP_PX_SQM = 2              # pixels de minimapa por quadrado NO ZOOM EM USO.
                                # Medido: 2.0 no zoom padrao e 0.5 com zoom out
                                # (1 px = 2 SQM). Rode "python main.py --zoom"
                                # para medir no seu zoom - so afeta os numeros
                                # em SQM dos logs, nao as decisoes, que sao
                                # todas em pixel.
# Rotas ficam em arquivos nomeados dentro de rotas/, para dar conta de mais de
# um cave. Caminho absoluto de proposito: a GUI pode ser aberta de outra pasta.
ROUTES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rotas")
WAYPOINTS_FILE = os.path.join(ROUTES_DIR, "padrao.json")
WALK_TOLERANCE = 4              # px de minimapa (2 SQM). Com a rota toda de
                                # clique, a folga cobre o erro de medicao: nos
                                # testes a chegada ficou entre 0 e 2px do alvo.
WALK_TIMEOUT = 15.0             # s no maximo por trecho
# COMO LUTAR. O cliente tem o proprio modo de luta (stand/chase) nos botoes; o
# que se escolhe aqui e o que o BOT faz enquanto luta:
#   "stand" - manda a tecla de parada ao engajar e nao sai do lugar;
#   "chase" - NAO manda a tecla de parada (ela cancela o follow do cliente
#             junto com o ataque); so para de clicar no mapa e deixa o cliente
#             perseguir. Ponha o cliente em chase nos botoes dele;
#   "kite"  - anda de seta para manter distancia de todo bicho na tela,
#             inclusive do alvo. Setas forcam stand no cliente, o que e
#             justamente o que um kiter quer.
# LOOT. Escolhida a TECLA e nao o clique direito no corpo: a tecla de saque
# rapido do cliente nao precisa de coordenada nenhuma nem de acertar item em
# menu, e o corpo nao tem barra de vida para o bot saber onde ele esta. O que o
# bot faz e a parte que falta: CHEGAR PERTO. Em stand o personagem ja esta
# colado no corpo; em kite ele esta a KITE_DIST de distancia, longe demais.
ENABLE_LOOT = True
LOOT_HOTKEY = "-"               # a tecla de saque rapido, no cliente
LOOT_DIST = 1                   # SQM: daqui o saque alcanca o corpo
LOOT_TENTATIVAS = 3             # apertadas por corpo (saque leva um por vez)
LOOT_COOLDOWN = 0.45            # s entre apertadas
LOOT_PRAZO = 8.0                # s tentando chegar no corpo antes de desistir:
                                # corpo em cima de escada, ou bicho novo no
                                # caminho, e loot que nao vale a cacada
ATTACK_MODE = "stand"
KITE_DIST = 3                   # SQM que se quer manter de qualquer bicho
KITE_COOLDOWN = 0.35            # s entre passos de fuga (velocidade de andar)
KITE_PISADO_MAX = 400           # quadrados guardados de chao ja andado (200 SQM
                                # de rastro; passando disso, esquece e recomeca)
KITE_AVISA_SEM_VER = 6          # leituras com bicho na lista e nada na tela
                                # antes de avisar no log
KITE_CLIQUE_ESPERA = 1.5        # s: se o personagem nao parou nesse tempo, o
                                # trajeto travou e vale clicar de novo. Antes o
                                # clique saia a cada KITE_COOLDOWN e cancelava o
                                # trajeto anterior toda vez - a perseguicao
                                # andava aos centimetros.
KITE_CLIQUE = 2                 # SQM alem da distancia pedida a partir dos quais
                                # se usa clique no mapa em vez de seta: seta e
                                # um quadrado por vez e esbarra em tudo, clique
                                # anda o trecho e desvia de parede.
KITE_FALHAS = 2                 # passos seguidos sem sair do lugar, no mesmo
                                # lado, para chamar de parede. Um so nao prova:
                                # o personagem leva 250-400ms para andar e a
                                # leitura pode chegar no meio do passo.
KITE_BLOQUEIO_MAX = 120.0       # s: teto da espera crescente. Uma parede fica
                                # praticamente fora da conta; obstaculo que
                                # anda volta a ser tentado logo.
KITE_BLOQUEIO = 3.0             # s que um lado fica fora depois de o passo nao
                                # sair do lugar. Nao se reconhece parede na
                                # tela: mede-se o resultado do passo. Expira
                                # porque caixa e bicho saem do caminho, parede
                                # nao.
# Para onde da para fugir, e a tecla de cada lado. As DIAGONAIS sao necessarias,
# nao enfeite: com bicho a esquerda e outro em cima, nenhum dos quatro lados
# retos aumenta a distancia do mais perto - so a diagonal aumenta. No cliente as
# diagonais sao o teclado numerico (7 9 1 3).
# As TECLAS de andar. As setas funcionam sempre; as diagonais dependem do
# cliente. No teste em jogo, as do teclado numerico nao moveram o personagem
# (dezenas de "num9" sem sair do lugar, e um "right" que andou) - por isso elas
# sao configuraveis: no Tibia 13 da para amarrar as diagonais a qualquer tecla
# nos controles do cliente, e ai basta escrever aqui as que voce escolheu.
# A ordem e: cima-esquerda, cima-direita, baixo-esquerda, baixo-direita.
KITE_DIAGONAIS_TECLAS = "num7,num9,num1,num3"


def monta_passos():
    """As teclas de andar com o rumo de cada uma, montado da configuracao."""
    passos = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
    rumos = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    teclas = [t.strip() for t in KITE_DIAGONAIS_TECLAS.split(",") if t.strip()]
    for tecla, rumo in zip(teclas, rumos):
        passos[tecla] = rumo
    return passos


KITE_PASSOS = monta_passos()


def atualiza_passos():
    """
    Refaz KITE_PASSOS a partir da configuracao atual.

    Precisa existir porque o dicionario e montado no import, com as teclas
    PADRAO: mudando KITE_DIAGONAIS_TECLAS na GUI, a decisao passava a devolver
    teclas novas ("q") e quem consultava o dicionario velho estourava
    KeyError - e derrubava o bot no meio da cacada, que e o pior lugar para
    parar. Chamado no arranque de todo modo e depois de aplicar a configuracao.
    """
    global KITE_PASSOS
    KITE_PASSOS = monta_passos()
    return KITE_PASSOS
# Quadrados em que NAO se pisa: escada, buraco, portal. Sao ensinados por
# clique ("python main.py --evitar") e guardados em evitar.json. A comparacao e
# por assinatura reduzida (um pixel a cada 4), que aguenta a animacao do chao.
EVITAR_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "evitar.json")
EVITAR_PASSO = 4                # de quantos em quantos pixels a assinatura pega
EVITAR_DIFF_MAX = 6             # diferenca media para ser o MESMO chao sem nem
                                # precisar de conta. Era 22 e casava 35% dos
                                # pares de quadrados DIFERENTES da caverna.
EVITAR_CORR_MIN = 0.95          # ... ou o mesmo desenho com outro brilho, por
                                # correlacao: acima disso so 0,06% dos pares de
                                # quadrados diferentes casam, e o mesmo quadrado
                                # escurecido ate 50% da 1,000.
EVITAR_VAR_MIN = 4              # desvio minimo dentro do quadrado para valer a
                                # pena guardar: chao chapado nao identifica nada
PARAR_SE_MUDAR_ANDAR = True     # mudou de andar durante o kite? para o bot.
                                # Cair num buraco fugindo de bicho e queda sem
                                # volta automatica, e o lugar onde se cai pode
                                # estar cheio - dai em diante quem decide e a
                                # pessoa, nao o bot.
KITE_DIAGONAIS = False          # As diagonais do teclado numerico NAO moveram o
                                # personagem no teste em jogo: de um log inteiro
                                # de kite, o unico passo que andou foi um
                                # "right" - as dezenas de "num9" nao saiiram do
                                # lugar. Ligue depois de conferir com
                                # "python main.py --teclas", que mede tecla por
                                # tecla (com NumLock ligado costuma funcionar).

# O VIEWPORT do jogo, em offsets de cliente, e o tamanho do quadrado na tela.
# Medido no cliente 1920x1009 do usuario: a area com textura comeca em (221,61)
# e a grade de 15x11 quadrados de 68px fecha exatamente nas bordas (1241, 809).
# Confira no seu layout com "python main.py --kite", que imprime o que enxerga.
GAME_VIEW = (221, 61, 15 * 68, 11 * 68)
TILE_PX = 68                    # px por SQM na tela do jogo
# A barrinha de vida sobre a criatura, medida na captura da cave: moldura de
# preto puro com 31 px de largura e 4 de altura, com 2 linhas de preenchimento
# colorido dentro. A moldura nao encurta com o dano.
CREATURE_BAR_W = (28, 34)       # largura da moldura
CREATURE_BAR_TALL = 4           # altura da moldura, de borda a borda
CREATURE_BORDER_MAX = 25        # ate este brilho o pixel conta como preto puro
CREATURE_BAR_ABOVE = 1          # a criatura fica este tanto de quadrado abaixo
                                # da propria barra

STOP_ATTACK_DELAY = 0.25        # s entre a tecla de parada e a de ataque: o
                                # cliente precisa processar a parada primeiro,
                                # senao ela solta o alvo recem-pego
STOP_WALK_KEY = "esc"           # tecla que cancela o trajeto quando aparece
                                # bicho. Clique no minimapa nao serve: com zoom
                                # out um pixel vale 2 SQM e o clique de "pare"
                                # cai longe, mandando ele andar. Vazio = nao
                                # cancela nada, so para de clicar.
WALK_STOP_TICKS = 2             # leituras sem movimento = o boneco parou
WALK_PROGRESSO = 4              # px de aproximacao que contam como progresso e
                               # renovam o orcamento de cliques
WALK_MAX_CLICKS = 4             # cliques SEM PROGRESSO antes de desistir do
                                # waypoint. Contar clique que aproxima faria o
                                # bot desistir depois de uma briga que o levou
                                # longe, quando ele so precisava de mais trechos.
# DESLIGADO: depois de matar tudo, o bot deve seguir para o ponto que ELE marcou
# no mapa, e nao trocar de destino por estar mais perto de outro. Ligue so se
# preferir que ele corte caminho quando a briga levar o personagem adiante.
WALK_SKIP_TO_NEAREST = False
# Ajuste fino com as setas: DESLIGADO. Teclado acerta o quadrado exato (1 toque
# = 1 SQM), mas nao desvia de nada - testado ao vivo, deu 10 toques sem sair do
# lugar contra uma parede. O clique usa o pathfinding do cliente, que contorna
# obstaculo, e e por isso que a rota inteira vai de mapa. Ligue isto so se
# estiver andando em area aberta e quiser encostar no quadrado exato.
ENABLE_WALK_KEYS = False
WALK_KEYS_MAX = 12              # px: daqui para baixo, anda de seta (6 SQM)
WALK_KEY_COOLDOWN = 0.4         # s entre passos de teclado
WALK_MAX_KEYS = 10              # passos de seta antes de aceitar onde parou
WALK_MAX_LEG = 40               # px: alcance de um clique dentro do minimapa
# Como a rota e gravada:
#   "clique"    -> waypoint = destino de cada clique SEU no minimapa (o padrao,
#                  porque sao os pontos que voce realmente escolheu)
#   "distancia" -> waypoint automatico a cada WALK_RECORD_STEP px andados
# Marcas do mapa como waypoints: voce coloca as marcas no jogo e o bot as usa.
# Melhor que rota gravada, porque a marca e desenhada pelo proprio cliente -
# nao tem deriva, e a CHEGADA e verificada por pixel: a marca fica sobre a cruz
# do personagem (a cruz "se esconde" debaixo dela).
USE_ROUTE_ORDER = True         # havendo rota gravada, segue a ORDEM dela; sem
                               # rota, vale a regra de ouro das marcas
USE_MAP_MARKS = True
MARK_CORE_MIN = 10             # miolo colorido da marca (medido: 13px na azul)
MARK_CORE_MAX = 20
MARK_RING_MIN = 30             # pixels creme do anel em volta do miolo
MARK_ICON = 13                 # lado do recorte do desenho da marca
MARK_COLOR = "azul"            # qual marca seguir: azul, verde ou vermelho
MARK_REACH = 52                # px: alcance de um clique dentro do minimapa
MARK_SEQ_TOL = 14              # px: casar a marca vista com a da sequencia
MARK_CLICK_TOL = 8             # px: clique perto de uma marca conta como ela
MARK_HISTORICO = 40            # marcas guardadas para desfazer o caminho
MARK_VIEW = 46                 # px: ate onde da para confiar que a bandeira
                               # apareceria na leitura. Alem disso ela so saiu
                               # pela beirada do minimapa - continua la.
MARK_BLIND_MAX = 40            # leituras andando as cegas rumo a ultima
                               # bandeira antes de desistir e esperar
MARK_BLIND_RELOC = 3           # leituras sem ver bandeira ate valer a pena se
                               # reencontrar pelo desenho delas
MARK_LOST_MAX = 30             # quadros seguindo pela previsao antes de dar a
                               # bandeira por perdida. O alvo so muda ao CHEGAR
                               # nela: some so quem sumiu de verdade (a bandeira
                               # foi apagada no jogo), nao quem piscou na leitura.
MARK_TRACK_TOL = 6             # px: folga para reencontrar a mesma marca no
                               # quadro seguinte, ja descontado o deslocamento
                               # do conjunto. Nao depende de odometria.
MARK_SHIFT_MAX = 40            # px: maior passo possivel entre duas leituras;
                               # acima disso o deslocamento seria chute.
MARK_ADJ = 1.6                 # o que conta como marca ADJACENTE: ate 1.6x a
                               # distancia da mais proxima. Sem isso o bot, ao
                               # voltar do fundo de um ramo, enxergava marcas do
                               # outro ramo (mais antigas) e pulava para la
                               # atravessando parede em vez de refazer o caminho.
MARK_ARRIVE = 3                # px da cruz: marca em cima = chegou
MARK_MERGE = 8                 # px: mesma marca entre leituras diferentes

RECORD_MODE = "clique"
RECORD_CLICK_TIMEOUT = 3.0      # s esperando o personagem sair do lugar
WALK_RECORD_STEP = 24           # px ANDADOS (comprimento do caminho) por waypoint
WALK_RECORD_MIN_DIST = 6        # nao fecha waypoint colado no anterior
WALK_CLICK_COOLDOWN = 1.5       # s entre cliques rumo ao mesmo waypoint
ODO_HISTORICO = 12              # leituras guardadas para saber o que e
                                # normal de diferenca neste andar
ODO_SALTO = 4.0                 # quantas vezes a mediana o resto tem de
                                # passar para ser mudanca de andar
ODO_RADIUS = 8                  # px de busca por leitura (4 SQM: sobra folga)
WALK_JITTER = [(0, 0), (2, 2), (-2, -2), (2, -2)]   # desvios ao reclicar

# Variacao do movimento. O trajeto ENTRE dois waypoints ja varia por conta
# propria: quem escolhe o caminho e o pathfinding do cliente, a partir de onde o
# personagem esta quando o clique sai - e isso muda a cada volta. Por isso a
# variacao de pixel vem DESLIGADA: ela nao acrescenta muito e atrapalha a
# chegada, porque clique deslocado perto do alvo custa um clique a mais.
# O que fica ligado e a variacao de RITMO (cooldowns), que nao custa precisao.
HUMANIZE = True
WALK_JITTER_MAX = 0        # px de desvio no clique; suba se quiser mais variacao
WALK_STEP_MIN = 1.0        # 1.0 = clica o vetor inteiro que falta

ERROS_SEGUIDOS_MAX = 5          # leituras seguidas com erro antes de parar de
                                # vez. Uma leitura ruim nao pode matar a
                                # cacada; cinco em sequencia significam que algo
                                # mudou de verdade.
LOOP_DELAY = 0.15          # intervalo do while True
STOP = False               # parada por codigo (alem do KILL_KEY)
KILL_KEY = "ctrl+alt+s"    # F12 nao serve: no jogo F12 e a pa
MIN_SAT = 30               # saturacao minima para considerar pixel "preenchido"

# Ler do projetor do OBS ("Projetor - Fonte: ...") em vez da janela do Tibia.
# LIGADO por padrao: a janela do Tibia sai preta na captura (ver docstring).
OBS_MODE = True
OBS_TITLE = "Projetor"

MIN_CLIENT = (400, 300)    # menor area de cliente aceitavel (descarta fantasma)

# API do Windows para foco e opacidade
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x00000002
SW_RESTORE = 9
SW_MAXIMIZE = 3
SW_SHOWMAXIMIZED = 3
WPF_RESTORETOMAXIMIZED = 0x0002
HWND_TOP = 0
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


class WINDOWPLACEMENT(ctypes.Structure):
    """Estado de exibicao da janela: diz se ela deve voltar maximizada."""
    _fields_ = [("length", wt.UINT), ("flags", wt.UINT), ("showCmd", wt.UINT),
                ("ptMinPosition", wt.POINT), ("ptMaxPosition", wt.POINT),
                ("rcNormalPosition", wt.RECT)]


# ------------------------------------------------------------------- UTILIDADES
def is_valid_tibia_title(title):
    """Aceita apenas 'Tibia' ou 'Tibia - <personagem>'."""
    clean_title = title.strip()
    return clean_title == "Tibia" or clean_title.startswith("Tibia - ")


def is_usable(win):
    """
    Descarta janela minimizada e o fantasma de mesmo titulo.

    Windows devolve rect (-32000,-32000) e cliente 0x0 para janela iconificada, e
    as vezes existe uma janela-sombra com o mesmo titulo (160x28). Usar qualquer
    das duas quebra a captura com "Region has zero or negative size".
    """
    try:
        if win.isMinimized or user32.IsIconic(win._hWnd):
            return False
        _, _, cw, ch = client_rect(win)
        return cw >= MIN_CLIENT[0] and ch >= MIN_CLIENT[1]
    except Exception:
        return False


def _maior(cands):
    return max(cands, key=lambda w: w.width * w.height) if cands else None


def find_tibia():
    """
    Janela do jogo: e ela que recebe as teclas.

    Inclui a janela minimizada de proposito: filtrar por is_usable() aqui deixava
    o bot sem saida, porque a janela minimizada era descartada antes de alguem
    poder restaura-la (quem restaura e o setup_windows).
    """
    return _maior([w for w in gw.getAllWindows() if is_valid_tibia_title(w.title)])


def find_projector():
    """Projetor do OBS: fonte de pixels (a janela do Tibia sai preta na captura)."""
    return _maior([w for w in gw.getAllWindows() if OBS_TITLE in w.title])


def client_rect(win):
    """Origem da area de cliente na tela + tamanho: (x, y, w, h).

    Usar a area de cliente (e nao win.left/win.top) mantem os offsets validos
    com qualquer borda/titulo e com a janela maximizada ou nao.
    """
    hwnd = win._hWnd
    rect = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    origin = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    return origin.x, origin.y, rect.right - rect.left, rect.bottom - rect.top


def wait_active(win, timeout=20.0):
    """
    Espera a janela alvo ficar em foco.

    A leitura e por pixel da TELA: com outra janela na frente o bot le a UI dela
    (e ve 0% de vida) em vez do jogo. Detectar as barras nessa situacao falha.
    """
    if win.isActive:
        return True
    print(f"Aguardando '{win.title}' ficar em foco (clique na janela)...")
    limite = time.time() + timeout
    while time.time() < limite:
        if keyboard.is_pressed(KILL_KEY):
            return False
        if win.isActive:
            time.sleep(0.4)          # deixa o compositor desenhar
            return True
        time.sleep(0.3)
    print("Erro: a janela nao ficou em foco.")
    return False


def wait_geometry(win, timeout=5.0):
    """
    Espera a janela reportar geometria coerente.

    Durante a ativacao (e em restore/mudanca de modo) o Windows devolve cliente
    0x0 por alguns instantes; falhar na primeira leitura aborta o bot sem motivo.
    """
    limite = time.time() + timeout
    while time.time() < limite:
        _, _, cw, ch = client_rect(win)
        if cw >= MIN_CLIENT[0] and ch >= MIN_CLIENT[1]:
            return True
        time.sleep(0.2)
    return False


def restore_if_minimized(win):
    """
    Restaura a janela minimizada PRESERVANDO o estado maximizado.

    SW_RESTORE numa janela que estava maximizada antes de minimizar pode devolve-la
    em modo janela. No Tibia isso e destrutivo: o cliente muda de tamanho, o jogo
    refaz o layout dos paineis e toda a geometria medida (barras, battle list)
    deixa de valer. GetWindowPlacement diz como ela deve voltar.
    """
    hwnd = win._hWnd
    if user32.IsIconic(hwnd):
        lugar = WINDOWPLACEMENT()
        lugar.length = ctypes.sizeof(WINDOWPLACEMENT)
        user32.GetWindowPlacement(hwnd, ctypes.byref(lugar))
        era_max = bool(lugar.flags & WPF_RESTORETOMAXIMIZED) or             lugar.showCmd == SW_SHOWMAXIMIZED
        print(f"[setup] '{win.title}' estava minimizada; restaurando"
              f"{' maximizada' if era_max else ''}.")
        user32.ShowWindow(hwnd, SW_MAXIMIZE if era_max else SW_RESTORE)
    return wait_geometry(win)


def focus_window(win, timeout=6.0):
    """Traz a janela para a frente e confirma que ela ficou ativa."""
    hwnd = win._hWnd
    # SW_RESTORE so se estiver minimizada: numa janela maximizada ele DESMAXIMIZA
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)

    limite = time.time() + timeout
    while time.time() < limite:
        if win.isActive:
            time.sleep(0.3)                     # deixa o compositor desenhar
            return True
        # SetForegroundWindow falha quando quem chama nao esta em primeiro plano
        user32.SwitchToThisWindow(hwnd, True)
        time.sleep(0.3)
    return bool(win.isActive)


# estado que o bot alterou nas janelas; desfeito por restore_windows()
_TOPMOST_TOCADAS = []
_ALPHA_ORIGINAL = []


def set_topmost(win, ligar=True):
    """
    Liga/desliga "sempre visivel" na janela.

    Por que topmost e nao apenas subir no z-order: o Windows ignora
    SetWindowPos(HWND_TOP) vindo de um processo que nao esta em primeiro plano -
    ele devolve sucesso e nao move nada. E so uma troca de janela ativa e
    permitida por evento de input, entao ativar projetor e depois jogo tambem
    nao funciona. Marcando os dois como topmost e ativando so o jogo, a pilha
    fica: jogo (transparente, com o teclado) sobre projetor (mostrando o jogo)
    sobre o resto da area de trabalho.
    """
    ok = bool(user32.SetWindowPos(
        win._hWnd, HWND_TOPMOST if ligar else HWND_NOTOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW))
    if ok and ligar and win not in _TOPMOST_TOCADAS:
        _TOPMOST_TOCADAS.append(win)
    return ok


def restore_windows():
    """Desfaz o que o bot mexeu nas janelas: topmost e opacidade."""
    while _TOPMOST_TOCADAS:
        win = _TOPMOST_TOCADAS.pop()
        try:
            user32.SetWindowPos(win._hWnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            print(f"[setup] '{win.title}' devolvida ao z-order normal.")
        except Exception:
            pass
    while _ALPHA_ORIGINAL:
        win, alpha = _ALPHA_ORIGINAL.pop()
        try:
            set_alpha(win, alpha)
            print(f"[setup] opacidade de '{win.title}' devolvida para {alpha}.")
        except Exception:
            pass


def get_alpha(win):
    """Opacidade atual da janela (0-255); 255 quando ela nao e layered."""
    alpha, flags, key = wt.BYTE(), wt.DWORD(), wt.DWORD()
    ok = user32.GetLayeredWindowAttributes(
        win._hWnd, ctypes.byref(key), ctypes.byref(alpha), ctypes.byref(flags))
    if not ok or not (flags.value & LWA_ALPHA):
        return 255
    return alpha.value


def set_alpha(win, valor):
    """Mesma operacao do opacity.py, para o bot poder se corrigir."""
    hwnd = win._hWnd
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED)
    user32.SetLayeredWindowAttributes(hwnd, 0, valor, LWA_ALPHA)


def setup_windows():
    """
    Deixa as janelas na ordem que o bot precisa. Devolve (leitura, teclado).

    Sao dois papeis diferentes:
      - LEITURA: de onde os pixels das barras saem;
      - TECLADO: quem recebe as teclas (sempre a janela do jogo).

    Modo direto: os dois papeis sao a propria janela do Tibia, que precisa estar
    visivel - com opacidade baixa o bot leria o desktop atras dela, entao aqui a
    opacidade e devolvida para 255.

    Modo OBS: o projetor fica ATRAS mostrando o jogo e o Tibia fica NA FRENTE,
    transparente, recebendo as teclas - a tela mostra o projetor atraves dele.
    Por isso a ordem importa: projetor primeiro, Tibia por ultimo.
    """
    jogo = find_tibia()
    if not jogo:
        print("Erro: janela do Tibia nao encontrada (o jogo esta aberto?).")
        return None, None
    if not restore_if_minimized(jogo):
        print("Erro: nao consegui restaurar a janela do Tibia.")
        return None, None

    leitura = jogo
    if OBS_MODE:
        projetor = find_projector()
        if not projetor:
            print(f"Erro: projetor do OBS ('{OBS_TITLE}') nao encontrado.")
            return None, None
        if not restore_if_minimized(projetor):
            print("Erro: nao consegui restaurar o projetor do OBS.")
            return None, None
        leitura = projetor
        print(f"[setup] 1/3 projetor sempre visivel: '{projetor.title}'")
        if not set_topmost(projetor):
            print("        aviso: nao consegui deixar o projetor sempre visivel.")
        print(f"[setup] 2/3 jogo sempre visivel, acima do projetor")
        set_topmost(jogo)
        alpha = get_alpha(jogo)
        if alpha > 250:
            print(f"        aviso: o Tibia esta opaco (alpha {alpha}) e vai cobrir o "
                  f"projetor. Rode 'python opacity.py 1' para ver atraves dele.")
    else:
        alpha = get_alpha(jogo)
        if alpha < 250:
            _ALPHA_ORIGINAL.append((jogo, alpha))
            set_alpha(jogo, 255)
            print(f"[setup] opacidade do Tibia estava em {alpha} (barras ilegiveis); "
                  f"subi para 255 e devolvo no fim.")

    # o jogo entra em foco POR ULTIMO: e ele que tem de receber as teclas
    print(f"[setup] {'3/3 ' if OBS_MODE else ''}foco no jogo: '{jogo.title}'")
    if not focus_window(jogo) and not wait_active(jogo):
        return None, None

    # o projetor/compositor leva um instante para redesenhar depois da troca de
    # z-order: sem esta pausa a deteccao roda sobre pixels ainda em branco
    time.sleep(1.0)

    if OBS_MODE:
        _, _, lw, lh = client_rect(leitura)
        _, _, jw, jh = client_rect(jogo)
        if (lw, lh) != (jw, jh):
            print(f"[setup] aviso: projetor {lw}x{lh} e jogo {jw}x{jh}. O projetor "
                  f"esta escalando a imagem; deixe-o maximizado na mesma resolucao "
                  f"para a leitura ficar 1:1.")

    # revalida a geometria depois de tudo posicionado (era aqui que estourava)
    for papel, win in (("leitura", leitura), ("teclado", jogo)):
        if not wait_geometry(win):
            _, _, cw, ch = client_rect(win)
            print(f"Erro: janela de {papel} com cliente {cw}x{ch} "
                  f"(minimizada, fantasma ou fechada).")
            return None, None

    return leitura, jogo


def grab(region):
    """Captura uma regiao absoluta (x, y, w, h) e devolve um array RGB."""
    x, y, w, h = region
    if w <= 0 or h <= 0:
        raise RuntimeError(f"regiao invalida {region}: a janela foi minimizada?")
    with mss.MSS() as sct:
        shot = sct.grab({"left": x, "top": y, "width": w, "height": h})
    return np.asarray(shot)[:, :, [2, 1, 0]]      # BGRA -> RGB


def to_screen(win, offset):
    """Converte um offset da area de cliente em regiao absoluta de tela."""
    cx, cy, _, _ = client_rect(win)
    dx, dy, w, h = offset
    return (cx + dx, cy + dy, w, h)


def fill_ratio(img, min_sat=MIN_SAT):
    """
    Fracao preenchida de uma barra (0.0 a 1.0).

    Criterio agnostico de cor: o preenchimento e SATURADO (verde, amarelo, vermelho
    ou azul) e o trilho vazio e cinza/escuro. Assim funciona com a barra de HP
    verde do Tibia 13 e continua funcionando se ela mudar de cor com o dano.
    """
    if img.size == 0:
        return 1.0
    img = img.astype(np.int16)
    sat = img.max(axis=2) - img.min(axis=2)
    # any() nas linhas: as colunas sob o texto branco ("155/155") continuam
    # contando, porque acima/abaixo do numero a barra segue colorida.
    columns = (sat > min_sat).any(axis=0)
    return float(columns.mean())


# regioes resolvidas em runtime, por tamanho de area de cliente
_BARS_CACHE = {}


def _runs(mask):
    """Intervalos (inicio, fim) contiguos de True."""
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def _merge(runs, max_gap):
    """Une intervalos separados por um vao de ate max_gap."""
    merged = []
    for a, b in runs:
        if merged and a - merged[-1][1] - 1 <= max_gap:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged


def _blocos(mask, min_len):
    """Mesma mascara, mas so com os trechos contiguos de min_len ou mais."""
    out = np.zeros(len(mask), bool)
    for a, b in _runs(mask):
        if b - a + 1 >= min_len:
            out[a:b + 1] = True
    return out


def detect_bars(win):
    """
    Acha os trilhos de HP e mana varrendo o topo da area de cliente.

    Independe da resolucao: localiza o TRILHO COMPLETO de cada barra (parte
    preenchida + parte vazia) e classifica pela cor - azul = mana, resto = HP.
    Por achar o trilho inteiro, a leitura nao depende de quao cheia a barra esta.

    Nao use fracao da resolucao no lugar disto: a altura da barra e fixa (12px) e
    a largura e "cliente - paineis fixos", que nao e uma porcentagem constante.

    Tres detalhes que a versao ingenua erra:
      - a faixa certa e a MAIS AO TOPO, nao a mais grossa: o topo do viewport do
        jogo tambem e saturado e ocupa mais linhas que as barras;
      - HP e mana ficam a 7px de distancia, menos que o vao do texto ("155/155"),
        entao nao da para separa-las por espaco - separa-se por cor;
      - respingos coloridos de ~12px (icones, overlay de FPS) grudam na barra pelo
        vao do texto, por isso o filtro BAR_NOISE;
      - a barra enche da esquerda para a direita, entao o trilho vazio e absorvido
        so para a direita - estender para a esquerda faz a mana engolir o vazio
        do HP e ler menos mana do que tem.

    Devolve (hp, mana) como offsets de cliente, ou None se nao tiver certeza.
    """
    cx, cy, cw, ch = client_rect(win)
    img = grab((cx, cy, cw, min(BAR_SEARCH_ROWS, ch))).astype(np.int16)
    sat = img.max(axis=2) - img.min(axis=2)
    bright = img.max(axis=2)

    filled = sat > MIN_SAT
    dark = (~filled) & (bright < 60)

    # 1) primeira faixa de linhas com preenchimento longo o bastante
    band = np.where(filled.sum(axis=1) > BAR_MIN_WIDTH)[0]
    if band.size == 0:
        return None
    # altura plausivel: a tela de login e saturada em dezenas de linhas seguidas e
    # seria "detectada" como uma barra de 80px, fazendo o bot agir sobre lixo.
    grupos = [g for g in _merge([(int(y), int(y)) for y in band], 1)
              if 4 <= g[1] - g[0] + 1 <= BAR_MAX_HEIGHT]
    if not grupos:
        return None

    # tenta faixa por faixa, de cima para baixo
    for y0, y1 in grupos:
        achado = _bars_na_faixa(img, filled, dark, y0, y1, cw)
        if achado:
            return achado
    return None


def _bars_na_faixa(img, filled, dark, y0, y1, cw):
    """Extrai (hp, mana) de uma faixa de linhas especifica, ou None."""

    # 2) cor media de cada coluna, olhando so os pixels preenchidos
    faixa, mask = img[y0:y1 + 1], filled[y0:y1 + 1]
    contagem = mask.sum(axis=0)
    media = (faixa * mask[:, :, None]).sum(axis=0) / np.maximum(contagem, 1)[:, None]

    cor = _blocos(contagem > 0, BAR_NOISE)
    azul = cor & (media[:, 2] > media[:, 0]) & (media[:, 2] > media[:, 1])
    quente = cor & ~azul

    # 3) trilho vazio: colunas escuras em quase toda a altura, em blocos largos
    vazio = _blocos(dark[y0:y1 + 1].mean(axis=0) >= DARK_ROW_FRAC, BAR_NOISE)
    blocos_vazios = _runs(vazio)

    # 4) para cada cor: junta o preenchido (unindo o vao do texto DENTRO da mesma
    #    cor, porque HP e mana estao a so 7px de distancia) e absorve o trilho
    #    vazio vizinho, sem invadir a barra da outra cor.
    def trilho_da_cor(base, bloqueio):
        candidatos = []
        for a, b in _merge(_runs(base), BAR_TEXT_GAP):
            mudou = True
            while mudou:
                mudou = False
                for ra, rb in blocos_vazios:
                    # so estende para a DIREITA: a barra enche da esquerda para a
                    # direita, entao a borda esquerda e o inicio do preenchimento
                    # e o vazio esta sempre depois dele.
                    if not (0 <= ra - (b + 1) <= BAR_TEXT_GAP):
                        continue
                    # nao pular por cima da barra da outra cor
                    if bloqueio[b + 1:rb + 1].any():
                        continue
                    b, mudou = rb, True
            if b - a + 1 >= BAR_MIN_WIDTH:
                candidatos.append((a, y0, b - a + 1, y1 - y0 + 1))
        if not candidatos:
            return None
        return max(candidatos, key=lambda reg: reg[2])

    achados = {}
    hp = trilho_da_cor(quente, azul)
    mana = trilho_da_cor(azul, quente)
    if hp:
        achados["hp"] = hp
    if mana:
        achados["mana"] = mana

    if "hp" in achados and "mana" in achados:
        return achados["hp"], achados["mana"]
    return None


def ensure_bars(win, force=False):
    """
    Devolve (hp, mana) resolvidos, ou None se nao souber onde as barras estao.

    Detecta uma vez por tamanho de area de cliente e guarda em cache.
    """
    _, _, cw, ch = client_rect(win)
    chave = (cw, ch)
    if not force and chave in _BARS_CACHE:
        return _BARS_CACHE[chave]

    achado = None
    if chave == FALLBACK_CLIENT:
        # medido a mao neste tamanho: mais confiavel que a deteccao, que nao
        # distingue o trilho vazio do HP do separador de 30px ate a mana e
        # acabava somando o separador ao HP (barra cheia lia 89,6%, logo abaixo
        # do limite de cura - o bot curava sem parar).
        achado = (HP_BAR, MANA_BAR)
    if achado is None and AUTO_DETECT_BARS:
        # a tela pode ainda estar sendo redesenhada; tenta por alguns segundos
        for tentativa in range(BAR_DETECT_TRIES):
            achado = detect_bars(win)
            if achado:
                break
            time.sleep(0.5)

    if achado:
        print(f"[bars] em {cw}x{ch}: hp={achado[0]} mana={achado[1]}")
    elif chave == FALLBACK_CLIENT:
        achado = (HP_BAR, MANA_BAR)
        print(f"[bars] deteccao falhou; usando os valores medidos para {cw}x{ch}: "
              f"hp={HP_BAR} mana={MANA_BAR}")
    else:
        # nao chutar: coordenadas erradas fariam o bot ler lixo e spammar cura
        print(f"[bars] NAO localizei as barras em {cw}x{ch} e os valores de "
              f"fallback sao de {FALLBACK_CLIENT[0]}x{FALLBACK_CLIENT[1]}.")
        print("       Deixe a janela do jogo visivel e com vida/mana cheias, ou "
              "meca com --calib e ajuste HP_BAR/MANA_BAR.")

    _BARS_CACHE[chave] = achado
    return achado


def como_fracao(limite, maximo):
    """
    Converte um limite para fracao da barra (0..1).

    Segue a convencao da configuracao: <= 1 ja e fracao, > 1 e numero de pontos e
    precisa do maximo correspondente.
    """
    if limite is None:
        return None
    if limite <= 1:
        return float(limite)
    if not maximo:
        raise ValueError(f"limite {limite} esta em pontos, mas o maximo nao foi "
                         f"configurado (HP_MAX/MANA_MAX)")
    return min(limite / maximo, 1.0)


def formata(frac, maximo):
    """Mostra a leitura nas duas unidades, quando o maximo e conhecido."""
    if maximo:
        return f"{frac * maximo:.0f}/{maximo} ({frac:.0%})"
    return f"{frac:.0%}"


def read_bars(win):
    """Le HP e mana da janela como fracoes (0.0 a 1.0)."""
    regioes = ensure_bars(win)
    if regioes is None:
        raise RuntimeError("barras nao localizadas")
    hp_region, mana_region = regioes
    hp = fill_ratio(grab(to_screen(win, hp_region)))
    mana = fill_ratio(grab(to_screen(win, mana_region)))
    return hp, mana


_BATTLE_TRACK = 0           # maior barra ja vista: serve de "100%" do alvo
_BATTLE_ANCHOR = {}         # {(cw, ch): x da coluna das barras da battle list}


def battle_assinatura(sprites):
    """
    Identidade da battle list atual, para saber quando ela mudou.

    Serve para o bot lembrar "esta lista aqui nao respondeu ao ataque" sem ficar
    preso a essa conclusao quando aparecer outro bicho.
    """
    return tuple(int(sprite.sum()) for sprite in sprites)


def battle_state(win):
    """
    Le a Battle List e devolve (entradas, atacando, hp_do_alvo, sprites, sprite_do_alvo).

    'sprites' sao os recortes da caixa de cada entrada, na ordem da lista - e o
    que permite reconhecer QUAL bicho esta ali (o cliente desenha o mesmo sprite
    sempre). Nome nao da: seria OCR.

    Sinais medidos na tela:
      - cada entrada tem um sprite colorido (34..119 px coloridos numa caixa de
        20x17) e, a direita dele, uma barra de vida fina (3px);
      - o alvo atual ganha moldura VERMELHA nessa caixa: 49% da moldura vermelha
        no alvo contra 0% nas outras entradas.

    Dois cuidados que vieram de erro observado:
      1. a barra ENCURTA com o dano e a parte vazia dela e o mesmo cinza do fundo
         (sat 1) - nao da para medir o total. Exigir barra larga fazia o bicho
         machucado desaparecer da leitura, o alvo virava False e o bot trocava de
         alvo com o bicho vivo;
      2. aceitar qualquer barra curta enche a leitura de falsas entradas (itens do
         backpack dao barras de 9..12px). Por isso a coluna das barras e usada
         como ancora: todas as entradas reais compartilham o mesmo x, aprendido
         de uma barra saudavel (>=BATTLE_BAR_HEALTHY px).

    CUIDADO: players tambem entram na battle list. Filtre players nos botoes da
    propria janela da Battle List para que "entrada" signifique sempre monstro.
    """
    global _BATTLE_TRACK
    cx, cy, cw, ch = client_rect(win)
    x0 = max(cw - BATTLE_PANEL_W, 0)
    y0, y1 = BATTLE_SEARCH_Y[0], min(BATTLE_SEARCH_Y[1], ch)
    if y1 - y0 < 20 or cw - x0 < 20:
        return 0, False, None, [], None

    img = grab((cx + x0, cy + y0, cw - x0, y1 - y0)).astype(np.int16)
    r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    brilho = img.max(axis=2)
    cheio = (brilho - img.min(axis=2)) > MIN_SAT          # colorido: vale p/ sprite
    # a BARRA ainda precisa ser clara: barra escura e bicho morto. Isto vale so
    # para a barra - aplicar ao sprite derrubava criatura de sprite escuro
    # (medido: uma das tres entradas reais deixava de ser detectada).
    barra_cheia = cheio & (brilho > BATTLE_BAR_MIN_BRIGHT)
    vermelho = (r > 100) & (r > g * 2) & (r > b * 2)

    # linhas com um pedaco preenchido de barra.
    #
    # Com a COLUNA das barras ja aprendida (a ancora), aceita-se barra de 2px: e
    # o bicho quase morto, que e justamente quem nao se pode largar. Antes o
    # minimo era 8px para todo mundo, entao o bicho morrendo sumia da leitura, o
    # bot achava que estava sem alvo, apertava a tecla de ataque de novo e
    # trocava de bicho a um golpe de matar o primeiro.
    chave = (cw, ch)
    ancora = _BATTLE_ANCHOR.get(chave)
    minimo = BATTLE_BAR_MIN_W if ancora is None else BATTLE_BAR_MIN_FRACO
    barras = {}
    for y in range(barra_cheia.shape[0]):
        runs = [run for run in _runs(barra_cheia[y])
                if run[1] - run[0] + 1 >= minimo]
        if not runs:
            continue
        if ancora is not None:
            # com a coluna conhecida, so vale barra NELA - ou barra larga, que
            # nunca e respingo e permite reaprender a coluna se o painel mudar
            # de lugar. Sem isso, os 2px coloridos das linhas do proprio sprite
            # entravam na conta, colavam na barra e o bloco virava alto demais,
            # sendo descartado como botao de painel: o bot parava de ver a
            # entrada inteira.
            validas = [run for run in runs if abs(run[0] - ancora) <= 3] or                       [run for run in runs if run[1] - run[0] + 1 >= BATTLE_BAR_MIN_W]
            if not validas:
                continue
            barras[y] = max(validas, key=lambda run: run[1] - run[0])
            continue
        barras[y] = max(runs, key=lambda run: run[1] - run[0])

    # candidatos: barra fina com sprite colorido a esquerda
    candidatos = []
    for gy0, gy1 in _merge([(y, y) for y in sorted(barras)], 1):
        if gy1 - gy0 + 1 > BATTLE_BAR_MAX_H:
            continue                     # bloco grosso: botao do painel, nao barra
        bx0, bx1 = barras[gy0]
        fatia = (slice(max(gy0 - 15, 0), gy0 + 2), slice(max(bx0 - 23, 0), max(bx0 - 3, 0)))
        caixa_cor, caixa_verm = cheio[fatia], vermelho[fatia]
        if caixa_cor.shape[0] < 3 or caixa_cor.shape[1] < 3:
            continue
        # sem sprite colorido nao e entrada: o widget Skills (Level, Experience)
        # tem barras finas e largas iguais, mas com texto cinza no lugar do sprite
        if caixa_cor.sum() < BATTLE_SPRITE_MIN:
            continue
        # e as barras de habilidade (Magic, Fist, Club) TEM icone colorido; a
        # diferenca e a altura: sprite de criatura ocupa a parte de cima da caixa
        meio = caixa_cor.shape[0] // 2
        if caixa_cor[:meio].sum() < BATTLE_SPRITE_TOP_MIN:
            continue
        moldura = np.concatenate([caixa_verm[0], caixa_verm[-1],
                                  caixa_verm[1:-1, 0], caixa_verm[1:-1, -1]])
        candidatos.append((bx0, bx1 - bx0 + 1,
                           float(moldura.mean()) if moldura.size else 0.0,
                           img[fatia].astype(np.uint8)))

    # ancora: coluna das barras, aprendida de uma barra saudavel
    saudaveis = [c for c in candidatos if c[1] >= BATTLE_BAR_HEALTHY]
    if saudaveis:
        maior = max(saudaveis, key=lambda c: c[1])
        _BATTLE_ANCHOR[chave] = maior[0]
        _BATTLE_TRACK = max(_BATTLE_TRACK, maior[1])
    ancora = _BATTLE_ANCHOR.get(chave)

    if ancora is None:
        # sem ancora ainda: so aceita barra larga, que nao tem falso positivo
        aceitos = [c for c in candidatos if c[1] >= BATTLE_BAR_HEALTHY]
    else:
        aceitos = [c for c in candidatos if abs(c[0] - ancora) <= 3]

    entradas, atacando, alvo_hp = len(aceitos), False, None
    sprites, alvo_sprite = [], None
    for bx0, largura, moldura, sprite in aceitos:
        sprites.append(sprite)
        if moldura >= BATTLE_FRAME_RED:
            atacando = True
            alvo_sprite = sprite         # quem engajou: prova de que e atacavel
            if _BATTLE_TRACK >= 60:
                alvo_hp = min(1.0, largura / _BATTLE_TRACK)
    return entradas, atacando, alvo_hp, sprites, alvo_sprite


# ------------------------------------------------------------------ WAYPOINTS
MOUSEEVENTF_MOVE_ABS = 0x8001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def click_game(x, y, pausa=0.09):
    """
    Clique que o Tibia aceita.

    pyautogui.click nao tem efeito nenhum no cliente (testado: clique no minimapa
    e na battle list, zero reacao). O que funciona e mouse_event com coordenada
    ABSOLUTA normalizada em 65535, movendo antes e com uma pausa entre down e up.
    """
    largura = user32.GetSystemMetrics(0)
    altura = user32.GetSystemMetrics(1)
    ax = int(x * 65535 / max(largura - 1, 1))
    ay = int(y * 65535 / max(altura - 1, 1))
    user32.mouse_event(MOUSEEVENTF_MOVE_ABS, ax, ay, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, ax, ay, 0, 0)
    time.sleep(pausa)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, ax, ay, 0, 0)


def minimap_grab(win):
    """Recorte do minimapa como array RGB."""
    cx, cy, _, _ = client_rect(win)
    dx, dy, w, h = MINIMAP
    return grab((cx + dx, cy + dy, w, h)).astype(np.int16)


def minimap_shift(antes, agora, raio=10):
    """
    Deslocamento (dx, dy) em pixels que melhor alinha 'agora' sobre 'antes'.

    O minimapa e centrado no personagem: quem rola e o mapa. O sinal do
    deslocamento medido e o MESMO do offset a clicar para ir naquela direcao,
    entao waypoint gravado pode ser reproduzido como clique sem inverter nada.
    """
    melhor, escolha = None, (0, 0)
    for dy in range(-raio, raio + 1):
        for dx in range(-raio, raio + 1):
            ay0, by0 = max(0, dy), max(0, -dy)
            ax0, bx0 = max(0, dx), max(0, -dx)
            h, w = antes.shape[0] - abs(dy), antes.shape[1] - abs(dx)
            if h < 60 or w < 60:
                continue
            d = float(np.abs(antes[ay0:ay0 + h, ax0:ax0 + w]
                             - agora[by0:by0 + h, bx0:bx0 + w]).mean())
            if melhor is None or d < melhor:
                melhor, escolha = d, (dx, dy)
    return escolha, melhor


class Odometro:
    """
    Posicao do personagem, por integracao do deslocamento do minimapa.

    A cruz do personagem fica sempre no centro do minimapa: quem rola e o mapa.
    Somando o deslocamento lido a cada amostra da uma posicao ABSOLUTA (em px de
    minimapa, 2 px = 1 SQM) a partir de onde a contagem comecou. Isso e o que
    permite reclicar certo depois de uma luta: o waypoint e uma posicao, nao um
    offset de tela, entao o que falta e sempre "alvo - posicao atual".

    A deriva e zerada em 'ancora()', chamada quando um waypoint e alcancado.
    """

    def __init__(self, win):
        self.win = win
        self.frame = minimap_grab(win)
        self.pos = [0, 0]
        self.restos = []               # o que sobrou de diferenca em cada leitura
        self.parado = 0

    def atualiza(self):
        """Le o minimapa e integra o deslocamento. Devolve o passo lido."""
        agora = minimap_grab(self.win)
        (dx, dy), resto = minimap_shift(self.frame, agora, raio=ODO_RADIUS)
        self.frame = agora
        self.pos[0] += dx
        self.pos[1] += dy
        self.parado = self.parado + 1 if (dx, dy) == (0, 0) else 0
        self.restos.append(resto)
        del self.restos[:-ODO_HISTORICO]
        return dx, dy

    def mudou_de_andar(self):
        """
        O minimapa trocou por inteiro? Entao o personagem mudou de andar.

        Andando pelo mesmo andar, o minimapa apenas ROLA: alinhado, o que sobra
        de diferenca e pouco. Descer uma escada ou cair num buraco troca o mapa
        todo, e nao ha alinhamento que feche - o resto dispara.

        A comparacao e com a MEDIANA dos restos recentes, nao com um numero
        fixo: cada cave tem sua textura, e o que interessa e a mudanca brusca
        em relacao ao que vinha acontecendo.
        """
        if len(self.restos) < ODO_HISTORICO:
            return False
        antigos = sorted(self.restos[:-1])
        mediana = antigos[len(antigos) // 2]
        return self.restos[-1] > max(mediana * ODO_SALTO, 8.0)

    def resync(self):
        """
        Recomeca a contagem do quadro atual, sem integrar o que passou.

        Usado ao voltar de uma pausa (jogo sem foco): o quadro guardado e velho,
        e integrar a diferenca acumulada inventaria um deslocamento que nao houve.
        """
        self.frame = minimap_grab(self.win)
        self.parado = 0

    def ancora(self, alvo):
        """Fixa a posicao no waypoint alcancado, cortando a deriva acumulada."""
        self.pos = [alvo[0], alvo[1]]

    def falta(self, alvo):
        return alvo[0] - self.pos[0], alvo[1] - self.pos[1]


def click_minimap(win, passo):
    """Clica no minimapa a 'passo' pixels do centro (a cruz do personagem)."""
    cx, cy, _, _ = client_rect(win)
    mx = cx + MINIMAP[0] + MINIMAP[2] // 2
    my = cy + MINIMAP[1] + MINIMAP[3] // 2
    click_game(mx + passo[0], my + passo[1])


VK_LBUTTON = 0x01


def clique_no_minimapa(leitura, _ignorado=None):
    """
    Detecta o clique que VOCE deu dentro do minimapa.

    Usa o bit "pressionado desde a ultima chamada" do GetAsyncKeyState (0x0001).
    O bit de "apertado agora" (0x8000) nao serve aqui: a leitura do minimapa leva
    ~100ms e o clique dura menos que isso, entao ele caia entre duas checagens.

    Devolve (False, offset) com o offset em px de minimapa a partir da cruz do
    personagem - a mesma unidade dos waypoints -, ou (False, None).
    """
    estado = user32.GetAsyncKeyState(VK_LBUTTON)
    if not (estado & 0x0001):
        return False, None

    ponto = wt.POINT()
    user32.GetCursorPos(ctypes.byref(ponto))
    cx, cy, _, _ = client_rect(leitura)
    dx = ponto.x - (cx + MINIMAP[0] + MINIMAP[2] // 2)
    dy = ponto.y - (cy + MINIMAP[1] + MINIMAP[3] // 2)
    dentro = abs(dx) <= MINIMAP[2] // 2 and abs(dy) <= MINIMAP[3] // 2
    return False, ((dx, dy) if dentro else None)


def _blocos_conexos(mask):
    """Blocos de pixels vizinhos (8-conectados) na mascara."""
    visto = np.zeros_like(mask)
    grupos = []
    alt, larg = mask.shape
    for y in range(alt):
        for x in range(larg):
            if not mask[y, x] or visto[y, x]:
                continue
            pilha, pts = [(y, x)], []
            visto[y, x] = True
            while pilha:
                py, px = pilha.pop()
                pts.append((py, px))
                for ny in range(max(py - 1, 0), min(py + 2, alt)):
                    for nx in range(max(px - 1, 0), min(px + 2, larg)):
                        if mask[ny, nx] and not visto[ny, nx]:
                            visto[ny, nx] = True
                            pilha.append((ny, nx))
            grupos.append(pts)
    return grupos


MARK_CORES = {
    "azul": lambda r, g, b: (b > 110) & (b > r + 40) & (b > g + 30),
    "verde": lambda r, g, b: (g > 110) & (g > r + 40) & (g > b + 40),
    "vermelho": lambda r, g, b: (r > 110) & (r > g + 40) & (r > b + 40),
}


def detect_marks(win, mm=None, cor=None):
    """
    Marcas do mapa visiveis no minimapa, como offsets (dx, dy) da cruz.

    Procura o MIOLO colorido da marca (a bandeira, o triangulo) com um anel
    creme em volta. Duas razoes para nao procurar o circulo creme inteiro:
    marcas vizinhas se fundem num bloco unico, e o miolo e o que separa a marca
    certa das outras - na cave ha bandeira azul (a rota) misturada com triangulo
    verde e flecha vermelha, que nao sao rota.

    Medido no minimapa: miolo azul de 13px, anel creme de 41 a 60px.
    """
    mm = minimap_grab(win) if mm is None else mm
    r, g, b = mm[:, :, 0], mm[:, :, 1], mm[:, :, 2]
    creme = (r > 170) & (g > 150) & (b > 120) & (r >= b)
    miolo = MARK_CORES[cor or MARK_COLOR](r, g, b)

    cx, cy = mm.shape[1] // 2, mm.shape[0] // 2
    marcas = []
    for pts in _blocos_conexos(miolo):
        if not (MARK_CORE_MIN <= len(pts) <= MARK_CORE_MAX):
            continue
        ys = [ponto[0] for ponto in pts]
        xs = [ponto[1] for ponto in pts]
        bx, by = (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2
        y0, y1 = max(by - 6, 0), min(by + 7, mm.shape[0])
        x0, x1 = max(bx - 6, 0), min(bx + 7, mm.shape[1])
        if creme[y0:y1, x0:x1].sum() < MARK_RING_MIN:
            continue
        marcas.append((bx - cx, by - cy))
    return sorted(marcas, key=lambda m: abs(m[0]) + abs(m[1]))


def icone_da_marca(mm, offset, lado=MARK_ICON):
    """
    Recorte quadrado do desenho da marca, centrado nela.

    Serve para mostrar a marca na lista da rota (a pessoa reconhece qual e pelo
    desenho: bandeira azul, cifrao, cadeado) e para conferir identidade quando a
    geometria sozinha ficaria ambigua.
    """
    alt, larg = mm.shape[:2]
    bx = larg // 2 + offset[0]
    by = alt // 2 + offset[1]
    y0, x0 = by - lado // 2, bx - lado // 2
    if y0 < 0 or x0 < 0 or y0 + lado > alt or x0 + lado > larg:
        return None
    return mm[y0:y0 + lado, x0:x0 + lado].astype(np.uint8)


def _perto(a, b, folga):
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) <= folga


def medir_escala():
    """
    Mede quantos pixels de minimapa valem um SQM no zoom atual.

    Anda alguns passos de teclado num rumo livre e compara com o deslocamento
    lido no minimapa. Precisa da janela em foco e de um lado sem parede.
    """
    leitura, teclado = setup_windows()
    if not leitura:
        return

    print("Medindo a escala do minimapa, passo a passo.")
    # medir passo por passo e pegar o MAIOR deslocamento: passo bloqueado da 0 e
    # afundaria a media. Um passo que anda vale exatamente 1 SQM.
    melhor, amostras = 0, []
    for tecla in ("down", "up", "right", "left"):
        for _ in range(4):
            antes = minimap_grab(leitura)
            pyautogui.press(tecla)
            time.sleep(0.5)
            (dx, dy), _ = minimap_shift(antes, minimap_grab(leitura), raio=16)
            passo = abs(dx) + abs(dy)
            if passo:
                amostras.append(passo)
                melhor = max(melhor, passo)
        if len(amostras) >= 4:
            break

    if not amostras:
        print("nao consegui andar em nenhum rumo; tente num lugar aberto.")
        return None

    print(f"  passos que renderam: {amostras}")
    print(f"\nescala medida: {melhor:.2f} px por SQM "
          f"(MINIMAP_PX_SQM atual = {MINIMAP_PX_SQM})")
    if abs(melhor - MINIMAP_PX_SQM) > 0.2:
        print(f"ajuste MINIMAP_PX_SQM para {melhor:.2f}")
    else:
        print("o valor configurado esta correto para este zoom.")
    return melhor


def record_marks(caminho=None, parar=None, ao_gravar=None):
    """
    Grava a ORDEM da rota: voce CLICA em cada marca, na sequencia que quer.

    As marcas do mapa dizem ONDE ir, mas nao em que ordem - e a ordem importa
    quando o percurso nao e um circulo: entra-se pelo meio, desce-se ate o fim,
    volta-se passando pela entrada e vai-se ao outro fim. Uma sequencia gravada
    aguenta esse vai-e-volta.

    O clique e ENCAIXADO na marca detectada mais proxima, entao errar o pixel
    nao desloca o ponto. Ande o cave enquanto grava: a posicao e mantida pelo
    movimento das proprias marcas, corrigida a cada leitura pelo desenho do
    conjunto - a mesma maquina que o bot usa depois para se achar na rota.

    `parar` e um Event (a GUI usa para o botao Parar); sem ele vale Ctrl+Alt+S.
    `ao_gravar(indice, ponto, icone)` avisa a cada ponto novo.
    """
    leitura, teclado = setup_windows()
    if not leitura:
        return [], []

    caminho = caminho or WAYPOINTS_FILE
    # O clique no minimapa DO JOGO e comando de andar: o personagem sairia
    # caminhando a cada ponto gravado. Por isso a gravacao comeca com o PROJETOR
    # na frente - ele mostra os mesmos pixels nas mesmas coordenadas de tela e
    # nao repassa nada ao jogo, entao da para clicar em todas as marcas com o
    # boneco parado. Clicar na janela do jogo tambem grava, e ai ele anda: serve
    # para quando a rota nao cabe inteira no minimapa.
    if leitura is not teclado:
        focus_window(leitura)
    print(f"Gravando a ordem das marcas '{MARK_COLOR}' em {caminho}.")
    print("CLIQUE em cada marca do minimapa, na ordem da rota.")
    print("No PROJETOR o personagem fica parado; na janela do JOGO ele anda "
          "ate a marca.")

    odo = Odometro(leitura)
    estado = {}
    pontos, icones = [], []
    pausado = False
    while not (parar.is_set() if parar is not None
               else keyboard.is_pressed(KILL_KEY)):
        time.sleep(0.15)
        # vale o foco no jogo OU no projetor: e no projetor que se clica com o
        # boneco parado. Fora dos dois, o clique e de outra coisa e nao conta.
        if not (teclado.isActive or leitura.isActive):
            if not pausado:
                print("\n[record] pausado: o foco saiu do jogo e do projetor")
                pausado = True
            continue
        if pausado:
            odo.resync()
            print("[record] foco de volta")
            pausado = False

        odo.atualiza()
        marcas = track_marks(leitura, estado, odo=odo) or []
        pos = estado.get("pos", (0, 0))

        _, clique = clique_no_minimapa(leitura)
        if not clique or not marcas:
            continue
        perto = min(marcas, key=lambda m: abs(m[0] - clique[0])
                    + abs(m[1] - clique[1]))
        if abs(perto[0] - clique[0]) + abs(perto[1] - clique[1]) > MARK_CLICK_TOL:
            print(f"\n[rota] clique em {clique} nao caiu em marca nenhuma")
            continue

        ponto = (pos[0] + perto[0], pos[1] + perto[1])
        if pontos and _perto(ponto, pontos[-1], MARK_MERGE):
            continue                      # clique repetido na mesma marca
        icone = icone_da_marca(minimap_grab(leitura), perto)
        pontos.append(ponto)
        icones.append(icone)
        # o ponto entra no mapa mental: e ele que segura a posicao no lugar
        estado.setdefault("visitadas", {})[ponto] = len(pontos)
        print(f"[rota] ponto {len(pontos)}: marca em {perto} "
              f"(posicao {ponto})")
        if ao_gravar:
            ao_gravar(len(pontos) - 1, ponto, icone)

    print()
    if pontos:
        save_waypoints(pontos, caminho, icones)
        print(f"[rota] {len(pontos)} pontos gravados. O bot vai seguir essa "
              f"ordem e recomecar no fim.")
    else:
        print("[rota] nada gravado: nenhum clique caiu em marca.")
    return pontos, icones


def track_marks(leitura, estado, andando=True, odo=None):
    """
    Acompanha as marcas do mapa quadro a quadro e anota quais ja foram visitadas.
    Roda SEMPRE, inclusive durante a briga - e essa a diferenca que faz a regra
    de ouro sobreviver ao combate.

    `andando` diz se o personagem esta percorrendo a rota. Na briga ele fica em
    False: o rastreio continua (as marcas nao podem perder a identidade), mas
    NENHUMA visita e registrada. O bicho empurra o personagem para tras, e contar
    esse empurrao como visita invertia o "de onde vim" - era o vai-e-volta
    ENT P4 ENT P5 ENT P4.

    Mantem em `estado`:
      alvo_off  - onde esta agora a bandeira para onde estamos indo;
      atual_off - a bandeira em que estamos pisando;
      veio_off  - a bandeira de onde viemos;
      evitar    - bandeira que nao deu para alcancar;
      pos       - odometria VISUAL: quanto o personagem andou, medido pelo
                  proprio movimento do conjunto de marcas;
      visitadas - {posicao da bandeira: ordem da visita}.

    A odometria daqui nao e a do minimapa. Ela vem das marcas, e a cada chegada e
    reancorada na bandeira pisada, entao o erro nunca passa de um trecho. A do
    minimapa derivava na briga e foi ela que fez o bot perder o alvo e recalcular
    a rota no meio do caminho.

    Devolve as marcas visiveis, ou None se nao houver nenhuma.
    """
    marcas = detect_marks(leitura)

    # sem nenhuma bandeira na tela o bot fica CEGO: se a posicao congelar aqui,
    # quando elas voltarem o mapa mental estara deslocado e todas vao parecer
    # novas - e ai ele se perde. Entao segue pela odometria do minimapa, que
    # deriva mas nao congela, e marca que precisa se reencontrar depois.
    odo_agora = tuple(odo.pos) if odo is not None else None
    if not marcas:
        anterior = estado.get("odo_ant")
        if odo_agora is not None and anterior is not None:
            andou = (odo_agora[0] - anterior[0], odo_agora[1] - anterior[1])
            pos = estado.get("pos", (0, 0))
            estado["pos"] = (pos[0] + andou[0], pos[1] + andou[1])
            # a bandeira se afasta na mesma medida em que o personagem avanca:
            # e assim que ele continua andando no rumo dela sem ve-la
            for chave in ("alvo_off", "atual_off", "veio_off", "evitar"):
                off = estado.get(chave)
                if off is not None:
                    estado[chave] = (off[0] - andou[0], off[1] - andou[1])
        estado["odo_ant"] = odo_agora
        estado["cego"] = estado.get("cego", 0) + 1
        estado["marcas_ant"] = None      # o proximo quadro nao tem com o que casar
        return []
    estava_cego = estado.pop("cego", 0)
    anterior_odo = estado.get("odo_ant")
    estado["odo_ant"] = odo_agora

    # 1) o quanto o conjunto de bandeiras andou desde a leitura anterior. Todas
    # andam juntas (quem se move e o personagem), entao o deslocamento certo e o
    # que alinha o maior numero delas.
    #
    # Com UMA bandeira so na tela nao ha conjunto para casar e a conta fica
    # ambigua - era por isso que o bot perdia a bandeira alvo com duas ou tres na
    # tela e trocava de rumo sem ter chegado. Por isso entra o palpite da
    # odometria do minimapa: ela ja sabe quanto o personagem andou, e a bandeira
    # anda o mesmo, ao contrario. O palpite so desempata; quando as bandeiras
    # concordam entre si, sao elas que mandam.
    palpite = (0, 0)
    if odo_agora is not None and anterior_odo is not None:
        palpite = (-(odo_agora[0] - anterior_odo[0]),
                   -(odo_agora[1] - anterior_odo[1]))

    anteriores = estado.get("marcas_ant") or []
    desloc = palpite
    if anteriores:
        melhor, testados = None, set()
        for a in anteriores:
            for b in marcas:
                d = (b[0] - a[0], b[1] - a[1])
                if d in testados or abs(d[0]) + abs(d[1]) > MARK_SHIFT_MAX:
                    continue
                testados.add(d)
                alinhadas = sum(
                    1 for x in anteriores
                    if any(abs(x[0] + d[0] - y[0]) + abs(x[1] + d[1] - y[1])
                           <= MARK_TRACK_TOL for y in marcas))
                nota = (alinhadas, -(abs(d[0] - palpite[0])
                                     + abs(d[1] - palpite[1])))
                if melhor is None or nota > melhor[0]:
                    melhor = (nota, d)
        if melhor and melhor[0][0] > 0:
            desloc = melhor[1]
    estado["marcas_ant"] = marcas

    # 2) odometria visual: a marca se afastar e o personagem ter andado ao
    # contrario. Com ela cada bandeira ganha uma posicao estavel, que e o que
    # permite lembrar quais ja foram visitadas.
    pos = estado.get("pos", (0, 0))
    pos = (pos[0] - desloc[0], pos[1] - desloc[1])

    # RECONHECIMENTO PELO DESENHO: o conjunto de bandeiras na tela e comparado
    # com o mapa mental e a posicao que encaixa mais delas vale.
    #
    # Roda a cada leitura, nao so ao sair de um trecho cego: a odometria visual
    # escorrega uns poucos pixels por volta e, sem essa correcao, a mesma
    # bandeira acaba virando duas no mapa mental - era o "21 bandeiras" onde ha
    # oito. Corrigir pouco a pouco basta, e por isso a correcao normal e limitada
    # a MARK_MERGE; so depois de ficar cego se aceita um salto grande, e ai
    # exigindo duas bandeiras encaixadas para nao errar de lugar.
    if estado.get("visitadas"):
        de_volta = estava_cego >= MARK_BLIND_RELOC
        achada, encaixes = relocaliza(estado["visitadas"], marcas, pos)
        erro = abs(achada[0] - pos[0]) + abs(achada[1] - pos[1])
        if de_volta and encaixes >= 2:
            if erro > MARK_MERGE:
                print(f"[marca] fiquei {estava_cego} leituras sem ver bandeira; "
                      f"me reencontrei pelo desenho de {encaixes} delas "
                      f"(corrigi {erro} px)")
            pos = achada
        elif encaixes >= 2 and erro <= MARK_MERGE * 2:
            pos = achada          # duas bandeiras encaixando e sinal forte
        elif encaixes >= 1 and erro <= MARK_MERGE:
            pos = achada
    estado["pos"] = pos

    perdidas = estado.setdefault("perdidas", {})

    def casa(chave):
        """
        Onde esta agora, neste quadro, a marca guardada em `estado[chave]`.

        Se ela nao aparece na leitura, NAO se desiste dela na hora: segue pela
        previsao (posicao anterior + deslocamento) por ate MARK_LOST_MAX quadros.
        Um piscar da deteccao - o bicho por cima da marca, o minimapa
        redesenhando - nao pode fazer o bot largar a bandeira no meio do caminho.
        """
        anterior = estado.get(chave)
        if anterior is None:
            return None
        esperado = (anterior[0] + desloc[0], anterior[1] + desloc[1])
        perto = min(marcas, key=lambda o: abs(o[0] - esperado[0])
                    + abs(o[1] - esperado[1]))
        erro = abs(perto[0] - esperado[0]) + abs(perto[1] - esperado[1])
        if erro <= MARK_TRACK_TOL:
            perdidas[chave] = 0
            return perto
        # so e motivo para desistir se ela DEVERIA estar visivel e nao esta. Uma
        # bandeira que apenas saiu pela beirada do minimapa continua existindo:
        # a previsao segue certa enquanto houver outras bandeiras na tela dando
        # o deslocamento, e largar o alvo por isso fazia o bot trocar de rumo a
        # cada dois passos. Lutando (andando=False) tambem nao conta: ele esta
        # parado brigando e a leitura pode falhar.
        deveria_aparecer = (abs(esperado[0]) <= MARK_VIEW
                            and abs(esperado[1]) <= MARK_VIEW)
        if andando and deveria_aparecer:
            perdidas[chave] = perdidas.get(chave, 0) + 1
            if perdidas[chave] > MARK_LOST_MAX:
                perdidas[chave] = 0
                if chave == "alvo_off":
                    print(f"[marca] a bandeira sumiu do lugar em "
                          f"{MARK_LOST_MAX} leituras; escolho outra")
                return None
        return esperado

    for chave in ("alvo_off", "atual_off", "veio_off", "evitar"):
        estado[chave] = casa(chave)

    # 3) passou por baixo de alguma bandeira? Isso e a visita, conferida por
    # pixel: a cruz do personagem some debaixo dela. Vale para QUALQUER marca,
    # nao so a que era o alvo - se o caminho passou por cima de outra, ela
    # tambem foi visitada e e dela que estamos vindo agora.
    visitadas = estado.setdefault("visitadas", {})
    sob_a_cruz = min(marcas, key=lambda m: abs(m[0]) + abs(m[1]))
    if andando and abs(sob_a_cruz[0]) + abs(sob_a_cruz[1]) <= MARK_ARRIVE:
        atual = estado.get("atual_off")
        if (atual is None or abs(atual[0] - sob_a_cruz[0])
                + abs(atual[1] - sob_a_cruz[1]) > MARK_MERGE):
            lugar = marca_conhecida(visitadas, pos, sob_a_cruz)
            # ligacao aprendida: viemos de la e chegamos aqui, entao existe
            # caminho entre as duas. E o que evita o bot mirar uma bandeira do
            # outro lado da pedra so porque em linha reta ela esta perto - numa
            # caverna em "O" os dois bracos quase se encostam.
            de_onde = (marca_conhecida(visitadas, pos, estado["atual_off"])
                       if estado.get("atual_off") is not None else None)
            if de_onde is not None and de_onde != lugar:
                ligacoes = estado.setdefault("ligacoes", {})
                ligacoes.setdefault(lugar, set()).add(de_onde)
                ligacoes.setdefault(de_onde, set()).add(lugar)
            estado["ordem"] = estado.get("ordem", 0) + 1
            nova_para_nos = lugar not in visitadas
            visitadas[lugar] = estado["ordem"]
            # reancora a odometria na bandeira pisada: o erro acumulado morre
            # aqui, a cada chegada
            estado["pos"] = (lugar[0] - sob_a_cruz[0], lugar[1] - sob_a_cruz[1])
            estado["veio_off"] = atual
            estado["atual_off"] = sob_a_cruz
            estado["evitar"] = None    # de outra bandeira o caminho pode ser outro
            print(f"[marca] cheguei numa bandeira "
                  f"({'primeira vez' if nova_para_nos else 'ja conhecida'}); "
                  f"{len(visitadas)} bandeira(s) no mapa mental")
        alvo = estado.get("alvo_off")
        if alvo is not None and abs(alvo[0] - sob_a_cruz[0]) + \
                abs(alvo[1] - sob_a_cruz[1]) <= MARK_MERGE:
            estado["alvo_off"] = None          # chegou onde queria
            estado["cliques"] = 0
    return marcas


def relocaliza(visitadas, marcas, palpite):
    """
    Onde estamos, deduzido do DESENHO das bandeiras na tela.

    Cada par (bandeira na tela, bandeira do mapa mental) propoe uma posicao; vale
    a que encaixa mais bandeiras. Empate vai para a mais perto do palpite atual -
    e o que desfaz a ambiguidade de um corredor com bandeiras igualmente
    espacadas, onde deslocar de um vao encaixa quase tao bem.

    Devolve (posicao, quantas bandeiras encaixaram).
    """
    if not visitadas or not marcas:
        return palpite, 0
    melhor = None
    for off in marcas:
        for conhecida in visitadas:
            # e se esta marca da tela for esta bandeira do mapa mental?
            cand = (conhecida[0] - off[0], conhecida[1] - off[1])
            encaixes = sum(
                1 for o in marcas
                if any(abs(cand[0] + o[0] - c[0]) + abs(cand[1] + o[1] - c[1])
                       <= MARK_MERGE for c in visitadas))
            nota = (encaixes, -(abs(cand[0] - palpite[0])
                                + abs(cand[1] - palpite[1])))
            if melhor is None or nota > melhor[0]:
                melhor = (nota, cand)
    return melhor[1], melhor[0][0]


def marca_conhecida(visitadas, pos, offset):
    """
    A chave desta bandeira no mapa mental: a entrada ja registrada que fica perto
    dela, ou a posicao nova. Sem isso, o erro de um pixel criaria uma bandeira
    nova a cada passagem e nada seria "ja visitado".
    """
    lugar = (pos[0] + offset[0], pos[1] + offset[1])
    for conhecida in visitadas:
        if abs(conhecida[0] - lugar[0]) + abs(conhecida[1] - lugar[1]) <= MARK_MERGE:
            return conhecida
    return lugar


def follow_route(leitura, odo, estado, click_cd):
    """
    Segue a rota GRAVADA, na ordem, e recomeca no fim.

    Diferente da regra de ouro, aqui quem manda e a ordem que a pessoa gravou:
    ela clicou nas marcas na sequencia que queria. Isso da conta de percurso que
    nao e circulo - descer um ramo, voltar passando pela entrada e ir ao outro -
    sem o bot ter de adivinhar nada.

    A localizacao usa a mesma maquina da regra de ouro: odometria tirada do
    movimento das proprias marcas, corrigida a cada leitura pelo desenho do
    conjunto contra os pontos da rota. Por isso a rota gravada num dia continua
    valendo no outro, mesmo comecando de qualquer ponto dela.

    O alvo so muda ao CHEGAR no ponto (marca detectada debaixo da cruz) - ou
    quando o caminho ate ele se prova impossivel, para nao travar a rota.
    """
    rota = estado.get("rota") or []
    if not rota:
        return False
    # a rota e o mapa mental: assim a correcao de posicao pelo desenho das
    # marcas, que ja existe, passa a valer no referencial da gravacao
    if not estado.get("visitadas"):
        estado["visitadas"] = {ponto: 0 for ponto in rota}

    marcas = track_marks(leitura, estado, odo=odo)
    if marcas is None:
        return False

    pos = estado.get("pos", (0, 0))
    if not estado.get("localizado"):
        achada, encaixes = relocaliza(rota, marcas, pos)
        if encaixes < 1:
            return False               # nenhuma marca da rota a vista ainda
        pos = achada
        estado["pos"] = pos
        estado["localizado"] = True
        # comeca pelo ponto mais perto: a pessoa pode ligar o bot em qualquer
        # lugar da rota, nao so no ponto 1
        estado["indice"] = min(range(len(rota)),
                               key=lambda i: abs(rota[i][0] - pos[0])
                               + abs(rota[i][1] - pos[1]))
        print(f"[rota] me localizei pelo desenho de {encaixes} marca(s); "
              f"comeco pelo ponto {estado['indice'] + 1} de {len(rota)}")

    indice = estado.get("indice", 0) % len(rota)
    alvo_ponto = rota[indice]
    alvo = (alvo_ponto[0] - pos[0], alvo_ponto[1] - pos[1])

    # chegou? exige marca DETECTADA sob a cruz, no lugar do ponto
    sob_a_cruz = min(marcas, key=lambda m: abs(m[0]) + abs(m[1])) if marcas else None
    if (sob_a_cruz is not None
            and abs(sob_a_cruz[0]) + abs(sob_a_cruz[1]) <= MARK_ARRIVE
            and abs(alvo[0]) + abs(alvo[1]) <= MARK_MERGE):
        estado["indice"] = (indice + 1) % len(rota)
        estado["cliques"] = 0
        estado["dist_alvo"] = None
        print(f"[rota] cheguei no ponto {indice + 1}/{len(rota)}; "
              f"vou para o {estado['indice'] + 1}")
        return True

    if odo.parado < WALK_STOP_TICKS or not click_cd.ready():
        return True

    distancia = abs(alvo[0]) + abs(alvo[1])
    antes = estado.get("dist_alvo")
    if antes is None or distancia < antes - WALK_PROGRESSO:
        estado["dist_alvo"] = distancia
        estado["cliques"] = 0

    cliques = estado.get("cliques", 0)
    if cliques >= WALK_MAX_CLICKS:
        # o ponto nao esta dando: pula para o proximo em vez de travar a rota
        estado["indice"] = (indice + 1) % len(rota)
        estado["cliques"] = 0
        estado["dist_alvo"] = None
        print(f"[rota] nao cheguei no ponto {indice + 1} em {cliques} cliques "
              f"sem progresso; pulo para o {estado['indice'] + 1}")
        return True

    passo = limita_passo(alvo, MARK_REACH)
    if abs(passo[0]) + abs(passo[1]) == 0:
        return True
    click_minimap(leitura, passo)
    click_cd.mark()
    estado["cliques"] = cliques + 1
    print(f"[rota] ponto {indice + 1}/{len(rota)}: clique {cliques + 1} "
          f"(offset {alvo})")
    return True


def follow_marks(leitura, odo, estado, click_cd):
    """
    Segue as bandeiras do mapa. REGRA DE OURO, na ordem:

      1. a bandeira visivel mais proxima que AINDA NAO FOI VISITADA;
      2. nao havendo nenhuma nova, a visitada ha mais tempo - nunca a ultima;
      3. a ultima visitada so quando ela e a unica opcao alem da que pisamos.

    O alvo so muda quando a cruz branca chega na bandeira: nada de recalcular no
    meio do caminho.
    """
    marcas = track_marks(leitura, estado, odo=odo)
    if marcas is None:
        return False
    alvo = estado.get("alvo_off")

    if not marcas:
        # nenhuma bandeira na tela. Parar aqui deixava o bot plantado no lugar
        # ate alguma reaparecer; entao ele segue no rumo da ultima conhecida,
        # pela odometria, ate acabar a paciencia. Chegada, essa nao: ela so vale
        # com bandeira detectada debaixo da cruz.
        cego = estado.get("cego", 0)
        if alvo is None or cego > MARK_BLIND_MAX:
            if alvo is not None:
                print(f"[marca] {cego} leituras sem ver bandeira nenhuma; "
                      f"solto o rumo e espero uma aparecer")
                estado["alvo_off"] = None
            return False
    elif alvo is None:
        pos = estado.get("pos", (0, 0))
        visitadas = estado.get("visitadas", {})
        ligacoes = estado.get("ligacoes", {})
        veio = estado.get("veio_off")
        rumo = estado.get("rumo")
        evitar = estado.get("evitar")

        def vale(m):
            if abs(m[0]) + abs(m[1]) <= MARK_ARRIVE:
                return False                       # e a que estamos pisando
            if evitar is not None and abs(m[0] - evitar[0]) \
                    + abs(m[1] - evitar[1]) <= MARK_MERGE:
                return False                       # ja tentei e nao alcancei
            return True

        def ordem_da_visita(m):
            """0 = nunca visitada; maior = visitada mais recentemente."""
            return visitadas.get(marca_conhecida(visitadas, pos, m), 0)

        def e_a_ultima(m):
            """A bandeira de onde acabamos de vir."""
            if veio is not None:
                return abs(m[0] - veio[0]) + abs(m[1] - veio[1]) <= MARK_MERGE
            if rumo is not None:      # perdida de vista: vale a direcao
                return m[0] * rumo[0] + m[1] * rumo[1] < 0
            return False

        def longe(m):
            return abs(m[0]) + abs(m[1])

        # De onde estamos pisando, o bot junta DUAS fontes de candidatas:
        #   - as LIGADAS: bandeiras que ele ja alcancou a partir desta, andando.
        #     Valem mesmo fora do minimapa - e assim que ele volta uma rota sem
        #     ficar preso nas ultimas bandeiras;
        #   - as que estao NA TELA agora, que e como o mapa cresce.
        # Usar so as ligadas travava a volta ao ponto de partida: na primeira
        # volta a ligacao com o outro lado ainda nao existe (ela so nasce depois
        # de pisar la), entao ele concluia "unica opcao, volto pelo caminho" e
        # voltava para o ramo que acabara de varrer.
        aqui = (marca_conhecida(visitadas, pos, estado["atual_off"])
                if estado.get("atual_off") is not None else None)
        # ... menos aquelas que ele ja tentou daqui e nao conseguiu alcancar:
        # dessas ele sabe que nao ha caminho, e nao adianta tentar de novo.
        sem_caminho = estado.get("sem_caminho", {}).get(aqui, set())

        def alcancavel(m):
            lugar = marca_conhecida(visitadas, pos, m)
            return lugar not in sem_caminho

        ligadas = [(lugar[0] - pos[0], lugar[1] - pos[1])
                   for lugar in ligacoes.get(aqui, ())]
        ligadas = [m for m in ligadas if vale(m) and alcancavel(m)]
        na_tela = [m for m in marcas if vale(m) and alcancavel(m)]

        candidatas = list(ligadas)
        for m in na_tela:                       # sem repetir a mesma bandeira
            if not any(abs(m[0] - c[0]) + abs(m[1] - c[1]) <= MARK_MERGE
                       for c in candidatas):
                candidatas.append(m)

        def e_ligada(m):
            return any(abs(m[0] - c[0]) + abs(m[1] - c[1]) <= MARK_MERGE
                       for c in ligadas)

        novas = [m for m in candidatas if not ordem_da_visita(m)]
        livres = [m for m in candidatas if not e_a_ultima(m)]

        if novas:
            # bandeira nova vale a qualquer distancia: e assim que o mapa cresce
            alvo = min(novas, key=longe)
            motivo = "mais proxima ainda nao visitada"
        elif livres:
            # ja visitadas: a ligada e vizinha por construcao e vale sempre; a
            # que so aparece na tela precisa estar por perto, senao o alvo vai
            # para a beirada do minimapa e some no meio do caminho
            perto = min(longe(m) for m in livres)
            livres = [m for m in livres
                      if e_ligada(m) or longe(m) <= perto * MARK_ADJ]
            alvo = min(livres, key=ordem_da_visita)
            motivo = "visitada ha mais tempo entre as que dao para alcancar"
        elif candidatas:
            alvo = min(candidatas, key=longe)
            motivo = "unica opcao: volto pelo caminho"
        else:
            return True

        estado["alvo_off"] = alvo
        estado["rumo"] = alvo                  # a direcao em que estamos saindo
        estado["cliques"] = 0
        estado["dist_alvo"] = None
        print(f"[marca] alvo: bandeira em {alvo} ({motivo}); "
              f"{len(candidatas)} candidata(s) "
              f"({len(ligadas)} ligada(s), {len(novas)} nova(s))")

    # anda ate ela: um clique por parada
    if odo.parado < WALK_STOP_TICKS or not click_cd.ready():
        return True

    # o orcamento de cliques e de cliques SEM PROGRESSO: enquanto a bandeira for
    # se aproximando, ele insiste nela o quanto for preciso - o alvo so muda ao
    # chegar. Quem gasta o orcamento e o clique que nao anda nada, que e como se
    # reconhece uma parede no meio do caminho.
    distancia = abs(alvo[0]) + abs(alvo[1])
    antes = estado.get("dist_alvo")
    if antes is None or distancia < antes - WALK_PROGRESSO:
        estado["dist_alvo"] = distancia
        estado["cliques"] = 0

    cliques = estado.get("cliques", 0)
    if cliques >= WALK_MAX_CLICKS:
        # Nao chegou: pedra no caminho, ou a bandeira esta do outro lado da
        # parede. Fica anotado que DAQUI nao se chega la - assim ele nao volta a
        # martelar a mesma parede toda vez que passar por esta bandeira. Nao
        # pode contar como visitada: isso a tiraria da rota para sempre.
        pos = estado.get("pos", (0, 0))
        visitadas = estado.get("visitadas", {})
        daqui = (marca_conhecida(visitadas, pos, estado["atual_off"])
                 if estado.get("atual_off") is not None else None)
        if daqui is not None:
            barreira = estado.setdefault("sem_caminho", {})
            barreira.setdefault(daqui, set()).add(
                marca_conhecida(visitadas, pos, alvo))
        print(f"[marca] nao alcancei a bandeira em {cliques} cliques; nao ha "
              f"caminho daqui ate ela, escolho outra")
        estado["evitar"] = alvo
        estado["alvo_off"] = None
        estado["cliques"] = 0
        estado["dist_alvo"] = None
        return True

    passo = limita_passo(alvo, MARK_REACH)
    if abs(passo[0]) + abs(passo[1]) == 0:
        return True                  # clique no proprio quadrado so faz parar
    click_minimap(leitura, passo)
    click_cd.mark()
    estado["cliques"] = cliques + 1
    print(f"[marca] clique {cliques + 1} (offset {alvo})")
    return True


# ------------------------------------------------------------------ ARQUIVOS
def caminho_rota(nome):
    """Caminho do arquivo de uma rota, a partir do nome que voce deu a ela."""
    limpo = "".join(c for c in str(nome).strip() if c.isalnum() or c in " _-").strip()
    if not limpo:
        return None
    if not limpo.lower().endswith(".json"):
        limpo += ".json"
    return os.path.join(ROUTES_DIR, limpo)


def nome_rota(caminho):
    """Nome amigavel de uma rota, para mostrar na interface."""
    return os.path.splitext(os.path.basename(caminho or ""))[0]


def rotas_disponiveis():
    """Nomes das rotas gravadas em rotas/."""
    if not os.path.isdir(ROUTES_DIR):
        return []
    return sorted(nome_rota(f) for f in os.listdir(ROUTES_DIR)
                  if f.lower().endswith(".json"))


def load_waypoints(caminho=None):
    """
    Le a rota, convertendo de SQM para pixels do zoom EM USO.

    O arquivo guarda a rota em SQM justamente para nao depender do zoom: pixel
    de minimapa vale 2 SQM com zoom out e 0.5 com zoom in, entao uma rota salva
    em pixel deixa de valer quando o zoom muda. Formato antigo (lista de pixels)
    continua sendo lido, assumindo a escala atual.
    """
    caminho = caminho or WAYPOINTS_FILE
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)

    if isinstance(dados, dict):
        pontos = dados.get("pontos", [])
        escala = float(dados.get("escala_px_sqm") or MINIMAP_PX_SQM)
        if abs(escala - MINIMAP_PX_SQM) > 0.05:
            print(f"[waypoints] rota gravada em SQM; convertendo para o zoom "
                  f"atual ({MINIMAP_PX_SQM} px/SQM)")
        return [(int(round(x * MINIMAP_PX_SQM)), int(round(y * MINIMAP_PX_SQM)))
                for x, y in pontos]

    return [tuple(t) for t in dados]


def save_waypoints(pontos, caminho=None, icones=None):
    """
    Salva a rota em SQM, para ela sobreviver a troca de zoom.

    Junto vai o DESENHO de cada marca (recorte do minimapa). Ele nao entra na
    navegacao: serve para a lista da rota mostrar qual marca e qual - bandeira
    azul, cifrao, cadeado - e a pessoa poder reordenar sabendo o que esta
    movendo.
    """
    caminho = caminho or WAYPOINTS_FILE
    pasta = os.path.dirname(os.path.abspath(caminho))
    os.makedirs(pasta, exist_ok=True)
    em_sqm = [(x / MINIMAP_PX_SQM, y / MINIMAP_PX_SQM) for x, y in pontos]
    dados = {"escala_px_sqm": MINIMAP_PX_SQM,
             "unidade": "SQM",
             "pontos": [[round(x, 2), round(y, 2)] for x, y in em_sqm]}
    if icones:
        dados["icones"] = [None if ico is None else np.asarray(ico).tolist()
                           for ico in icones]
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2)
    print(f"[waypoints] {len(pontos)} pontos salvos em {caminho} "
          f"(em SQM, medidos a {MINIMAP_PX_SQM} px/SQM)")


def load_icones(caminho=None):
    """Desenhos das marcas da rota, na mesma ordem dos pontos."""
    caminho = caminho or WAYPOINTS_FILE
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    if not isinstance(dados, dict):
        return []
    return [None if ico is None else np.array(ico, dtype=np.uint8)
            for ico in dados.get("icones", [])]


def assinatura_tile(tile):
    """Reduz o quadrado a uma assinatura comparavel (um pixel a cada 4)."""
    return np.ascontiguousarray(tile[::EVITAR_PASSO, ::EVITAR_PASSO])


def tile_da_tela(img, col, lin):
    """O quadrado (col, lin) da grade do viewport, ou None se cair fora."""
    alt, larg = img.shape[:2]
    x0, y0 = col * TILE_PX, lin * TILE_PX
    if x0 < 0 or y0 < 0 or x0 + TILE_PX > larg or y0 + TILE_PX > alt:
        return None
    return img[y0:y0 + TILE_PX, x0:x0 + TILE_PX]


def load_evitar(caminho=None):
    """Quadrados a evitar: {nome: assinatura}."""
    caminho = caminho or EVITAR_FILE
    if not os.path.exists(caminho):
        return {}
    with open(caminho, encoding="utf-8") as f:
        cru = json.load(f)
    return {nome: np.array(px, dtype=np.uint8) for nome, px in cru.items()}


def save_evitar(lugares, caminho=None):
    """Grava os quadrados a evitar."""
    caminho = caminho or EVITAR_FILE
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump({nome: np.asarray(px).tolist()
                   for nome, px in lugares.items()}, f)
    print(f"[evitar] {len(lugares)} lugar(es) salvo(s) em {caminho}")


def tile_proibido(tile, lugares):
    """
    Nome do lugar a evitar que este quadrado parece ser, ou None.

    Comparar por diferenca media de pixel NAO serve aqui, e isso esta medido nos
    98 quadrados da captura da caverna: com a folga de 22 que estava em uso, 35%
    dos pares de quadrados DIFERENTES passavam por iguais - um unico lugar
    aprendido bloqueava 7 dos 8 lados e o bot ficava paralisado ao lado do bicho
    ("7 lado(s) fora (0 por parede)" no log). So baixar a folga tambem nao
    resolve: o chao muda de brilho com a luz.

    O que separa e a CORRELACAO, que desconta brilho e escala. Na mesma captura:
    quadrados diferentes ficam em 0,04 de mediana (99% abaixo de 0,59), e o
    mesmo quadrado escurecido ate 50% da 1,000. Acima de 0,95 apenas 0,06% dos
    pares casam por acidente.
    """
    if tile is None or not lugares:
        return None
    assinatura = assinatura_tile(tile).astype(np.float32).ravel()
    centrada = assinatura - assinatura.mean()
    forca = float((centrada * centrada).sum())
    for nome, modelo in lugares.items():
        plano = modelo.astype(np.float32).ravel()
        if plano.shape != assinatura.shape:
            continue
        if float(np.abs(assinatura - plano).mean()) <= EVITAR_DIFF_MAX:
            return nome                    # identico, nem precisa de conta
        outro = plano - plano.mean()
        escala = (forca * float((outro * outro).sum())) ** 0.5
        if escala > 1e-6 and float((centrada * outro).sum()) / escala \
                >= EVITAR_CORR_MIN:
            return nome
    return None


def passos_proibidos(img, lugares):
    """
    Quais passos caem em quadrado de nao pisar.

    Olha o quadrado de destino de cada lado e compara com o que foi ensinado.
    Sem isso o kite anda para tras e cai na escada ou no buraco atras dele - e
    de andar em andar nao ha volta automatica.
    """
    if not lugares:
        return set()
    _vx, _vy, vw, vh = GAME_VIEW
    meio_col, meio_lin = (vw // TILE_PX) // 2, (vh // TILE_PX) // 2
    proibidos = set()
    for (px, py) in set(KITE_PASSOS.values()):
        tile = tile_da_tela(img, meio_col + px, meio_lin + py)
        nome = tile_proibido(tile, lugares)
        if nome:
            proibidos.add((px, py))
    return proibidos


def load_monsters(caminho=None):
    """
    Le a lista de monstros: {nome: sprite ou None}.

    Nome com None e um cadastro PENDENTE: existe na lista mas ainda nao tem
    sprite, entao nao reconhece nada. Serve para montar a lista antes de
    encontrar o bicho, e depois ligar o sprite quando ele aparecer.
    """
    caminho = caminho or MONSTERS_FILE
    if not os.path.exists(caminho):
        return {}
    with open(caminho, encoding="utf-8") as f:
        cru = json.load(f)
    return {nome: (np.array(px, dtype=np.uint8) if px else None)
            for nome, px in cru.items()}


def save_monsters(monstros, caminho=None):
    caminho = caminho or MONSTERS_FILE
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump({nome: (arr.tolist() if arr is not None else None)
                   for nome, arr in monstros.items()}, f)
    prontos = sum(1 for a in monstros.values() if a is not None)
    print(f"[monstros] {len(monstros)} na lista ({prontos} com sprite) em {caminho}")


def add_monster_name(nome, monstros=None):
    """
    Cadastra um nome sem sprite.

    O nome fica pendente e NAO filtra nada sozinho - o reconhecimento e por
    sprite. Ligue o sprite com learn_monster quando o bicho aparecer na lista.
    """
    monstros = monstros if monstros is not None else load_monsters()
    limpo = str(nome).strip()
    if not limpo:
        print("[monstros] nome vazio")
        return monstros
    if limpo in monstros:
        print(f"[monstros] '{limpo}' ja esta na lista")
        return monstros
    monstros[limpo] = None
    save_monsters(monstros)
    if ONLY_KNOWN_MONSTERS:
        print(f"[monstros] '{limpo}' cadastrado sem sprite. O filtro esta LIGADO e "
              f"nome sozinho nao reconhece nada, entao esse bicho NAO sera atacado "
              f"ate voce aprender o sprite dele.")
    else:
        print(f"[monstros] '{limpo}' cadastrado sem sprite. O filtro esta "
              f"DESLIGADO, entao o bot ataca qualquer bicho da battle list - "
              f"inclusive esse. O sprite so e necessario para filtrar.")
    return monstros


def sprite_igual(a, b):
    """
    Compara dois sprites de entrada da battle list.

    Dois criterios, e basta um passar:

      1. diferenca media por pixel pequena - o caso normal, mesmo bicho, mesma
         luz;
      2. mesmo DESENHO com outro brilho, medido por correlacao (a media de cada
         um e descontada e a escala normalizada, entao escurecer o sprite todo
         nao muda o resultado).

    O segundo criterio existe por erro observado: com o bicho quase morto o
    cliente ESCURECE o sprite dele na lista. Só com a diferenca media, o sprite
    escuro deixava de casar - e ai o bot dava o bicho por morto, trocava de alvo
    a um golpe de mata-lo, e voltava a clicar no mapa achando a lista sem bicho
    atacavel.
    """
    if a is None or b is None or a.shape != b.shape:
        return False
    x = a.astype(np.float32).ravel()
    y = b.astype(np.float32).ravel()
    if float(np.abs(x - y).mean()) <= MONSTER_DIFF_MAX:
        return True
    x = x - x.mean()
    y = y - y.mean()
    escala = float(np.sqrt((x * x).sum() * (y * y).sum()))
    if escala < 1e-6:                      # sprite chapado: nada a correlacionar
        return False
    return float((x * y).sum() / escala) >= MONSTER_CORR_MIN


def monstros_atacaveis(sprites, monstros, filtrar=None):
    """
    Quantas entradas da battle list contam como bicho para atacar.

    Com ONLY_KNOWN_MONSTERS ligado, so as que batem com um sprite aprendido. Isso
    importa alem do ataque: a battle list tambem lista NPC e player (visto em
    teste: "Flavius" e "Gustavo, The Guard"), e o "space" do Tibia nao ataca NPC.
    Sem esse filtro o bot ficava proibido de andar a rota o tempo todo, porque
    entendia NPC parado como bicho para matar primeiro.
    """
    if filtrar is None:
        filtrar = ONLY_KNOWN_MONSTERS
    if not filtrar:
        return len(sprites)
    return sum(1 for sprite in sprites
               if monstro_conhecido([sprite], monstros) is not None)


def monstro_conhecido(sprites, monstros):
    """Nome do primeiro sprite da lista que esta entre os aprendidos."""
    for sprite in sprites:
        for nome, modelo in monstros.items():
            if sprite_igual(sprite, modelo):
                return nome
    return None


def rename_monster(antigo, novo, monstros=None):
    """
    Renomeia uma entrada da lista, preservando o sprite.

    Serve para batizar o que o bot aprendeu sozinho ("bicho 1" -> "Bonelord").
    Se o nome novo ja existir como cadastro PENDENTE, ele recebe o sprite.
    Nome novo que ja tenha sprite nao e sobrescrito.
    """
    monstros = monstros if monstros is not None else load_monsters()
    limpo = str(novo).strip()
    if antigo not in monstros:
        print(f"[monstros] '{antigo}' nao esta na lista")
        return monstros
    if not limpo or limpo == antigo:
        return monstros
    if monstros.get(limpo) is not None:
        print(f"[monstros] '{limpo}' ja existe com sprite; renomeie ou remova ele "
              f"antes")
        return monstros

    monstros[limpo] = monstros.pop(antigo)
    save_monsters(monstros)
    print(f"[monstros] '{antigo}' renomeado para '{limpo}'")
    return monstros


def auto_learn(alvo_sprite, monstros):
    """
    Aprende sozinho o sprite do bicho que o bot conseguiu engajar.

    Engajar e a prova de que aquilo e atacavel: NPC e player nao entram na
    moldura vermelha com a tecla de atacar. O nome sai automatico ("bicho N") e
    voce renomeia depois. So roda com AUTO_LEARN ligado.
    """
    if not AUTO_LEARN or alvo_sprite is None:
        return monstros, None
    if monstro_conhecido([alvo_sprite], monstros):
        return monstros, None

    usados = [n for n in monstros if n.startswith("bicho ")]
    nome = f"bicho {len(usados) + 1}"
    monstros[nome] = alvo_sprite
    save_monsters(monstros)
    print(f"[monstros] aprendi sozinho o sprite do alvo engajado como '{nome}' "
          f"(renomeie na lista se quiser)")
    return monstros, nome


def learn_monster(win, nome, monstros=None, linha=0):
    """
    Liga o sprite de uma linha da battle list a um nome.

    'linha' e o indice na lista (0 = primeira), entao da para aprender qualquer
    bicho visivel, com ou sem alvo engajado. Se o nome ja existir como cadastro
    pendente, ele so ganha o sprite.
    """
    monstros = monstros if monstros is not None else load_monsters()
    limpo = str(nome).strip()
    if not limpo:
        print("[monstros] de um nome ao monstro")
        return monstros

    entradas, atacando, _, sprites, _ = battle_state(win)
    if not sprites:
        print("[monstros] battle list vazia; nada para aprender")
        return monstros
    if linha >= len(sprites):
        print(f"[monstros] a lista tem {len(sprites)} entrada(s); "
              f"nao existe a linha {linha + 1}")
        return monstros

    novo = "novo" if limpo not in monstros else "atualizado"
    monstros[limpo] = sprites[linha]
    save_monsters(monstros)
    print(f"[monstros] '{limpo}' {novo} com o sprite da linha {linha + 1} "
          f"({entradas} na lista, alvo engajado={atacando})")
    return monstros


# --------------------------------------------------------------------- ACOES
def varia(valor, fracao=0.3):
    """Sacode um valor para o ritmo nao sair sempre igual."""
    if not HUMANIZE or not fracao:
        return valor
    return valor * random.uniform(1 - fracao, 1 + fracao)


class Cooldown:
    """
    Controla o intervalo minimo entre repeticoes de uma acao.

    'variacao' sacode o intervalo a cada uso, para o bot nao agir num compasso
    exato. Fica em zero na cura de proposito: atrasar cura por estetica e
    trocar seguranca por disfarce.
    """

    def __init__(self, seconds, variacao=0.0):
        self.seconds = seconds
        self.variacao = variacao
        self.atual = seconds
        self.last = 0.0

    def ready(self):
        return (time.time() - self.last) >= self.atual

    def mark(self):
        self.last = time.time()
        self.atual = varia(self.seconds, self.variacao)


def auto_heal(hp, mana, heal_cd, mana_cd, forte_cd=None):
    """Aplica cura e mana pot conforme os limites configurados."""
    lim_forte = como_fracao(HEAL_STRONG_THRESHOLD, HP_MAX)
    lim_cura = como_fracao(HEAL_THRESHOLD, HP_MAX)
    lim_mana = como_fracao(MANA_THRESHOLD, MANA_MAX)

    # A EMERGENCIA TEM COOLDOWN PROPRIO. Compartilhando o da cura normal, uma
    # cura que acabou de sair travava a emergencia por HEAL_COOLDOWN inteiro -
    # medido: a vida passou do limite na leitura 3 e a emergencia so saiu na 5.
    # Passar do limite forte e justamente quando nao se pode esperar.
    forte_cd = heal_cd if forte_cd is None else forte_cd
    if (ENABLE_HEAL and HEAL_STRONG_HOTKEY and lim_forte and hp <= lim_forte
            and forte_cd.ready()):
        pyautogui.press(HEAL_STRONG_HOTKEY)
        forte_cd.mark()
        print(f"[heal] emergencia ({HEAL_STRONG_HOTKEY}) - hp {formata(hp, HP_MAX)}")
        return "cura"

    if ENABLE_HEAL and lim_cura and hp <= lim_cura and heal_cd.ready():
        pyautogui.press(HEAL_HOTKEY)
        heal_cd.mark()
        print(f"[heal] cura ({HEAL_HOTKEY}) - hp {formata(hp, HP_MAX)}")
        return "cura"

    if ENABLE_MANA and lim_mana and mana <= lim_mana and mana_cd.ready():
        pyautogui.press(MANA_HOTKEY)
        mana_cd.mark()
        print(f"[mana] pot ({MANA_HOTKEY}) - mana {formata(mana, MANA_MAX)}")
        return "mana"

    return None


def autocast_cooldowns():
    """Um Cooldown por slot ativo, com pequena variacao de ritmo."""
    return [(slot, Cooldown(max(float(slot.get("intervalo", 0) or 0), 1.0), 0.08))
            for slot in AUTOCAST
            if slot.get("ativo") and slot.get("tecla")]


def run_autocast(cooldowns, mana):
    """
    Aperta as teclas de autocast que ja venceram o intervalo.

    Fica abaixo da cura na ordem de prioridade e respeita AUTOCAST_MANA_FLOOR:
    buff que consome a mana reservada para curar sai caro na hora errada.
    """
    if not ENABLE_AUTOCAST:
        return []
    piso = como_fracao(AUTOCAST_MANA_FLOOR, MANA_MAX)
    enviadas = []
    for slot, cd in cooldowns:
        if not cd.ready():
            continue
        if piso is not None and mana < piso:
            continue
        pyautogui.press(slot["tecla"])
        cd.mark()
        enviadas.append(slot["tecla"])
        print(f"[autocast] {slot['tecla']} (a cada {slot['intervalo']:.0f}s, "
              f"mana {formata(mana, MANA_MAX)})")
    return enviadas


def select_target(win):
    """Clica na primeira linha da Battle List para selecionar alvo."""
    if not ENABLE_TARGET_CLICK:
        return False
    cx, cy, cw, ch = client_rect(win)
    dx, dy = BATTLE_LIST_FIRST_ENTRY
    x = cx + (cw + dx if dx < 0 else dx)      # dx negativo = a partir da direita
    y = cy + (ch + dy if dy < 0 else dy)      # dy negativo = a partir de baixo
    click_game(x, y)
    print(f"[target] clique na battle list ({x},{y})")
    return True


class TravaDeAlvo:
    """
    Segura a tecla de ataque enquanto o bicho engajado nao SUMIR da battle list.

    Vida em 1 nao e vida em 0: enquanto a entrada dele estiver la ele esta vivo,
    e no Tibia a tecla de atacar pula para a proxima criatura. Confiar so na
    moldura vermelha nao basta - um quadro lido errado apagaria o alvo e o bot
    trocaria de bicho com o primeiro a um golpe de morrer.

    Como o sprite nao distingue dois bichos iguais, o que se guarda e QUANTAS
    entradas iguais a ele havia no engajamento: caiu esse numero, um morreu - e
    era o nosso.

    Depois de TARGET_LOST_MAX sem moldura com a entrada ainda na lista, solta:
    ai a leitura ruim e persistente e insistir travaria o bot.
    """

    def __init__(self):
        self.sprite = None
        self.iguais = 0
        self.desde = None
        self.avisou = False
        self.sumidas = 0
        self.morreu = False               # um bicho saiu da lista: o loot le

    def atualiza(self, alvo, alvo_sprite, sprites, agora=None):
        """Devolve True se pode apertar a tecla de atacar (nenhum alvo preso)."""
        agora = time.time() if agora is None else agora
        if alvo and alvo_sprite is not None:
            self.sprite = alvo_sprite
            self.iguais = sum(1 for sp in sprites
                              if sprite_igual(sp, alvo_sprite))
            self.desde, self.avisou, self.sumidas = None, False, 0
            return False
        if self.sprite is None:
            return True

        iguais_agora = sum(1 for sp in sprites if sprite_igual(sp, self.sprite))
        if iguais_agora < self.iguais:
            # sumir de UMA leitura nao e morrer: a leitura da battle list falha
            # de vez em quando, e tratar isso como morte fazia o bot voltar a
            # clicar no mapa no meio da luta - o que no cliente troca o modo de
            # luta de "chase" para "stand".
            self.sumidas += 1
            if self.sumidas < TARGET_GONE_READS:
                return False
            print(f"[attack] o bicho que eu atacava saiu da battle list em "
                  f"{self.sumidas} leituras seguidas: morreu, posso trocar")
            self.morreu = True             # o loot le isto e vai buscar o corpo
            self.solta()
            return True
        self.sumidas = 0
        if self.desde is None:
            self.desde = agora
        if not self.avisou:
            self.avisou = True
            print("[attack] perdi a moldura do alvo, mas a entrada dele continua "
                  "na battle list: seguro o ataque para nao trocar de bicho")
        if agora - self.desde > TARGET_LOST_MAX:
            print(f"[attack] {TARGET_LOST_MAX:.0f}s sem moldura e o bicho ainda "
                  f"na lista: solto o alvo e reengajo")
            self.solta()
            return True
        return False

    def solta(self):
        # `morreu` NAO se apaga aqui: quem consome e o loot, na volta seguinte
        self.sprite, self.iguais = None, 0
        self.desde, self.avisou, self.sumidas = None, False, 0


def attack_monster(teclado, entradas, alvo, attack_cd, confirmado=True,
                   sprites=None, monstros=None, permitido=True):
    """
    Engaja um monstro se houver algum sem alvo ativo.

    Recebe o estado da Battle List ja lido. Sem entrada nao ha o que atacar; com
    moldura vermelha o alvo ja esta engajado e o jogo so troca quando ele morrer.

    'confirmado' exige que a ausencia de alvo tenha aparecido em varias leituras
    seguidas (ATTACK_CONFIRM): um unico quadro lido errado faria o bot trocar de
    bicho no meio da luta.

    'permitido' e o freio do chamador: a battle list tambem lista NPC e player, e
    o "space" do Tibia nao ataca esses. O loop desliga isto quando a lista atual
    provou nao responder ao ataque.
    """
    if not ENABLE_ATTACK or not attack_cd.ready() or entradas == 0 or alvo:
        return False
    if not confirmado or not permitido:
        return False

    select_target(teclado)
    pyautogui.press(ATTACK_HOTKEY)
    attack_cd.mark()
    print(f"[attack] {ATTACK_HOTKEY} ({entradas} atacavel(is) na lista, sem alvo)")
    return True


def cast_spell(alvo, mana, spell_cd, nao_antes_de=0.0):
    """
    Solta a magia no alvo engajado, alternando com os turnos de ataque.

    So conjura com alvo vermelho (magia de alvo sem alvo e tecla perdida) e
    acima de SPELL_MANA_FLOOR, para nao gastar a mana que a cura vai precisar.

    'nao_antes_de' segura a magia por SPELL_DELAY_AFTER_ATTACK depois da tecla de
    ataque: conjurar junto com o ataque faz perder o turno que acabou de sair.
    """
    if not ENABLE_SPELL or not SPELL_HOTKEY or not alvo or not spell_cd.ready():
        return False
    if time.time() < nao_antes_de:
        return False                 # turno do ataque ainda saindo
    if mana < como_fracao(SPELL_MANA_FLOOR, MANA_MAX):
        return False

    pyautogui.press(SPELL_HOTKEY)
    spell_cd.mark()
    print(f"[spell] {SPELL_HOTKEY} (mana {formata(mana, MANA_MAX)})")
    return True


def detect_creatures(leitura, img=None):
    """
    Criaturas na tela do jogo, como offsets (dx, dy) em SQM a partir do
    personagem. O personagem em si nao entra na lista.

    O que se procura e a MOLDURA da barrinha de vida que o cliente desenha sobre
    cada criatura. Medida na captura de dentro da cave, ela e assim:

        ###############################     <- 31 px de preto puro
        #VVVVVVVVVVVVVVVVVVVVVVVVVVVVV#     <- 2 linhas de preenchimento
        #VVVVVVVVVVVVVVVVVVVVVVVVVVVVV#
        ###############################     <- preto puro nas quatro bordas

    Procurar so "faixa fina e saturada", como era antes, nao serve no viewport:
    ali ha textura, efeito de magia e item por tudo, e o bot dizia ver 42, 90,
    ate 202 criaturas na tela. Com a moldura preta exigida em cima, embaixo e
    nas duas pontas, o desenho do jogo nao imita mais isso.

    A moldura NAO encurta com o dano - so o preenchimento -, entao a deteccao
    funciona igual com o bicho quase morto, que e justamente quem esta perto.

    A criatura fica um quadrado abaixo da propria barra. O personagem tem barra
    igual, e ela e descartada por estar no quadrado do meio do viewport.
    """
    vx, vy, vw, vh = GAME_VIEW
    if img is None:
        cx, cy, _, _ = client_rect(leitura)
        img = grab((cx + vx, cy + vy, vw, vh))

    # Cada leitura destas acontece a todo passo do kite, e o tempo aqui e atraso
    # de reacao: meio passo atras de um bicho que corre e nunca alcancar. Por
    # isso as contas sao medidas, nao escritas do jeito mais obvio:
    #   img.max(axis=2)      9.0 ms   (reducao no eixo errado)
    #   np.maximum(r, g, b)  0.6 ms   <- 15x mais rapido
    claro = np.maximum(np.maximum(img[:, :, 0], img[:, :, 1]), img[:, :, 2])
    escuro = np.minimum(np.minimum(img[:, :, 0], img[:, :, 1]), img[:, :, 2])
    preto = claro < CREATURE_BORDER_MAX
    colorido = (claro.astype(np.int16) - escuro) > 40

    # PRE-FILTRO. Numa caverna 36% dos pixels sao preto puro, entao procurar so
    # "fileira de preto" da 212 mil candidatos e nao filtra nada. O que e raro e
    # COR: 2% dos pixels. Exigindo fileira de preto em cima, outra igual
    # CREATURE_BAR_TALL-1 linhas abaixo, e cor no meio das duas, sobram 16
    # candidatos - e so esses passam pela conferencia detalhada.
    alt, larg = preto.shape
    minimo = CREATURE_BAR_W[0]
    base = CREATURE_BAR_TALL - 1

    def janela(mascara):
        """Para cada pixel, quantos da mascara ha em [x, x+minimo)."""
        soma = np.cumsum(mascara, axis=1)
        jan = np.zeros_like(soma)
        jan[:, 0] = soma[:, minimo - 1]
        jan[:, 1:larg - minimo + 1] = soma[:, minimo:] - soma[:, :-minimo]
        return jan

    comeca = janela(preto) == minimo
    tem_cor = janela(colorido) > 0
    candidatos = (comeca[:alt - base] & comeca[base:]
                  & (tem_cor[1:alt - base + 1] | tem_cor[2:alt - base + 2]))

    achadas = []
    for y, ini_x in zip(*np.nonzero(candidatos)):
        y, ini_x = int(y), int(ini_x)
        if ini_x > 0 and preto[y, ini_x - 1]:
            continue                             # nao e o comeco da fileira
        fim_x = ini_x
        while fim_x + 1 < larg and preto[y, fim_x + 1]:
            fim_x += 1
        if not (CREATURE_BAR_W[0] <= fim_x - ini_x + 1 <= CREATURE_BAR_W[1]):
            continue
        fundo = y + base
        if not preto[fundo, ini_x:fim_x + 1].all():
            continue
        dentro = slice(y + 1, fundo)
        if not (preto[dentro, ini_x].all() and preto[dentro, fim_x].all()):
            continue
        if not colorido[dentro, ini_x + 1:fim_x].any():
            continue
        achadas.append((ini_x, fim_x, y))

    # a mesma barra aparece na varredura de cada linha da borda de cima; junta
    barras = []
    for ini_x, fim_x, y in achadas:
        if any(abs(b[0] - ini_x) <= 2 and abs(b[2] - y) <= 2 for b in barras):
            continue
        barras.append((ini_x, fim_x, y))

    meio_col, meio_lin = (vw // TILE_PX) // 2, (vh // TILE_PX) // 2
    criaturas = []
    for ini_x, fim_x, y in barras:
        col = int(((ini_x + fim_x) / 2) // TILE_PX)
        lin = int(y // TILE_PX) + CREATURE_BAR_ABOVE
        offset = (col - meio_col, lin - meio_lin)
        if offset == (0, 0) or offset in criaturas:
            continue                     # o proprio personagem, ou repetida
        criaturas.append(offset)
    return criaturas


def longe_o_bastante(criaturas, distancia=None):
    """Distancia do bicho mais perto, em SQM (o Tibia mede pelo maior eixo)."""
    distancia = KITE_DIST if distancia is None else distancia
    if not criaturas:
        return None
    return min(max(abs(dx), abs(dy)) for dx, dy in criaturas)


def passo_de_kite(criaturas, distancia=None, proibidos=(), pisado=(),
                  aqui=None):
    """
    Para que lado andar para ficar EXATAMENTE a `distancia` do bicho mais perto,
    ou None se ja esta bom (ou se andar so piora).

    A distancia tem dois lados, nao um: perto demais e perigo, longe demais e
    perder o bicho - se ele corre, tem de correr atras. A nota de cada posicao e
    (esta na distancia ou mais, o quanto desvia da distancia): assim, estando
    perto demais vale o lado que mais afasta, e estando longe vale o lado que
    mais aproxima, sem nunca escolher um lado que deixe algum bicho perto demais.

    `proibidos` sao passos que nao se pode dar - escada, buraco, portal. Andar
    para um deles nao troca de posicao: troca de andar.

    `pisado` sao os quadrados por onde o personagem JA ANDOU, e `aqui` e onde
    ele esta (nas duas coisas, em px de minimapa). Empatando o resto, prefere-se
    voltar por onde se veio: aquele chao esta provado - nao tem parede, porque o
    personagem passou por ele, e nao tem escada, porque ele nao mudou de andar
    ali. E de graca: nao depende de reconhecer nada na tela.
    """
    distancia = KITE_DIST if distancia is None else distancia
    if not criaturas:
        return None

    def nota_de(lista):
        """
        Quao boa e uma posicao, em tres niveis:

          1. esta na distancia pedida ou mais (seguranca vem primeiro);
          2. o quanto desvia da distancia pedida - perto demais e perigo, longe
             demais e perder o bicho;
          3. a soma das distancias EM LINHA RETA, como desempate fino.

        O terceiro nivel nao e detalhe: o Tibia mede distancia pelo maior eixo,
        e por essa conta sair de (1,0) para (1,1) nao melhora nada - continua
        colado. Em linha reta melhora (1.0 para 1.41), e e esse passo que, no
        seguinte, abre de verdade. Sem ele o bot ficava plantado quando o unico
        lado que aumentava a distancia estava bloqueado por escada.
        """
        perto = longe_o_bastante(lista, distancia)
        seguro = 1 if perto >= distancia else 0
        # o desempate em linha reta vale so quando esta PERTO DEMAIS: ai qualquer
        # ganho de espaco serve. Estando na distancia certa ele nao vale, senao
        # o bot fica andando em circulo para ganhar centesimos de diagonal.
        reta = (0.0 if seguro else
                sum((dx * dx + dy * dy) ** 0.5 for dx, dy in lista))
        return (seguro, -abs(perto - distancia), reta)

    passos = KITE_PASSOS if KITE_DIAGONAIS else {
        t: p for t, p in KITE_PASSOS.items() if 0 in p}
    def conhecido(px, py):
        """O destino deste passo e chao por onde o personagem ja andou?"""
        if aqui is None or not pisado:
            return 0
        destino = (aqui[0] + px * MINIMAP_PX_SQM,
                   aqui[1] + py * MINIMAP_PX_SQM)
        return 1 if destino in pisado else 0

    # a nota da posicao ATUAL tem de ter os mesmos campos, na mesma ordem, que
    # a dos candidatos - senao a comparacao mistura "chao pisado" com "linha
    # reta" e a escolha sai errada (foi o que aconteceu: com escada de um lado,
    # ele voltou a ficar plantado)
    de_agora = nota_de(criaturas)
    melhor, melhor_nota = None, (de_agora[0], de_agora[1], 0, de_agora[2])
    for tecla, (px, py) in passos.items():
        if (px, py) in criaturas or (px, py) in proibidos:
            continue                     # quadrado ocupado, ou lugar de nao pisar
        depois = [(dx - px, dy - py) for dx, dy in criaturas]
        # o chao ja pisado entra ANTES do desempate fino: entre dois lados que
        # resolvem igual o problema do bicho, vale o que se sabe que da para
        # andar e nao muda de andar
        nota = nota_de(depois)
        nota = (nota[0], nota[1], conhecido(px, py), nota[2])
        if nota > melhor_nota:
            melhor, melhor_nota = tecla, nota
    return melhor


def kite(leitura, teclado, kite_cd, lugares=None, odo=None, estado=None):
    """
    Anda para ficar na distancia certa dos bichos - inclusive do alvo.

    Anda de SETA, um quadrado por vez: clique no mapa daria um trajeto inteiro,
    que num kite e o contrario do que se quer. Seta tambem forca o cliente para
    "stand", o que e o modo certo para quem esta kitando.

    PAREDE: nao se tenta reconhecer parede na tela - mede-se o resultado. Depois
    de cada passo, se o personagem NAO saiu do lugar, aquele lado fica bloqueado
    por KITE_BLOQUEIO segundos e o kite escolhe outro. Sem isso o bot fica
    martelando a mesma tecla contra a pedra para sempre, porque nada na tela
    muda para ele decidir diferente.

    O bloqueio expira sozinho: parede nao anda, mas bicho e caixa sim, e o que
    estava bloqueado pode abrir.
    """
    if not kite_cd.ready():
        return False
    estado = {} if estado is None else estado
    agora = time.time()
    bloqueados = estado.setdefault("bloqueados", {})

    # O passo anterior funcionou? Duas falhas seguidas do mesmo lado e que
    # contam como parede: um passo do personagem leva de 250 a 400ms e a leitura
    # pode chegar antes de ele terminar de andar - uma unica falha nao prova
    # nada.
    falhas = estado.setdefault("falhas", {})
    ultimo = estado.pop("ultimo", None)
    if ultimo is not None and odo is not None:
        if tuple(odo.pos) == tuple(estado.get("pos_antes", ())):
            falhas[ultimo] = falhas.get(ultimo, 0) + 1
            if falhas[ultimo] >= KITE_FALHAS:
                # ESPERA CRESCENTE: cada vez que o mesmo lado falha de novo, ele
                # fica fora por mais tempo. Parede nao muda, e testar de novo a
                # cada poucos segundos custa dois passos perdidos toda vez;
                # caixa e bicho saem do caminho, e esses voltam a ser tentados
                # cedo. Um passo bom naquele lado zera a conta.
                vezes = estado.setdefault("vezes", {})
                vezes[ultimo] = min(vezes.get(ultimo, 0) + 1, 8)
                espera = min(KITE_BLOQUEIO * 2 ** (vezes[ultimo] - 1),
                             KITE_BLOQUEIO_MAX)
                bloqueados[ultimo] = agora + espera
                falhas[ultimo] = 0
                print(f"[kite] '{ultimo}' nao saiu do lugar {KITE_FALHAS}x: "
                      f"parede desse lado, evito por {espera:.0f}s")
        else:
            falhas[ultimo] = 0
            estado.setdefault("vezes", {})[ultimo] = 0

    vx, vy, vw, vh = GAME_VIEW
    cx, cy, _, _ = client_rect(leitura)
    img = grab((cx + vx, cy + vy, vw, vh))
    criaturas = detect_creatures(leitura, img=img)
    proibidos = set(passos_proibidos(img, lugares or {}))
    # O bloqueio expira pelo TEMPO, e so. Tentei tambem esquece-lo ao andar
    # alguns quadrados - "parede a esquerda nao diz nada 3 quadrados adiante" -
    # e ficou pior: andando rente a uma parede o bot muda de lugar a cada passo,
    # redescobria a mesma pedra a cada dois quadrados e gastava 10 dos 24 passos
    # nisso. A espera crescente ja separa os dois casos sem precisar de lugar:
    # parede continua falhando e vai ficando mais tempo fora; caixa e bicho
    # saem do caminho, o passo seguinte da certo e a conta zera.
    parados = []
    for tecla_bloqueada, ate in list(bloqueados.items()):
        if ate <= agora:
            del bloqueados[tecla_bloqueada]
            continue
        parados.append(tecla_bloqueada)
        rumo = KITE_PASSOS.get(tecla_bloqueada)
        if rumo is not None:               # tecla que saiu da configuracao
            proibidos.add(rumo)

    perto = longe_o_bastante(criaturas)

    # BICHO QUE CORRE: fechar 6 quadrados de seta sao 6 teclas a KITE_COOLDOWN
    # cada, e cada seta esbarra sozinha em cada pedra do caminho. Um clique no
    # mapa anda o trecho inteiro e desvia de parede pelo caminho do proprio
    # cliente - muito mais rapido para perseguir quem fugiu com pouca vida.
    #
    # Isso vale so no modo kite: aqui as setas ja forcam "stand" no cliente,
    # entao o clique nao troca modo de luta nenhum.
    if perto is not None and perto >= KITE_DIST + KITE_CLIQUE:
        # DEIXAR O CLIQUE TERMINAR. Clique no mapa e um trajeto inteiro, e
        # clicar de novo no meio dele CANCELA o anterior: clicando a cada
        # KITE_COOLDOWN o personagem re-rotava sem parar e andava aos
        # centimetros - era por isso que a perseguicao nao saia do lugar.
        #
        # Entao so se clica com o personagem PARADO (que e como a rota faz), ou
        # depois de KITE_CLIQUE_ESPERA se ele travou no caminho.
        andando = odo is not None and odo.parado < WALK_STOP_TICKS
        desde = agora - estado.get("clicou_em", 0.0)
        if andando and desde < KITE_CLIQUE_ESPERA:
            return False                   # o trajeto de antes ainda esta indo
        alvo = min(criaturas, key=lambda c: max(abs(c[0]), abs(c[1])))
        reta = (alvo[0] ** 2 + alvo[1] ** 2) ** 0.5
        if reta > 0:
            fracao = max(0.0, (reta - KITE_DIST) / reta)
            passo = (int(round(alvo[0] * fracao * MINIMAP_PX_SQM)),
                     int(round(alvo[1] * fracao * MINIMAP_PX_SQM)))
            if abs(passo[0]) + abs(passo[1]) > 0:
                click_minimap(leitura, passo)
                kite_cd.mark()
                estado.pop("ultimo", None)     # clique nao e passo de seta
                estado["clicou_em"] = agora
                print(f"[kite] bicho a {perto} SQM (correu): clico no mapa "
                      f"para chegar a {KITE_DIST} dele")
                return True

    # o chao por onde ele andou: prova de que da para andar e que nao muda de
    # andar. Guardado por quadrado, em px de minimapa.
    pisado = estado.setdefault("pisado", set())
    aqui = None
    if odo is not None:
        passo_px = MINIMAP_PX_SQM
        aqui = (int(round(odo.pos[0] / passo_px)) * passo_px,
                int(round(odo.pos[1] / passo_px)) * passo_px)
        pisado.add(aqui)
        if len(pisado) > KITE_PISADO_MAX:
            pisado.clear()               # cave inteira na memoria nao ajuda
            pisado.add(aqui)

    tecla = passo_de_kite(criaturas, proibidos=proibidos,
                          pisado=pisado, aqui=aqui)
    if tecla is None:
        if perto is not None and perto != KITE_DIST:
            print(f"[kite] sem lado bom: o bicho mais perto esta a {perto} SQM"
                  + (f", {len(proibidos)} lado(s) fora "
                     f"({len(parados)} por parede)" if proibidos else ""))
        return False
    if not teclado.isActive:
        focus_window(teclado)
    pyautogui.press(tecla)
    kite_cd.mark()
    estado["ultimo"] = tecla
    estado["pos_antes"] = tuple(odo.pos) if odo is not None else ()
    # guarda a tela e o lado: caindo de andar, e daqui que sai o retrato do
    # quadrado que fez cair, para nunca mais pisar nele
    estado["tela_antes"] = img
    estado["passo_dado"] = KITE_PASSOS.get(tecla)
    print(f"[kite] {len(criaturas)} bicho(s), o mais perto a {perto} SQM: "
          f"ando para {tecla}"
          + (f" (evitando {len(proibidos)} lado(s))" if proibidos else ""))
    return True


def clique_na_tela_do_jogo(leitura):
    """
    O quadrado do viewport em que VOCE clicou, ou None.

    Mesmo mecanismo do clique no minimapa: o bit de "apertado desde a ultima
    chamada" do GetAsyncKeyState, que nao perde clique curto. Devolve
    (coluna, linha) na grade e o offset (dx, dy) em SQM a partir do personagem.
    """
    if not (user32.GetAsyncKeyState(VK_LBUTTON) & 0x0001):
        return None
    ponto = wt.POINT()
    user32.GetCursorPos(ctypes.byref(ponto))
    cx, cy, _, _ = client_rect(leitura)
    vx, vy, vw, vh = GAME_VIEW
    x = ponto.x - (cx + vx)
    y = ponto.y - (cy + vy)
    if not (0 <= x < vw and 0 <= y < vh):
        return None
    col, lin = int(x // TILE_PX), int(y // TILE_PX)
    meio_col, meio_lin = (vw // TILE_PX) // 2, (vh // TILE_PX) // 2
    return (col, lin), (col - meio_col, lin - meio_lin)


def record_evitar(segundos=120.0):
    """
    Ensina os quadrados de NAO PISAR: escada, buraco, portal, teleporte.

    Clique em cada um deles na tela do jogo. O quadrado e recortado e guardado
    em evitar.json; no modo kite, o bot deixa de andar para qualquer lado cujo
    quadrado de destino se pareca com um desses - e assim ele nao cai de andar
    fugindo de bicho, que e queda sem volta automatica.

    Clique no PROJETOR para nao mexer no personagem: o clique na tela do jogo
    anda ou usa item. Ctrl+Alt+S para salvar e sair.
    """
    leitura, teclado = setup_windows()
    if not leitura:
        return
    if leitura is not teclado:
        focus_window(leitura)          # clicar aqui nao mexe no personagem
    lugares = load_evitar()
    print(f"{len(lugares)} lugar(es) ja ensinado(s): "
          f"{', '.join(lugares) or 'nenhum'}")
    print("CLIQUE em cada quadrado de nao pisar (escada, buraco, portal).")
    print("Clique no PROJETOR: na janela do jogo o clique anda ou usa item.")
    print("Ctrl+Alt+S para salvar e sair." + chr(10))

    vx, vy, vw, vh = GAME_VIEW
    fim = time.time() + segundos
    novos = 0
    while time.time() < fim and not keyboard.is_pressed(KILL_KEY):
        time.sleep(0.1)
        onde = clique_na_tela_do_jogo(leitura)
        if not onde:
            continue
        (col, lin), offset = onde
        cx, cy, _, _ = client_rect(leitura)
        img = grab((cx + vx, cy + vy, vw, vh))
        tile = tile_da_tela(img, col, lin)
        if tile is None:
            continue
        ja = tile_proibido(tile, lugares)
        if ja:
            print(f"[evitar] esse quadrado ja e '{ja}'")
            continue
        if float(assinatura_tile(tile).std()) < EVITAR_VAR_MIN:
            print("[evitar] esse quadrado e chapado demais (sem desenho) para "
                  "reconhecer depois; clique num com a escada visivel")
            continue
        nome = f"lugar{len(lugares) + 1}"
        lugares[nome] = assinatura_tile(tile)
        novos += 1
        arquivo = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               f"evitar_{nome}.png")
        grande = np.repeat(np.repeat(tile, 3, axis=0), 3, axis=1)
        mss.tools.to_png(np.ascontiguousarray(grande).tobytes(),
                         (grande.shape[1], grande.shape[0]), output=arquivo)
        print(f"[evitar] '{nome}' guardado do quadrado {offset} "
              f"(recorte em {os.path.basename(arquivo)})")

    if novos:
        save_evitar(lugares)
    else:
        print("[evitar] nada novo ensinado.")
    restore_windows()


def aprende_o_que_derrubou(estado, lugares):
    """
    Guarda o quadrado que acabou de fazer o personagem mudar de andar.

    O minimapa NAO marca piso que muda de andar - conferido: o vermelho da
    paleta que eu esperava ser escada e telhado de casa, 111 blocos espalhados
    acompanhando os predios. Sem esse sinal, nao ha como saber de antemao que um
    quadrado e escada; o que da e cair nele UMA vez e guardar o retrato, e dai
    em diante ele fica de fora.

    Devolve o nome dado ao lugar, ou None se nao havia o que guardar.
    """
    tela = estado.get("tela_antes")
    passo = estado.get("passo_dado")
    if tela is None or passo is None:
        return None
    _vx, _vy, vw, vh = GAME_VIEW
    meio_col, meio_lin = (vw // TILE_PX) // 2, (vh // TILE_PX) // 2
    tile = tile_da_tela(tela, meio_col + passo[0], meio_lin + passo[1])
    if tile is None:
        return None
    if tile_proibido(tile, lugares):
        return None                        # ja conhecido; caiu de outro jeito
    if float(assinatura_tile(tile).std()) < EVITAR_VAR_MIN:
        print("[evitar] o quadrado que me derrubou e chapado demais para "
              "reconhecer depois; nao guardei")
        return None
    nome = f"queda{len(lugares) + 1}"
    lugares[nome] = assinatura_tile(tile)
    save_evitar(lugares)
    arquivo = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           f"evitar_{nome}.png")
    grande = np.repeat(np.repeat(tile, 3, axis=0), 3, axis=1)
    mss.tools.to_png(np.ascontiguousarray(grande).tobytes(),
                     (grande.shape[1], grande.shape[0]), output=arquivo)
    return nome


def show_teclas():
    """
    Mede QUAIS teclas de movimento realmente andam no seu cliente.

    Aperta cada uma e le no minimapa se o personagem saiu do lugar. Serve para o
    kite: as setas andam sempre, mas as diagonais do teclado numerico dependem
    de NumLock e da configuracao do cliente - e uma tecla que nao anda faz o bot
    parecer travado, apertando sem sair do lugar.

    Precisa de um lugar sem parede em volta: parede tambem da "nao andou".
    """
    atualiza_passos()          # a configuracao manda nas teclas
    leitura, teclado = setup_windows()
    if not leitura:
        return
    print("Apertando cada tecla de movimento e medindo no minimapa.")
    print("Fique num lugar aberto: parede tambem aparece como 'nao andou'."
          + chr(10))
    odo = Odometro(leitura)
    resultado = {}
    for tecla in KITE_PASSOS:
        odo.atualiza()
        antes = tuple(odo.pos)
        pyautogui.press(tecla)
        for _ in range(6):
            time.sleep(0.2)
            odo.atualiza()
        andou = (odo.pos[0] - antes[0], odo.pos[1] - antes[1])
        distancia = abs(andou[0]) + abs(andou[1])
        resultado[tecla] = distancia
        esperado = KITE_PASSOS[tecla]
        print(f"  {tecla:>6} (esperado {esperado}): andou {andou} "
              f"-> {'ANDA' if distancia >= 2 else 'nao andou'}")
        time.sleep(0.4)
        # volta para onde estava, para nao sair andando pela cave: a tecla de
        # volta e a do rumo oposto, calculada - assim vale para qualquer
        # diagonal que voce tenha configurado
        oposto = (-KITE_PASSOS[tecla][0], -KITE_PASSOS[tecla][1])
        volta = next((t for t, r in KITE_PASSOS.items() if r == oposto), None)
        if distancia >= 2 and volta:
            pyautogui.press(volta)
            time.sleep(0.6)

    setas = [t for t in ("up", "down", "left", "right") if resultado[t] >= 2]
    diagonais = [t for t, r in KITE_PASSOS.items()
                 if 0 not in r and resultado.get(t, 0) >= 2]
    print(chr(10) + f"setas que andam: {setas or 'nenhuma'}")
    print(f"diagonais que andam: {diagonais or 'nenhuma'}")
    if not diagonais:
        print("Nenhuma diagonal andou. Tres coisas a tentar, nessa ordem:")
        print("  1. ligar o NumLock e rodar isto de novo;")
        print("  2. nos controles do cliente, amarrar as diagonais a teclas "
              "suas (por exemplo q, e, z, c) e escrever essas teclas em "
              "KITE_DIAGONAIS_TECLAS, na ordem cima-esquerda, cima-direita, "
              "baixo-esquerda, baixo-direita;")
        print("  3. deixar KITE_DIAGONAIS desligado: com quatro lados o kite "
              "funciona, so perde um caso - bicho de um lado e outro em cima, "
              "onde nenhuma seta aumenta a distancia.")
    else:
        print(f"Pode ligar KITE_DIAGONAIS: {len(diagonais)} diagonal(is) "
              f"andando.")
    restore_windows()


def show_kite(segundos=20.0):
    """
    Diagnostico do kite: mostra o que o bot enxerga na tela do jogo.

    Imprime as criaturas achadas em SQM a partir do personagem, a distancia da
    mais perto e o passo que o kite daria - SEM apertar tecla nenhuma. Salva
    tambem um PNG com a grade desenhada, para conferir se GAME_VIEW e TILE_PX
    batem com o seu layout: o quadrado do meio tem de cair no personagem.
    """
    leitura, _teclado = setup_windows()
    if not leitura:
        return
    vx, vy, vw, vh = GAME_VIEW
    print(f"viewport {vw}x{vh} em ({vx},{vy}), quadrado de {TILE_PX}px "
          f"-> grade {vw // TILE_PX}x{vh // TILE_PX}")
    print(f"mantendo {KITE_DIST} SQM. Ctrl+Alt+S para sair." + chr(10))

    cx, cy, _, _ = client_rect(leitura)
    fim = time.time() + segundos
    salvo = False
    while time.time() < fim and not keyboard.is_pressed(KILL_KEY):
        img = grab((cx + vx, cy + vy, vw, vh))
        criaturas = detect_creatures(leitura, img=img)
        perto = longe_o_bastante(criaturas)
        passo = passo_de_kite(criaturas)
        print(f"  {len(criaturas)} criatura(s) {criaturas} | mais perto: "
              f"{perto} SQM | passo: {passo or '-'}          ",
              end=chr(13), flush=True)
        if criaturas and not salvo:
            desenho = img.copy()
            meio_col, meio_lin = (vw // TILE_PX) // 2, (vh // TILE_PX) // 2
            for i in range(vw // TILE_PX + 1):          # grade
                desenho[:, min(i * TILE_PX, vw - 1)] = (60, 60, 60)
            for j in range(vh // TILE_PX + 1):
                desenho[min(j * TILE_PX, vh - 1), :] = (60, 60, 60)
            for dx, dy in criaturas:                    # criaturas em vermelho
                x0 = (meio_col + dx) * TILE_PX
                y0 = (meio_lin + dy) * TILE_PX
                desenho[y0:y0 + TILE_PX, x0:x0 + 3] = (255, 0, 0)
                desenho[y0:y0 + 3, x0:x0 + TILE_PX] = (255, 0, 0)
            x0, y0 = meio_col * TILE_PX, meio_lin * TILE_PX   # personagem
            desenho[y0:y0 + TILE_PX, x0:x0 + 3] = (0, 255, 255)
            desenho[y0:y0 + 3, x0:x0 + TILE_PX] = (0, 255, 255)
            arquivo = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "kite_visto.png")
            mss.tools.to_png(np.ascontiguousarray(desenho).tobytes(),
                             (vw, vh), output=arquivo)
            print(chr(10) + f"[kite] grade desenhada em {arquivo}: o quadrado "
                  f"ciano tem de cair no personagem e os vermelhos nos bichos")
            salvo = True
        time.sleep(0.3)
    print()
    restore_windows()


def loot(leitura, teclado, estado, loot_cd, odo=None):
    """
    Vai ate o corpo do bicho que acabou de morrer e aperta a tecla de saque.

    O que se guarda, no momento da morte, e ONDE o bicho estava - o corpo nao
    tem barra de vida, entao depois de morto o bot nao tem como enxerga-lo. Dai
    e caminho: em stand o personagem ja esta colado e a tecla resolve; em kite
    ele esta a KITE_DIST de distancia e precisa chegar.

    Devolve True enquanto estiver cuidando do loot - e assim que o trajeto da
    rota fica esperando, em vez de sair andando e deixar o dinheiro no chao.
    """
    onde = estado.get("loot_onde")
    if not ENABLE_LOOT or onde is None:
        return False

    if time.time() - estado.get("loot_desde", 0) > LOOT_PRAZO:
        print(f"[loot] {LOOT_PRAZO:.0f}s tentando chegar no corpo em {onde}; "
              f"desisto e sigo a rota")
        estado["loot_onde"] = None
        return False

    # o corpo nao anda: o que muda e a posicao do personagem, e o offset dele
    # acompanha o odometro
    if odo is not None and "loot_pos" in estado:
        andou = (odo.pos[0] - estado["loot_pos"][0],
                 odo.pos[1] - estado["loot_pos"][1])
        onde = (onde[0] - andou[0] / MINIMAP_PX_SQM,
                onde[1] - andou[1] / MINIMAP_PX_SQM)
        estado["loot_onde"] = onde
        estado["loot_pos"] = tuple(odo.pos)

    distancia = max(abs(onde[0]), abs(onde[1]))
    if distancia > LOOT_DIST:
        # longe: anda ate o corpo. Clique no mapa, que desvia de parede, e um
        # por parada como no resto do projeto.
        if odo is not None and odo.parado < WALK_STOP_TICKS:
            return True
        if not loot_cd.ready():
            return True
        passo = (int(round(onde[0] * MINIMAP_PX_SQM)),
                 int(round(onde[1] * MINIMAP_PX_SQM)))
        if abs(passo[0]) + abs(passo[1]) == 0:
            estado["loot_onde"] = None
            return False
        click_minimap(leitura, passo)
        loot_cd.mark()
        print(f"[loot] corpo a {distancia:.0f} SQM: ando ate ele")
        return True

    if not loot_cd.ready():
        return True
    if not teclado.isActive:
        focus_window(teclado)
    pyautogui.press(LOOT_HOTKEY)
    loot_cd.mark()
    tentativas = estado.get("loot_tentativas", 0) + 1
    estado["loot_tentativas"] = tentativas
    print(f"[loot] {LOOT_HOTKEY} no corpo ({tentativas} de "
          f"{LOOT_TENTATIVAS})")
    if tentativas >= LOOT_TENTATIVAS:
        estado["loot_onde"] = None
        estado["loot_tentativas"] = 0
        print("[loot] pronto, volto para a rota")
        return False
    return True


def marca_o_corpo(estado, onde, odo=None):
    """Guarda onde o bicho morreu, para o loot ir buscar."""
    if not ENABLE_LOOT or onde is None:
        return
    estado["loot_onde"] = (float(onde[0]), float(onde[1]))
    estado["loot_desde"] = time.time()
    estado["loot_tentativas"] = 0
    estado["loot_pos"] = tuple(odo.pos) if odo is not None else (0, 0)
    print(f"[loot] o bicho morreu em {onde}: vou pegar o loot")


def parar_de_andar(leitura, teclado=None):
    """
    Cancela o trajeto em andamento, por TECLA.

    Sem isso o personagem segue ate o destino ja clicado mesmo com bicho na tela,
    puxando mais monstro pelo caminho.

    Era um clique no proprio quadrado do personagem (centro do minimapa), e isso
    nao serve com zoom out: la um pixel vale 2 SQM, o quadrado do personagem nem
    chega a ocupar um pixel, e o clique que deveria dizer "fique onde esta" cai
    a varios SQM de distancia - manda ele ANDAR em vez de parar. Por isso agora
    e tecla: STOP_WALK_KEY, que no cliente e a parada de todas as acoes.

    Com STOP_WALK_KEY vazio, nao se manda nada: o personagem termina o trecho
    que ja estava andando e o bot apenas para de clicar.
    """
    if not STOP_WALK_KEY:
        return False
    if teclado is not None and not teclado.isActive:
        focus_window(teclado)
    pyautogui.press(STOP_WALK_KEY)
    return True


def limita_passo(falta, alcance=None):
    """
    Corta o vetor para caber no minimapa, mantendo a direcao.

    Um clique so alcanca o que esta visivel no minimapa; para alvo distante o
    bot clica o mais longe que da naquele rumo e reclica ao chegar mais perto.
    """
    alcance = alcance or WALK_MAX_LEG
    maior = max(abs(falta[0]), abs(falta[1]))
    if maior <= alcance:
        return (int(falta[0]), int(falta[1]))
    escala = alcance / maior
    return (int(round(falta[0] * escala)), int(round(falta[1] * escala)))


def passo_de_seta(falta):
    """Um passo de teclado no eixo que falta mais. Devolve a tecla usada."""
    dx, dy = falta
    if abs(dx) >= abs(dy):
        tecla = "right" if dx > 0 else "left"
    else:
        tecla = "down" if dy > 0 else "up"
    pyautogui.press(tecla)
    return tecla


def follow_waypoints(leitura, odo, estado, click_cd, teclado=None, key_cd=None):
    """
    Segue uma rota gravada de posicoes absolutas, em ciclo.

    Ritmo de um trecho: clica UMA vez rumo ao waypoint, espera o personagem
    PARAR e so entao confere a posicao. Chegou dentro da tolerancia, ancora e
    passa ao proximo; parou antes, clica de novo com o que falta recalculado.

    Modo alternativo ao follow_marks, para quem preferir rota gravada em vez das
    marcas do mapa.
    """
    pontos = estado.get("pontos") or []
    if not pontos:
        return False

    i = estado.get("indice", 0) % len(pontos)
    alvo = pontos[i]
    falta = odo.falta(alvo)
    dist = abs(falta[0]) + abs(falta[1])

    if dist <= WALK_TOLERANCE:
        odo.ancora(alvo)
        estado["indice"] = i + 1
        estado["cliques"] = estado["passos"] = 0
        estado.pop("dist_clique", None)
        print(f"[walk] waypoint {i} alcancado {tuple(alvo)}")
        return True

    if odo.parado < WALK_STOP_TICKS:
        return True

    if (ENABLE_WALK_KEYS and teclado is not None and key_cd is not None
            and dist <= WALK_KEYS_MAX):
        passos = estado.get("passos", 0)
        if passos >= WALK_MAX_KEYS:
            print(f"[walk] waypoint {i}: nao encostei ({dist}px faltando depois "
                  f"de {passos} passos de seta); sigo sem ancorar")
            estado["indice"] = i + 1
            estado["cliques"] = estado["passos"] = 0
            estado.pop("dist_clique", None)
            return True
        if key_cd.ready():
            tecla = passo_de_seta(falta)
            key_cd.mark()
            estado["passos"] = passos + 1
            print(f"[walk] waypoint {i}: ajuste fino de seta ({tecla}), "
                  f"faltam {falta}")
        return True

    if not click_cd.ready():
        return True

    anterior = estado.get("dist_clique")
    if anterior is not None and dist + WALK_TOLERANCE < anterior:
        estado["cliques"] = 0

    cliques = estado.get("cliques", 0)
    if cliques >= WALK_MAX_CLICKS:
        print(f"[walk] waypoint {i} sem progresso em {cliques} cliques "
              f"(faltavam {falta}), pulando para o proximo")
        estado["indice"] = i + 1
        estado["cliques"] = 0
        estado.pop("dist_clique", None)
        return True

    passo = limita_passo(falta)
    click_minimap(leitura, passo)
    click_cd.mark()
    estado["cliques"] = cliques + 1
    estado["dist_clique"] = dist
    print(f"[walk] waypoint {i}: faltam {falta} ({dist // MINIMAP_PX_SQM} SQM), "
          f"clique {cliques + 1} em {passo}")
    return True


# ---------------------------------------------------------------------- MODOS
def show_bars():
    """Modo leitura: imprime HP/mana sem enviar nenhuma tecla."""
    leitura, _ = setup_windows()
    if not leitura:
        return

    cx, cy, cw, ch = client_rect(leitura)
    print(f"Lendo de '{leitura.title}': cliente {cw}x{ch} na tela ({cx},{cy})")
    regioes = ensure_bars(leitura, force=True)
    if regioes is None:
        return
    hp_region, mana_region = regioes
    print(f"hp   {hp_region} -> tela {to_screen(leitura, hp_region)}")
    print(f"mana {mana_region} -> tela {to_screen(leitura, mana_region)}")
    print("Leve dano/gaste mana e veja se os valores acompanham. Ctrl+Alt+S para sair.\n")

    while not keyboard.is_pressed(KILL_KEY):
        hp, mana = read_bars(leitura)
        print(f"  hp={formata(hp, HP_MAX):>17s}   mana={formata(mana, MANA_MAX):>15s}",
              end="\r", flush=True)
        time.sleep(0.3)
    print("\nEncerrado.")


def show_battle():
    """Modo diagnostico: mostra o que o bot ve na Battle List, sem digitar nada."""
    leitura, _ = setup_windows()
    if not leitura:
        return

    print(f"Lendo a Battle List de '{leitura.title}'. Ctrl+Alt+S para sair.")
    while not keyboard.is_pressed(KILL_KEY):
        entradas, atacando, alvo_hp, _, _ = battle_state(leitura)
        if entradas == 0:
            acao = "lista vazia, nao ataca"
        elif atacando:
            acao = f"alvo engajado ({alvo_hp:.0%} de vida), conjura {SPELL_HOTKEY}"
        else:
            acao = f"apertaria {ATTACK_HOTKEY}"
        print(f"  entradas={entradas}  alvo_vermelho={atacando}  -> {acao}       ",
              end=chr(13), flush=True)
        time.sleep(0.3)
    print()


def record_waypoints():
    """
    Grava a rota enquanto VOCE anda.

    Modo "clique" (padrao): cada waypoint e a posicao de onde voce clicou o ponto
    SEGUINTE - ou seja, onde voce realmente chegou. Assim a gravacao aguenta o
    caminho ser interrompido: clique, pare para matar bicho, termine a pe de
    teclado e clique o proximo ponto. O ultimo waypoint e onde voce encerrar.

    Modo "distancia": waypoint automatico a cada WALK_RECORD_STEP px andados.
    Serve para quem anda de teclado.

    Em qualquer modo a posicao e absoluta, contada a partir de onde a gravacao
    comecou - comece no mesmo ponto onde o bot vai comecar a rodar. A gravacao
    PAUSA se o jogo perder o foco, porque sem foco a tela nao mostra o jogo e a
    leitura viraria lixo. Ctrl+Alt+S encerra e salva.
    """
    leitura, teclado = setup_windows()
    if not leitura:
        return

    if RECORD_MODE == "clique":
        print(f"Gravando em {WAYPOINTS_FILE} pelos seus CLIQUES no minimapa. "
              f"Ande a rota clicando no mapa; cada clique vira um waypoint.")
    else:
        print(f"Gravando em {WAYPOINTS_FILE} por distancia: cada "
              f"{WALK_RECORD_STEP}px ({WALK_RECORD_STEP // MINIMAP_PX_SQM} SQM) "
              f"andados fecham um waypoint.")
    print("Ctrl+Alt+S para encerrar e salvar.")

    odo = Odometro(leitura)
    pontos, ultimo, andado = [], [0, 0], 0
    pausado, pendente, pos_parado = False, None, [0, 0]
    proxima_leitura = 0.0

    while not keyboard.is_pressed(KILL_KEY):
        time.sleep(0.05)                 # rapido, para nao perder clique

        if not teclado.isActive:
            if not pausado:
                print(f"\n[record] pausado: o jogo perdeu o foco. "
                      f"Nada e gravado ate voltar.")
                pausado = True
            pendente = None
            continue
        if pausado:
            odo.resync()
            print("[record] foco de volta, retomando a gravacao")
            pausado = False

        # 1) seus cliques no minimapa.
        #
        #    O waypoint gravado NAO e o destino calculado do clique nem a
        #    primeira parada depois dele: e a posicao de onde voce clica o ponto
        #    SEGUINTE. Isso e o que sobrevive ao seu jeito de gravar - clicar,
        #    parar para matar bicho, terminar o caminho de teclado e so entao
        #    clicar o proximo ponto. A primeira parada seria onde a briga
        #    aconteceu, e o destino calculado erra quando o trajeto e
        #    interrompido.
        if RECORD_MODE == "clique":
            _, clique = clique_no_minimapa(leitura)
            if clique:
                if pendente is None:
                    print(f"\n[waypoints] primeiro clique {clique} anotado; o "
                          f"ponto sera gravado quando voce clicar o proximo")
                else:
                    alvo = tuple(pos_parado)
                    perto = (pontos and abs(alvo[0] - pontos[-1][0])
                             + abs(alvo[1] - pontos[-1][1]) <= WALK_TOLERANCE)
                    if perto:
                        print(f"\n[waypoints] {alvo} ignorado: colado no anterior")
                    else:
                        pontos.append(alvo)
                        print(f"\n[waypoints] {len(pontos) - 1}: {alvo}  "
                              f"(onde voce estava ao clicar o ponto seguinte)")
                pendente = clique

        # 2) odometro: posicao atual e a ultima posicao com o boneco PARADO
        agora = time.time()
        if agora < proxima_leitura:
            continue
        proxima_leitura = agora + 0.3

        dx, dy = odo.atualiza()
        andado += abs(dx) + abs(dy)
        if odo.parado >= WALK_STOP_TICKS:
            pos_parado = list(odo.pos)   # a leitura estavel, sem meio-passo
        dist = abs(odo.pos[0] - ultimo[0]) + abs(odo.pos[1] - ultimo[1])
        print(f"  posicao={tuple(odo.pos)}  parado_em={tuple(pos_parado)}  "
              f"waypoints={len(pontos)}  andado={andado:3d}px   ",
              end=chr(13), flush=True)

        if (RECORD_MODE != "clique" and andado >= WALK_RECORD_STEP
                and dist >= WALK_RECORD_MIN_DIST):
            pontos.append(tuple(odo.pos))
            ultimo, andado = list(odo.pos), 0
            print(f"\n[waypoints] {len(pontos) - 1}: {tuple(odo.pos)}")

    if RECORD_MODE == "clique":
        # o ultimo clique fecha aqui: a posicao onde voce encerrou a gravacao
        if pendente is not None:
            alvo = tuple(pos_parado)
            perto = (pontos and abs(alvo[0] - pontos[-1][0])
                     + abs(alvo[1] - pontos[-1][1]) <= WALK_TOLERANCE)
            if not perto:
                pontos.append(alvo)
                print(f"[waypoints] {len(pontos) - 1}: {alvo}  "
                      f"(ultimo ponto, onde voce encerrou)")
    else:
        resto = abs(odo.pos[0] - ultimo[0]) + abs(odo.pos[1] - ultimo[1])
        if resto >= WALK_RECORD_MIN_DIST:
            pontos.append(tuple(odo.pos))
    print()
    if pontos:
        save_waypoints(pontos)
    else:
        print("[waypoints] nada gravado.")


def calibrate():
    """Mostra posicao do mouse (absoluta e relativa ao cliente) e cor do pixel."""
    win, _ = setup_windows()
    if not win:
        return

    cx, cy, cw, ch = client_rect(win)
    print(f"Referencia: '{win.title}' cliente {cw}x{ch} na tela ({cx},{cy})")
    print("Passe o mouse sobre as barras. Ctrl+Alt+S para sair.\n")

    while not keyboard.is_pressed(KILL_KEY):
        x, y = pyautogui.position()
        color = grab((x, y, 1, 1))[0, 0]
        print(
            f"tela=({x:5d},{y:5d})  cliente=({x - cx:5d},{y - cy:5d})  "
            f"rgb={tuple(int(c) for c in color)}",
            end="\r",
        )
        time.sleep(0.2)
    print("\nCalibracao encerrada.")


def run_bot():
    """Loop principal do bot."""
    atualiza_passos()          # a configuracao manda nas teclas
    leitura, teclado = setup_windows()
    if not leitura:
        return

    if ensure_bars(leitura) is None:
        print("Abortando: sem as barras o bot leria lixo e spammaria cura.")
        return

    print(f"Bot iniciado: lendo de '{leitura.title}', teclas em '{teclado.title}'.")
    print("Ctrl+Alt+S para parar.")
    if ATTACK_MODE == "stand":
        print(f"[luta] modo stand: paro com {STOP_WALK_KEY} e nao saio do lugar")
    elif ATTACK_MODE == "chase":
        print("[luta] modo chase: nao mando tecla de parada (ela cancelaria o "
              "follow); ponha o cliente em chase")
    elif ATTACK_MODE == "kite":
        print(f"[luta] modo kite: ando de seta para manter {KITE_DIST} SQM de "
              f"todo bicho na tela")
    else:
        print(f"[luta] modo {ATTACK_MODE!r} desconhecido; tratando como stand")
    heal_cd = Cooldown(HEAL_COOLDOWN)                 # sem variacao: cura na hora
    forte_cd = Cooldown(HEAL_COOLDOWN)                # a emergencia tem o seu
    mana_cd = Cooldown(MANA_COOLDOWN, 0.10)
    attack_cd = Cooldown(ATTACK_COOLDOWN, 0.15)
    spell_cd = Cooldown(SPELL_COOLDOWN, 0.15)
    sem_alvo = 0
    monstros = load_monsters()
    evitar_lugares = load_evitar() if ATTACK_MODE == "kite" else {}
    odo_kite = None                    # odometro proprio do kite: ele roda com
                                       # a rota desligada, onde nao ha odo
    estado_kite = {}                   # lados que se provaram parede, e quando
    if ATTACK_MODE == "kite":
        print(f"[kite] {len(evitar_lugares)} lugar(es) de nao pisar: "
              f"{', '.join(evitar_lugares) or 'nenhum ainda, ensine com --evitar'}")
    if ONLY_KNOWN_MONSTERS:
        print(f"[monstros] atacando so os {len(monstros)} sprites da lista: "
              f"{', '.join(monstros) or 'nenhum'}")
    rota_gravada = load_waypoints() if USE_ROUTE_ORDER else []
    caminho = {"pontos": load_waypoints(), "indice": 0, "tentativas": 0,
               "rota": rota_gravada}
    click_cd = Cooldown(WALK_CLICK_COOLDOWN, 0.30)
    kite_cd = Cooldown(KITE_COOLDOWN, 0.10)
    loot_cd = Cooldown(LOOT_COOLDOWN, 0.10)
    key_cd = Cooldown(WALK_KEY_COOLDOWN, 0.15)
    auto_cds = autocast_cooldowns()
    if auto_cds:
        print(f"[autocast] {len(auto_cds)} slot(s) ativos: "
              + ", ".join(f"{s['tecla']} a cada {s['intervalo']:.0f}s"
                          for s, _ in auto_cds))
    odo = Odometro(leitura) if ENABLE_WALK else None
    sem_foco = False
    parou_por_bicho = False
    assinatura_vista, sem_resposta, lista_inutil = None, 0, None
    trava = TravaDeAlvo()
    limpo = 0
    espera_magia = 0.0
    curas_sem_efeito, hp_da_ultima_cura = 0, None
    avisou_impasse = False
    if ENABLE_WALK and rota_gravada:
        print(f"[walk] seguindo a ORDEM gravada: {len(rota_gravada)} pontos de "
              f"{WAYPOINTS_FILE}")
    elif ENABLE_WALK and USE_MAP_MARKS:
        print(f"[walk] seguindo as marcas '{MARK_COLOR}' do mapa, sem rota gravada")
    elif ENABLE_WALK:
        print(f"[walk] {len(caminho['pontos'])} waypoints carregados de "
              f"{WAYPOINTS_FILE}")

    seguidos = 0                       # erros em sequencia
    while True:
        # UMA LEITURA RUIM NAO PODE MATAR A CACADA. Um KeyError numa
        # leitura derrubou o bot no meio de uma cave, e o personagem fica
        # la sendo comido. Erro isolado entra no log e a volta seguinte
        # tenta de novo; erros em sequencia significam que algo mudou de
        # verdade (janela fechada, layout diferente) e ai se para.
        try:
            if STOP:
                print("[stop] parada solicitada por codigo.")
                break
            if keyboard.is_pressed(KILL_KEY):
                print("\n[stop] Ctrl+Alt+S pressionado.")
                break

            # as janelas podem ser fechadas/minimizadas no meio do caminho
            if not is_usable(teclado) or not is_usable(leitura):
                print("[warn] janela minimizada ou fechada, aguardando...")
                time.sleep(1.0)
                leitura_nova = find_projector() if OBS_MODE else find_tibia()
                teclado_nova = find_tibia()
                if leitura_nova and teclado_nova:
                    leitura, teclado = leitura_nova, teclado_nova
                continue

            # nunca enviar teclas se o jogo nao estiver em foco
            if not teclado.isActive:
                sem_foco = True
                time.sleep(0.5)
                continue
            if sem_foco:
                if odo:
                    odo.resync()      # nao inventar deslocamento durante a pausa
                print("[bot] foco de volta")
                sem_foco = False

            hp, mana = read_bars(leitura)

            # leitura zerada = personagem morto ou janela coberta: nao vale agir
            if hp <= 0.005:
                print(f"[warn] hp lido em {hp:.1%}: morto ou janela coberta, pausando.")
                time.sleep(1.0)
                continue

            # 1) prioridade: se curou nesta iteracao, nao faz mais nada
                # CURAR NAO DESCARTA A LEITURA. Antes havia um "continue" aqui, e
            # comecando com a vida abaixo do limite o bot passava a leitura toda
            # curando: medido, 7 curas e so 3 ataques em 40 leituras. Cura e
            # ataque sao teclas diferentes e nao brigam - a cura sai primeiro,
            # que e a prioridade, e o resto da leitura continua.
            agiu = auto_heal(hp, mana, heal_cd, mana_cd, forte_cd)
            if agiu:
                # cura que nao levanta a vida e sinal de pocao acabada, hotkey
                # errada ou dano maior que a cura - vale avisar em vez de martelar
                if hp_da_ultima_cura is not None and hp <= hp_da_ultima_cura:
                    curas_sem_efeito += 1
                    if curas_sem_efeito == HEAL_WARN_AFTER:
                        print(f"[warn] {HEAL_WARN_AFTER} curas seguidas e a vida nao "
                              f"subiu (parada em {formata(hp, HP_MAX)}): acabou a "
                              f"pocao, a hotkey esta errada ou o dano e maior que a "
                              f"cura")
                else:
                    curas_sem_efeito = 0
                hp_da_ultima_cura = hp
                # sem "continue": a cura ja saiu, e a mesma leitura ainda serve
                # para atacar, conjurar e andar

            # 2) autocast: teclas de intervalo fixo, depois da cura
            run_autocast(auto_cds, mana)

            # 3) combo: engaja quem estiver sem alvo, e conjura no alvo engajado
            entradas, alvo, alvo_hp, sprites, alvo_sprite = battle_state(leitura)
            monstros, aprendido = auto_learn(alvo_sprite, monstros)

            # filtro ligado com a lista vazia + auto-aprendizado seria um impasse:
            # nao ataca porque nao conhece, e nao conhece porque nunca ataca. Nesse
            # caso o filtro fica suspenso ate o primeiro sprite entrar na lista.
            prontos = sum(1 for sp in monstros.values() if sp is not None)
            filtrar = ONLY_KNOWN_MONSTERS and not (AUTO_LEARN and prontos == 0)
            if ONLY_KNOWN_MONSTERS and not filtrar and not avisou_impasse:
                print("[monstros] filtro ligado sem nenhum sprite: ataco livremente "
                      "ate aprender o primeiro, senao nunca aprenderia")
                avisou_impasse = True
            atacaveis = monstros_atacaveis(sprites, monstros, filtrar)
            sem_alvo = 0 if alvo else sem_alvo + 1

            # so troca de alvo quando o bicho engajado sumir da battle list
            pode_trocar = trava.atualiza(alvo, alvo_sprite, sprites)

            # ONDE O BICHO ESTA, enquanto vivo: o corpo nao tem barra de vida,
            # entao depois de morto nao ha como enxerga-lo. Guardar a posicao do
            # mais perto a cada leitura e o que permite ir buscar o loot depois.
            if ENABLE_LOOT and entradas > 0:
                na_tela = detect_creatures(leitura)
                if na_tela:
                    caminho["bicho_visto"] = min(
                        na_tela, key=lambda c: max(abs(c[0]), abs(c[1])))
            if ENABLE_LOOT and trava.morreu:
                trava.morreu = False
                marca_o_corpo(caminho, caminho.get("bicho_visto"), odo)

            # a lista mudou? volta a valer a pena tentar atacar
            assinatura = battle_assinatura(sprites)
            if assinatura != assinatura_vista:
                assinatura_vista, sem_resposta = assinatura, 0
                lista_inutil = None
            if alvo:
                sem_resposta, lista_inutil = 0, None

            # lista que ja provou nao responder ao ataque (NPC, player) nao conta
            # como bicho para NADA: nem para apertar tecla, nem para segurar a rota.
            # Antes o freio calava a tecla mas o trajeto seguia cancelado, e um NPC
            # parado perto travava o cave inteiro.
            if lista_inutil == assinatura:
                atacaveis = 0

            # Cancelar o trajeto vem ANTES de atacar: a tecla de parada do cliente
            # solta tambem o alvo, entao mandada depois ela mataria o ataque que
            # acabou de sair - o bot apertava, perdia o alvo e so reengajava depois
            # de ATTACK_CONFIRM leituras.
            if ENABLE_WALK and (atacaveis or alvo) and not parou_por_bicho:
                # a tecla de parada e do modo STAND. Em chase ela cancelaria o
                # follow do cliente junto com o ataque, e em kite quem manda no
                # movimento sao as setas.
                parou = (parar_de_andar(leitura, teclado)
                         if ATTACK_MODE == "stand" else False)
                caminho["cliques"] = 0
                parou_por_bicho = True
                print(f"[walk] {atacaveis} atacavel(is) na lista: "
                      + (f"trajeto cancelado com {STOP_WALK_KEY}, lutando primeiro"
                         if parou else
                         f"paro de clicar, lutando em modo {ATTACK_MODE}"))
                if parou:
                    # o ataque so depois que a parada foi processada: as duas teclas
                    # sairiam com milissegundos de diferenca e o cliente poderia
                    # tratar a parada DEPOIS do ataque - soltando o alvo que acabou
                    # de ser pego. Este respiro custa um quarto de segundo, uma vez
                    # por briga.
                    time.sleep(STOP_ATTACK_DELAY)

            apertou = attack_monster(teclado, atacaveis, alvo, attack_cd,
                                     confirmado=sem_alvo >= ATTACK_CONFIRM,
                                     sprites=sprites, monstros=monstros,
                                     permitido=(lista_inutil != assinatura
                                                and pode_trocar))
            if apertou:
                espera_magia = time.time() + SPELL_DELAY_AFTER_ATTACK
                sem_resposta += 1
                if sem_resposta >= ATTACK_GIVEUP:
                    lista_inutil = assinatura
                    print(f"[attack] {atacaveis} entrada(s) nao engajaram em "
                          f"{sem_resposta} tentativas: NPC ou player? Paro de apertar "
                          f"{ATTACK_HOTKEY} ate a lista mudar.")
            cast_spell(alvo, mana, spell_cd, espera_magia)

            # LUTANDO: qualquer entrada na battle list segura o trajeto, nao so a
            # que conta como atacavel - bicho ainda nao aprendido, ou com o sprite
            # escurecido por estar quase morto, tambem e bicho vivo do lado do
            # personagem. A excecao e a lista que ja provou nao responder ao ataque
            # (NPC, player): essa nao morre nunca e travaria o cave.
            so_inuteis = lista_inutil == assinatura
            lutando = ((entradas > 0 and not so_inuteis)
                       or bool(alvo) or not pode_trocar)

            # 4) kite: e comportamento de COMBATE, nao de rota - roda mesmo com o
            # andar desligado. Ficava dentro do bloco da rota e nao acontecia nada
            # para quem so quer o bot lutando.
            if lutando and ATTACK_MODE == "kite":
                # bicho na lista mas fora da tela: a tela alcanca 7 SQM de lado e 5
                # de altura, e o que corre alem disso o bot nao ve. Sem este aviso
                # nao ha como saber, num log, se ele "nao perseguiu" por isso ou por
                # decisao errada.
                if entradas > 0 and not detect_creatures(leitura):
                    sem_ver = estado_kite.get("sem_ver", 0) + 1
                    estado_kite["sem_ver"] = sem_ver
                    if sem_ver == KITE_AVISA_SEM_VER:
                        print(f"[kite] {entradas} na battle list e nenhum bicho na "
                              f"tela: correu para fora do alcance da tela "
                              f"(7 SQM de lado, 5 de altura)")
                else:
                    estado_kite["sem_ver"] = 0
                if odo_kite is None:
                    odo_kite = Odometro(leitura)
                odo_kite.atualiza()
                if odo_kite.mudou_de_andar():
                    aprendido = aprende_o_que_derrubou(estado_kite, evitar_lugares)
                    print("[kite] O MINIMAPA TROCOU POR INTEIRO: mudei de andar "
                          "(escada, buraco ou portal)."
                          + (f" Guardei o quadrado como '{aprendido}': nao piso "
                             f"nele de novo." if aprendido else ""))
                    if PARAR_SE_MUDAR_ANDAR:
                        print("      Parando o bot - dai em diante quem decide "
                              "e voce.")
                        break
                    odo_kite = None            # o andar novo tem outra textura
                kite(leitura, teclado, kite_cd, evitar_lugares,
                     odo=odo_kite, estado=estado_kite)

            # 5) segue o cave. A posicao e integrada SEMPRE, inclusive durante a
            # briga: e isso que faz o reclique depois da luta cair no lugar certo.
            if ENABLE_WALK:
                odo.atualiza()
                # LUTANDO NAO SE ANDA, e a razao nao e so nao puxar monstro: no
                # cliente, tecla de direcao ou clique no mapa durante o ataque troca
                # o modo de luta de "chase" para "stand".
                if USE_MAP_MARKS:
                    # acompanha as marcas SEMPRE, inclusive lutando: se o rastreio
                    # para durante a briga, ao voltar o bot nao sabe mais de onde
                    # veio e a regra de ouro manda ele para tras. Lutando, porem, o
                    # que o bicho empurra nao conta como visita.
                    track_marks(leitura, caminho, andando=not lutando,
                                odo=odo)
                # O trajeto so volta depois de a lista ficar limpa por VARIAS
                # leituras seguidas. Uma leitura ruim no meio da briga nao pode
                # virar clique no mapa: no cliente, clique no mapa durante o ataque
                # troca o modo de luta de "chase" para "stand". Perder meio segundo
                # aqui e barato; trocar o modo do personagem, nao.
                limpo = 0 if lutando else limpo + 1
                if not lutando and limpo >= WALK_RESUME_READS:
                    if parou_por_bicho:
                        print(f"[walk] battle list limpa por {limpo} leituras, "
                              f"retomando o trajeto")
                        parou_por_bicho = False
                        caminho["cliques"] = 0
                    # LOOT ANTES DA ROTA: sair andando com o corpo no chao e
                    # deixar o profit para tras. Fica DENTRO desta carencia
                    # porque o loot tambem anda de clique no mapa, e clique no
                    # meio da briga troca chase/stand - o teste pegou o bot
                    # clicando numa leitura ruim que a trava leu como morte.
                    if loot(leitura, teclado, caminho, loot_cd, odo):
                        time.sleep(LOOP_DELAY)
                        continue
                    if rota_gravada:
                        follow_route(leitura, odo, caminho, click_cd)
                    elif USE_MAP_MARKS:
                        follow_marks(leitura, odo, caminho, click_cd)
                    else:
                        follow_waypoints(leitura, odo, caminho, click_cd,
                                         teclado, key_cd)
                # o cancelamento do trajeto ja aconteceu la em cima, antes do
                # ataque: a tecla de parada solta o alvo junto e nao pode vir depois

            time.sleep(LOOP_DELAY)
        except Exception as erro:
            seguidos += 1
            print(f'[erro] {type(erro).__name__}: {erro} (leitura {seguidos} de {ERROS_SEGUIDOS_MAX})')
            traceback.print_exc()
            if seguidos >= ERROS_SEGUIDOS_MAX:
                print('[stop] erros seguidos demais; parando para nao ficar chutando.')
                break
            time.sleep(LOOP_DELAY)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cave bot base para Tibia.")
    parser.add_argument("--bars", action="store_true",
                        help="So le e imprime HP/mana, sem pressionar teclas.")
    parser.add_argument("--calib", action="store_true",
                        help="Modo calibracao: coordenadas e cor do pixel sob o mouse.")
    parser.add_argument("--record", action="store_true",
                        help="Grava waypoints enquanto voce anda a rota.")
    parser.add_argument("--marcas", action="store_true",
                        help="Grava a ORDEM das marcas do mapa (pise em cada uma).")
    parser.add_argument("--zoom", action="store_true",
                        help="Mede a escala do minimapa (px por SQM) no zoom atual.")
    parser.add_argument("--battle", action="store_true",
                        help="Diagnostico da Battle List: entradas e alvo atual.")
    parser.add_argument("--kite", action="store_true",
                        help="Diagnostico do kite: criaturas na tela em SQM.")
    parser.add_argument("--teclas", action="store_true",
                        help="Mede quais teclas de movimento andam no cliente.")
    parser.add_argument("--evitar", action="store_true",
                        help="Ensina por clique os quadrados de nao pisar.")
    parser.add_argument("--obs", action="store_true",
                        help="Ler do projetor do OBS em vez da janela do Tibia.")
    args = parser.parse_args()

    OBS_MODE = OBS_MODE or args.obs

    try:
        if args.bars:
            show_bars()
        elif args.battle:
            show_battle()
        elif args.kite:
            show_kite()
        elif args.teclas:
            show_teclas()
        elif args.evitar:
            record_evitar()
        elif args.record:
            record_waypoints()
        elif args.marcas:
            record_marks()
        elif args.zoom:
            medir_escala()
        elif args.calib:
            calibrate()
        else:
            run_bot()
    except KeyboardInterrupt:
        print("\nEncerrado pelo usuario.")
    finally:
        # nao deixar o jogo/projetor presos como "sempre visivel" nem opacos
        restore_windows()
