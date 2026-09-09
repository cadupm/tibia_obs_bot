# -*- coding: utf-8 -*-
"""Quatro bichos, TRES marcados para saque e um nao: os tres corpos sao pegos.

Relatado em cacada: "quando aparece uns 3 pra lootear e um sem, ele so ta indo
no ultimo". Duas coisas causavam isso, e as duas eram sobre a HISTORIA de
leituras (bichos_vistos), que e a referencia da comparacao de imagem:

  1. rejeitar um bicho pelo filtro APAGAVA a historia. Ela e compartilhada por
     todos os bichos, nao e de um: apagar deixava as mortes seguintes sem
     referencia;
  2. `if historico:` governava o bloco inteiro, inclusive o registro de barras
     que sumiram - que nao depende dela. Historia vazia, nenhum corpo marcado,
     mesmo com o quadrado exato da morte anotado.

O registro de barras passa a valer sozinho, e o filtro descarta apenas o ponto
de morte DAQUELE bicho.

O que se mede aqui:
  - cada uma das quatro mortes e registrada, em quadrados diferentes;
  - os tres marcados viram corpo na fila; o desmarcado nao;
  - os tres sao clicados, em tres pontos distintos da tela;
  - a ordem das mortes nao importa: o desmarcado morre no MEIO, que e o caso
    que apagava a referencia dos que vinham depois.
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
CHAO = np.random.default_rng(53).integers(40, 70, (VH, VW, 3), dtype=np.uint8)


def sprite(semente):
    """Ruido proprio por bicho: sprites parecidos demais contam como o MESMO
    bicho para o bot, e com razao - ja custou um teste que nao media nada."""
    return np.random.default_rng(semente).integers(
        0, 255, (17, 20, 3), dtype=np.uint8)


# quatro bichos em quatro quadrados; o TERCEIRO a morrer e o desmarcado
NOMES = ["quero A", "quero B", "NAO quero", "quero C"]
ONDE = [(1, 0), (0, 1), (-1, 0), (1, 1)]
SPRITES = [sprite(10 + i) for i in range(4)]
MONSTROS = dict(zip(NOMES, SPRITES))
MARCAS = {n: (n != "NAO quero") for n in NOMES}
for i in range(4):
    for j in range(i + 1, 4):
        assert not main.sprite_igual(SPRITES[i], SPRITES[j]), \
            "os sprites do teste tem de ser distinguiveis"


def desenha(img, off, cor, tamanho=44):
    x0 = (MEIO_COL + off[0]) * main.TILE_PX + (main.TILE_PX - tamanho) // 2
    y0 = (MEIO_LIN + off[1]) * main.TILE_PX + (main.TILE_PX - tamanho) // 2
    img[y0:y0 + tamanho, x0:x0 + tamanho] = cor
    return img


def barra(img, off):
    x = (MEIO_COL + off[0]) * main.TILE_PX + 18
    y = (MEIO_LIN + off[1] - main.CREATURE_BAR_ABOVE) * main.TILE_PX + 10
    img[y:y + 4, x:x + 31] = (0, 0, 0)
    img[y + 1:y + 3, x + 1:x + 30] = (0, 95, 0)
    return img


def tela(vivos):
    """Vivos de pe com barra; mortos como cadaver, SEM barra e SEM nome."""
    img = CHAO.copy()
    for i, off in enumerate(ONDE):
        if i in vivos:
            desenha(img, off, (170, 40, 40))
            barra(img, off)
        else:
            desenha(img, off, (95, 75, 55))
    return img


class Janela:
    isActive = True
    title = "falso"
    isMinimized = False


class OdoFalso:
    todos = []

    def __init__(self, _win=None):
        self.pos = [0, 0]
        self.parado = 9
        OdoFalso.todos.append(self)

    def atualiza(self):
        pass

    def resync(self):
        pass

    def ancora(self, alvo):
        pass

    def mudou_de_andar(self):
        return False


# roteiro: os quatro na lista, e morrem um a um na ordem 0, 1, 2, 3
FASES = [{0, 1, 2, 3}, {1, 2, 3}, {2, 3}, {3}, set()]
POR_FASE = 7

fita, quadro = [], {"i": 0}
roteiro, telas = [], []
for vivos in FASES:
    engajado = bool(vivos)
    presentes = [SPRITES[i] for i in sorted(vivos)]
    for _ in range(POR_FASE if vivos else 40):
        roteiro.append((len(presentes), engajado,
                        0.9 if engajado and presentes else None,
                        presentes, presentes[0] if engajado and presentes
                        else None))
        telas.append(tela(vivos))


def agora():
    return min(quadro["i"], len(roteiro) - 1)


def loop_sleep(_s):
    quadro["i"] += 1
    if quadro["i"] >= len(roteiro):
        main.STOP = True


def clica_jogo(x, y, pausa=0.09, botao="esquerdo", mod=""):
    fita.append((agora(), "clique", botao, (x, y)))
    if botao == "esquerdo":                # o esquerdo ANDA ate o quadrado
        off = (round((x - _vx) / main.TILE_PX - 0.5 - MEIO_COL),
               round((y - _vy) / main.TILE_PX - 0.5 - MEIO_LIN))
        for odo in OdoFalso.todos:
            odo.pos[0] += off[0] * main.MINIMAP_PX_SQM
            odo.pos[1] += off[1] * main.MINIMAP_PX_SQM


main.setup_windows = lambda: (Janela(), Janela())
main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
main.read_bars = lambda win: (1.0, 1.0)
main.battle_state = lambda win: roteiro[agora()]
main.grab = lambda regiao: telas[agora()]
main.Odometro = OdoFalso
main.client_rect = lambda win: (0, 0, 1920, 1009)
main.detect_marks = lambda win, mm=None, cor=None: []
main.is_usable = lambda win: True
main.focus_window = lambda win: True
main.restore_windows = lambda: None
main.keyboard = type("K", (), {"is_pressed": staticmethod(lambda k: False)})()
main.pyautogui = type("P", (), {
    "press": staticmethod(lambda t: fita.append((agora(), "tecla", t, None))),
    "keyDown": staticmethod(lambda t: None),
    "keyUp": staticmethod(lambda t: None)})()
main.click_minimap = lambda w, p: fita.append((agora(), "mapa", p, None))
main.click_game = clica_jogo
main.time = type("T", (), {"time": staticmethod(lambda: quadro["i"] * 0.3),
                           "sleep": staticmethod(loop_sleep)})()
main.load_monsters = lambda caminho=None: dict(MONSTROS)
main.load_loot_flags = lambda caminho=None: dict(MARCAS)
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
main.LOOT_SO_MARCADOS = True
main.LOOT_SO_SE_ACHOU = False
main.ATTACK_CONFIRM = 2
main.STOP = False

saida = io.StringIO()
with redirect_stdout(saida):
    main.run_bot()
log = saida.getvalue()

falhas = []
if os.environ.get("VERBOSO"):
    for l in log.splitlines():
        if "[loot]" in l or "[attack]" in l:
            print("   " + l)

marcados = [l for l in log.splitlines() if "bicho morreu a" in l]
ignorados = [l for l in log.splitlines() if "nao esta marcado para saque" in l]
saques = [l for l in log.splitlines()
          if "Saqueado" in l or "saqueio na hora" in l]
cliques = [f for f in fita if f[1] == "clique" and f[2] == main.LOOT_BOTAO]
pontos = {f[3] for f in cliques}

print(f"quatro bichos em {ONDE}, o 3o a morrer e o desmarcado\n")
print(f"corpos marcados na fila: {len(marcados)}")
for l in marcados:
    print("   " + l.strip())
print(f"\nignorados pelo filtro: {len(ignorados)}")
for l in ignorados:
    print("   " + l.strip())
print(f"\ncorpos saqueados: {len(saques)}")
for l in saques:
    print("   " + l.strip())
print(f"\ncliques de saque: {len(cliques)} em {len(pontos)} ponto(s) distintos")

if len(marcados) < 3:
    falhas.append(f"marcou {len(marcados)} corpo(s) de 3 marcados: as mortes "
                  f"do meio estao sendo perdidas. Era o caso relatado - com "
                  f"tres para saquear e um sem, so o ultimo era pego")
if len(ignorados) != 1:
    falhas.append(f"{len(ignorados)} ignorado(s) pelo filtro, esperava 1")
if len(saques) < 3:
    falhas.append(f"saqueou {len(saques)} de 3")
if len(pontos) < 3:
    falhas.append(f"clicou em {len(pontos)} ponto(s) distintos: os tres corpos "
                  f"estao em quadrados diferentes, entao os cliques tambem "
                  f"tem de estar")

# o quadrado do DESMARCADO nao pode ter sido clicado
desmarcado = ONDE[NOMES.index("NAO quero")]
print(f"\nquadrado do desmarcado: {desmarcado}")
if any("saqueio na hora em" in l and str(desmarcado) in l
       for l in log.splitlines()):
    falhas.append(f"saqueou o corpo do desmarcado em {desmarcado}")

print("\nVEREDITO:", "OK - guarda todos os pontos de morte e pega os marcados"
      if not falhas else "FALHOU: " + "; ".join(falhas))
