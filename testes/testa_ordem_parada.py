# -*- coding: utf-8 -*-
"""A ORDEM das acoes quando aparece bicho, medida no laco de verdade.

Duas garantias que o modo de luta do cliente exige:

  1. a tecla de PARAR sai antes da tecla de ATACAR - a parada solta o alvo, e
     mandada depois mataria o ataque recem-dado;
  2. NENHUM clique no mapa (nem tecla de direcao) enquanto ha bicho engajado -
     no cliente, clique no mapa ou seta durante o ataque troca o modo de luta de
     "chase" para "stand".

O laco roda de verdade; o que e de mentira e a tela: battle list, barras,
janelas e teclado sao substituidos, e cada acao emitida entra numa fita para
conferir a ordem depois.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

# ----------------------------------------------------------------- o cenario
BICHO = np.full((17, 20, 3), 40, dtype=np.uint8)
BICHO[3:8, 3:8] = (200, 30, 30)

ESCURO = (BICHO.astype(float) * 0.35).astype(np.uint8)   # bicho quase morto
OUTRO = np.full((17, 20, 3), 40, dtype=np.uint8)         # bicho nao aprendido
OUTRO[9:14, 9:15] = (30, 200, 30)

VAZIA = (0, False, None, [], None)
COM_BICHO = (1, False, None, [BICHO], None)          # na lista, sem moldura
ENGAJADO = (1, True, 0.9, [BICHO], BICHO)            # moldura vermelha
SUMIU_DA_LEITURA = (0, False, None, [], None)        # leitura ruim no meio da luta
QUASE_MORTO = (1, False, None, [ESCURO], None)       # sprite escurecido
DESCONHECIDO = (1, False, None, [OUTRO], None)       # nao esta na lista de bichos

ROTEIRO = ([VAZIA] * 3                     # andando
           + [COM_BICHO] * 5               # bicho aparece
           + [ENGAJADO] * 6                # engajou
           + [SUMIU_DA_LEITURA] * 4        # leitura ruim: a entrada piscou
           + [ENGAJADO] * 4                # voltou
           + [QUASE_MORTO] * 4             # quase morto: o cliente escurece
           + [DESCONHECIDO] * 4            # bicho que nao esta na lista
           + [VAZIA] * 8)                  # a lista esvazia de verdade

fita = []                                  # (quadro, o que aconteceu)
quadro = {"i": 0}


class Janela:
    _hWnd = 1
    title = "falso"
    isActive = True
    isMinimized = False
    left = top = 0
    width = height = 100


class OdoFalso:
    def __init__(self):
        self.pos = [0, 0]
        self.parado = 9

    def atualiza(self):
        pass

    def resync(self):
        pass

    def ancora(self, alvo):
        pass


def battle_state(_win):
    i = min(quadro["i"], len(ROTEIRO) - 1)
    return ROTEIRO[i]


def press(tecla):
    fita.append((quadro["i"], f"tecla {tecla}"))


def click_minimap(_win, passo):
    fita.append((quadro["i"], f"CLIQUE NO MAPA {passo}"))


def click_game(x, y):
    fita.append((quadro["i"], f"clique na tela ({x},{y})"))


def sleep(_s):
    pass


class RelogioFalso:
    """time.sleep vira contador de quadros: um sleep = um quadro."""

    def __init__(self):
        self.t = 0.0

    def time(self):
        return self.t


relogio = RelogioFalso()


def loop_sleep(segundos):
    relogio.t += max(segundos, 0.05)
    quadro["i"] += 1
    if quadro["i"] > len(ROTEIRO):
        main.STOP = True


# ------------------------------------------------------------- as substituicoes
main.setup_windows = lambda: (Janela(), Janela())
main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
main.read_bars = lambda win: (1.0, 1.0)
main.battle_state = battle_state
main.Odometro = lambda win: OdoFalso()
main.click_minimap = click_minimap
main.click_game = click_game
main.detect_marks = lambda win, mm=None, cor=None: [(0, 20), (0, -20)]
main.minimap_grab = lambda win: np.zeros((110, 108, 3), dtype=np.uint8)
main.is_usable = lambda win: True
main.focus_window = lambda win: True
main.wait_active = lambda win, prazo=1.0: True
main.restore_windows = lambda: None
main.keyboard = type("K", (), {"is_pressed": staticmethod(lambda k: False)})()
main.pyautogui = type("P", (), {"press": staticmethod(press)})()
main.time = type("T", (), {"time": staticmethod(relogio.time),
                           "sleep": staticmethod(loop_sleep)})()
main.load_monsters = lambda caminho=None: {"bicho": BICHO}
main.load_waypoints = lambda caminho=None: []          # regra de ouro, sem rota
main.ONLY_KNOWN_MONSTERS = True
main.AUTO_LEARN = False
main.ENABLE_WALK = True
main.USE_MAP_MARKS = True
main.USE_ROUTE_ORDER = False
main.ENABLE_HEAL = main.ENABLE_MANA = False
main.ENABLE_SPELL = False
main.ENABLE_AUTOCAST = False
main.ATTACK_CONFIRM = 2
main.WALK_CLICK_COOLDOWN = 0.0
main.STOP = False

main.run_bot()

# ------------------------------------------------------------------ o veredito
print("\nroteiro da battle list, quadro por quadro:")
print("  0-2 vazia | 3-7 na lista | 8-13 engajado | 14-17 leitura ruim |\n"
      "  18-21 engajado | 22-25 sprite escurecido | 26-29 desconhecido |\n"
      "  30+ vazia de verdade\n")
for i, acao in fita:
    print(f"  quadro {i:>2}: {acao}")

ataques = [i for i, a in fita if a == f"tecla {main.ATTACK_HOTKEY}"]
paradas = [i for i, a in fita if a == f"tecla {main.STOP_WALK_KEY}"]
cliques = [i for i, a in fita if a.startswith("CLIQUE NO MAPA")]

falhas = []
if not paradas:
    falhas.append("nunca apertou a tecla de parada")
if not ataques:
    falhas.append("nunca apertou a tecla de ataque")
if paradas and ataques and min(paradas) > min(ataques):
    falhas.append(f"atacou no quadro {min(ataques)} antes de parar "
                  f"no {min(paradas)}")
# clique no mapa so vale nos quadros em que a lista esta vazia de verdade
com_bicho = set(range(3, 30))   # tudo isso e bicho vivo do lado do personagem
no_meio_da_briga = [i for i in cliques if i in com_bicho]
if no_meio_da_briga:
    falhas.append(f"clicou no mapa durante a briga, nos quadros "
                  f"{no_meio_da_briga}")

print(f"\nparada nos quadros {paradas} | ataque nos quadros {ataques}")
print(f"cliques no mapa nos quadros {cliques}")
print("VEREDITO:", "OK - para antes de atacar e nao clica durante a briga"
      if not falhas else "FALHOU: " + "; ".join(falhas))
