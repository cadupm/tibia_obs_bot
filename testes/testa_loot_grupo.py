# -*- coding: utf-8 -*-
"""Tres bichos na battle list: gravar os TRES corpos, recolher depois de matar
todos.

Eles morrem COLADOS no personagem e lado a lado, que e o que acontece quando os
tres estavam batendo nele. Com bichos espacados o teste passava escondendo dois
bugs: a fusao de corpos "por perto" juntava vizinhos num corpo so, e a
referencia da comparacao de tela era apagada a cada morte, deixando a proxima
sem quadro antigo para comparar.

Numa caverna se mata em grupo, e a ordem certa e: lutar tudo, e so depois
saquear. Saquear entre uma morte e outra e ruim por tres razoes medidas neste
projeto - clique no mapa ou na tela durante o ataque troca o modo de luta de
chase para stand no cliente; parado em cima do corpo com bicho vivo em volta o
personagem apanha de graca; e corpo no Tibia dura minutos, entao nao ha pressa.

O que se mede aqui, no laco de verdade (run_bot):
  - cada morte grava UM corpo, e nao so a ultima;
  - corpo COLADO e saqueado na hora, mesmo com bicho na lista: clicar num corpo
    ao lado nao e ordem de movimento;
  - NAO se anda (clique de mapa) ate corpo enquanto ha bicho na briga;
  - todos os corpos sao saqueados, cada um com um clique no quadrado dele.
"""
import io
import os
import sys
from contextlib import redirect_stdout
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

_vx, _vy, VW, VH = main.GAME_VIEW
MEIO_COL, MEIO_LIN = (VW // main.TILE_PX) // 2, (VH // main.TILE_PX) // 2
CHAO = np.random.default_rng(5).integers(40, 70, (VH, VW, 3), dtype=np.uint8)

# GEOMETRIA REALISTA: os tres estavam batendo no personagem, entao morrem
# COLADOS nele e lado a lado. Era (2,0),(0,2),(-2,0) - espacados, o que escondia
# dois bugs: a fusao de corpos "por perto" (1 SQM inteiro de tolerancia) juntava
# vizinhos num corpo so, e o loot pegava apenas um.
ONDE = [(1, 0), (1, 1), (0, 1)]


def sprite(cor):
    s = np.full((17, 20, 3), 40, dtype=np.uint8)
    s[3:8, 3:8] = cor
    return s


SPRITES = [sprite((200, 30, 30)), sprite((30, 200, 30)), sprite((30, 30, 200))]


def bicho(img, off, cor):
    """Desenha dentro do quadrado, sem invadir o vizinho: com os bichos colados,
    sprite transbordando faria o quadrado do vizinho mudar tambem e o teste
    mediria a sobreposicao em vez da deteccao."""
    x0 = (MEIO_COL + off[0]) * main.TILE_PX + 12
    y0 = (MEIO_LIN + off[1]) * main.TILE_PX + 12
    img[y0:y0 + 44, x0:x0 + 44] = cor
    return img


def barra(img, off):
    x = (MEIO_COL + off[0]) * main.TILE_PX + 18
    y = (MEIO_LIN + off[1] - main.CREATURE_BAR_ABOVE) * main.TILE_PX + 10
    img[y:y + 4, x:x + 31] = (0, 0, 0)
    img[y + 1:y + 3, x + 1:x + 30] = (0, 95, 0)
    return img


def tela(vivos):
    """A tela com os `vivos` de pe e os mortos como corpo no mesmo quadrado."""
    img = CHAO.copy()
    for i, off in enumerate(ONDE):
        if i in vivos:
            bicho(img, off, (170, 40, 40))
            barra(img, off)
        else:
            bicho(img, off, (95, 75, 55))       # corpo: cor bem diferente
    return img


# roteiro: 3 na lista, morre um, morre outro, morre o ultimo, e cave vazia
VAZIA = (0, False, None, [], None)
ROTEIRO = []
for vivos, engajado in (({0, 1, 2}, False), ({0, 1, 2}, True),
                        ({1, 2}, True), ({2}, True), (set(), False)):
    quantos = 6 if vivos else 40
    for _ in range(quantos):
        presentes = [SPRITES[i] for i in sorted(vivos)]
        if not presentes:
            ROTEIRO.append((0, False, None, [], None))
        else:
            ROTEIRO.append((len(presentes), engajado, 0.9 if engajado else None,
                            presentes, presentes[0] if engajado else None))
VIVOS_POR_QUADRO = []
for vivos, _e in (({0, 1, 2}, 0), ({0, 1, 2}, 0), ({1, 2}, 0), ({2}, 0),
                  (set(), 0)):
    VIVOS_POR_QUADRO += [frozenset(vivos)] * (6 if vivos else 40)


class Janela:
    isActive = True
    title = "falso"
    isMinimized = False


class OdoFalso:
    """Anda quando o clique de mapa manda, como o cliente faria.

    Precisa andar: os corpos estao a 2 SQM e LOOT_DIST e 1. Com odometro
    parado, nenhum deles e alcancavel e o teste mediria o mundo de mentira em
    vez do bot - foi o que aconteceu na primeira versao deste arquivo.
    """

    unico = None

    def __init__(self, _win=None):
        self.pos = [0, 0]
        self.parado = 9
        OdoFalso.unico = self

    def atualiza(self):
        pass

    def resync(self):
        pass

    def ancora(self, alvo):
        pass

    def mudou_de_andar(self):
        return False


fita, quadro = [], {"i": 0}


def onde_estou():
    return min(quadro["i"], len(ROTEIRO) - 1)


def loop_sleep(_s):
    quadro["i"] += 1
    if quadro["i"] >= len(ROTEIRO):
        main.STOP = True


main.setup_windows = lambda: (Janela(), Janela())
main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
main.read_bars = lambda win: (1.0, 1.0)
main.battle_state = lambda win: ROTEIRO[onde_estou()]
main.grab = lambda regiao: tela(VIVOS_POR_QUADRO[onde_estou()])
main.Odometro = OdoFalso
main.client_rect = lambda win: (0, 0, 1920, 1009)
main.detect_marks = lambda win, mm=None, cor=None: []
main.is_usable = lambda win: True
main.focus_window = lambda win: True
main.restore_windows = lambda: None
main.keyboard = type("K", (), {"is_pressed": staticmethod(lambda k: False)})()
main.pyautogui = type("P", (), {
    "press": staticmethod(lambda t: fita.append((onde_estou(), "tecla", t))),
    "keyDown": staticmethod(lambda t: None),
    "keyUp": staticmethod(lambda t: None)})()
def clica_mapa(_w, passo):
    fita.append((onde_estou(), "mapa", passo))
    if OdoFalso.unico is not None:            # o personagem chega onde clicou
        OdoFalso.unico.pos[0] += passo[0]
        OdoFalso.unico.pos[1] += passo[1]


main.click_minimap = clica_mapa
main.click_game = lambda x, y, pausa=0.09, botao="esquerdo", mod="": \
    fita.append((onde_estou(), "clique", (x, y)))
main.time = type("T", (), {"time": staticmethod(lambda: quadro["i"] * 0.3),
                           "sleep": staticmethod(loop_sleep)})()
main.load_monsters = lambda caminho=None: {
    f"b{i}": sp for i, sp in enumerate(SPRITES)}
main.load_waypoints = lambda caminho=None: []
main.load_evitar = lambda caminho=None: {}
main.ONLY_KNOWN_MONSTERS = True
main.AUTO_LEARN = False
main.ENABLE_WALK = False
main.USE_MAP_MARKS = False
main.USE_ROUTE_ORDER = False
main.ATTACK_MODE = "stand"
main.ENABLE_HEAL = main.ENABLE_MANA = False
main.ENABLE_SPELL = main.ENABLE_AUTOCAST = False
main.ENABLE_PARALISIA = False
main.ENABLE_LOOT = True
main.ATTACK_CONFIRM = 2
main.STOP = False

saida = io.StringIO()
with redirect_stdout(saida):
    main.run_bot()
log = saida.getvalue()

falhas = []
if os.environ.get("VERBOSO"):
    for _l in log.splitlines():
        if "[attack]" in _l or "[loot]" in _l:
            print("   " + _l)
mortes = [l for l in log.splitlines() if "bicho morreu a" in l]
saques = [l for l in log.splitlines()
          if "Saqueado" in l or "saqueio na hora" in l]
cliques = [f for f in fita if f[1] == "clique"]

print(f"tres bichos na lista, morrendo um por um\n")
print(f"corpos gravados: {len(mortes)}")
for l in mortes:
    print("   " + l.strip())
print(f"\ncorpos saqueados: {len(saques)}")
for l in saques:
    print("   " + l.strip())

if len(mortes) < 3:
    falhas.append(f"gravou {len(mortes)} corpo(s) de 3 mortes: cada morte tem "
                  f"de virar um corpo na fila, senao o profit dos primeiros "
                  f"fica no chao")
if len(saques) < 3:
    falhas.append(f"saqueou {len(saques)} corpo(s) de 3")

# CLICAR NUM CORPO COLADO durante a briga E PERMITIDO: nao e ordem de
# movimento, e o que troca chase por stand no cliente e movimento (tecla de
# direcao, clique no mapa). O que NAO pode e ANDAR ate corpo durante a briga:
# isso e clique no mapa, e leva o personagem para dentro do que sobrou.
ultimo_com_bicho = max(i for i, v in enumerate(VIVOS_POR_QUADRO) if v)
na_briga = [c for c in cliques if c[0] <= ultimo_com_bicho]
andou_na_briga = [f for f in fita
                  if f[1] == "mapa" and f[0] <= ultimo_com_bicho]
print(f"\nultimo quadro com bicho vivo na lista: {ultimo_com_bicho}")
print(f"cliques em corpo COLADO durante a briga: {len(na_briga)} "
      f"(permitido: nao e movimento)")
print(f"cliques de MAPA durante a briga: {len(andou_na_briga)}")
if andou_na_briga:
    falhas.append(f"andou {len(andou_na_briga)}x ate corpo com bicho ainda na "
                  f"battle list: clique no mapa e ordem de movimento, troca "
                  f"chase por stand no cliente e leva para dentro do bicho")

# um clique por corpo. O PONTO na tela e sempre o do meio, e isso esta certo:
# ele ANDA ate o corpo, entao na hora de clicar o corpo esta debaixo do
# personagem. Quem prova que ele foi a tres lugares diferentes sao os cliques
# de MAPA, nao os cliques na tela.
print(f"cliques em corpo depois da briga: {len(cliques)}")
if len(cliques) != len(saques) * main.LOOT_CLIQUES:
    falhas.append(f"{len(cliques)} clique(s) para {len(saques)} corpo(s): "
                  f"esperava {main.LOOT_CLIQUES} por corpo")

# O QUE IMPORTA E TER AGIDO EM LUGARES DIFERENTES, e o caminho pode ser andar
# (corpo longe) ou clicar noutro ponto da tela (corpo colado). Exigir trajeto de
# mapa era errado nesta geometria: os tres estao dentro de LOOT_DIST e nao ha
# para onde andar.
andadas = [f[2] for f in fita if f[1] == "mapa"]
pontos = {c[2] for c in cliques}
lugares = len(set(andadas)) if andadas else len(pontos)
print(f"trajetos de mapa: {andadas or 'nenhum (todos ao alcance)'}")
print(f"pontos de clique distintos: {len(pontos)}")
if len(saques) >= 2 and lugares < 2:
    falhas.append(f"os corpos estao em quadrados diferentes e o bot agiu "
                  f"sempre no mesmo lugar (trajetos {andadas}, pontos "
                  f"{pontos})")

# e as posicoes gravadas tem de ser as tres, e nao a mesma tres vezes
gravadas = set()
for l in mortes:
    gravadas.add(l.split("morreu a ")[1].split(" SQM")[0])
print(f"posicoes gravadas: {sorted(gravadas)}")
if len(gravadas) < 3:
    falhas.append(f"gravou {len(gravadas)} posicao(oes) distinta(s) para 3 "
                  f"bichos em quadrados diferentes: {sorted(gravadas)}")

print("\nVEREDITO:", "OK - grava os corpos do grupo e recolhe depois da briga"
      if not falhas else "FALHOU: " + "; ".join(falhas))
