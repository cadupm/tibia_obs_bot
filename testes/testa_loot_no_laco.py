# -*- coding: utf-8 -*-
"""O loot no LACO inteiro: bicho morre -> marca o corpo -> saqueia.

O testa_loot.py exercita a funcao de loot isolada. Este aqui percorre o caminho
de verdade dentro do run_bot: o bicho aparece na battle list, e engajado, some,
a trava confirma a morte, o corpo e marcado e o saque acontece. E onde se ve se
a fiacao esta certa - foi exatamente ai que o loot nao acontecia.
"""
import io, os, sys
from contextlib import redirect_stdout
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

BICHO = np.full((17, 20, 3), 40, dtype=np.uint8)
BICHO[3:8, 3:8] = (200, 30, 30)

VAZIA = (0, False, None, [], None)
NA_LISTA = (1, False, None, [BICHO], None)
ENGAJADO = (1, True, 0.9, [BICHO], BICHO)

# aparece, engaja, morre (some da lista) e o resto e cave vazia
ROTEIRO = ([VAZIA] * 2 + [NA_LISTA] * 3 + [ENGAJADO] * 6 + [VAZIA] * 25)

fita = []
quadro = {"i": 0}


class Janela:
    isActive = True
    title = "falso"
    isMinimized = False


class OdoFalso:
    def __init__(self, _win=None):
        self.pos = [0, 0]
        self.parado = 9

    def atualiza(self):
        pass

    def resync(self):
        pass

    def ancora(self, alvo):
        pass

    def mudou_de_andar(self):
        return False


def viewport_com_bicho(dx, dy):
    _vx, _vy, vw, vh = main.GAME_VIEW
    img = np.full((vh, vw, 3), 30, dtype=np.uint8)
    meio_col, meio_lin = (vw // main.TILE_PX) // 2, (vh // main.TILE_PX) // 2
    x = (meio_col + dx) * main.TILE_PX + 18
    y = (meio_lin + dy - main.CREATURE_BAR_ABOVE) * main.TILE_PX + 10
    img[y:y + 4, x:x + 31] = (0, 0, 0)
    img[y + 1:y + 3, x + 1:x + 30] = (0, 95, 0)
    return img


TELA = viewport_com_bicho(1, 0)             # bicho colado a direita


def loop_sleep(_s):
    quadro["i"] += 1
    if quadro["i"] >= len(ROTEIRO):
        main.STOP = True


main.setup_windows = lambda: (Janela(), Janela())
main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
main.read_bars = lambda win: (1.0, 1.0)
main.battle_state = lambda win: ROTEIRO[min(quadro["i"], len(ROTEIRO) - 1)]
main.Odometro = OdoFalso
main.client_rect = lambda win: (0, 0, 1920, 1009)
main.grab = lambda regiao: TELA
main.detect_marks = lambda win, mm=None, cor=None: []
main.is_usable = lambda win: True
main.focus_window = lambda win: True
main.restore_windows = lambda: None
main.keyboard = type("K", (), {"is_pressed": staticmethod(lambda k: False)})()
main.pyautogui = type("P", (), {
    "press": staticmethod(lambda t: fita.append((quadro["i"], t)))})()
main.click_minimap = lambda w, p: fita.append((quadro["i"], ("clique", p)))
main.mira_mouse = lambda x, y: fita.append((quadro["i"], ("mira", (x, y))))
main.time = type("T", (), {"time": staticmethod(lambda: quadro["i"] * 0.3),
                           "sleep": staticmethod(loop_sleep)})()
main.load_monsters = lambda caminho=None: {"bicho": BICHO}
main.load_waypoints = lambda caminho=None: []
main.load_evitar = lambda caminho=None: {}
main.ONLY_KNOWN_MONSTERS = True
main.AUTO_LEARN = False
main.ENABLE_WALK = True
main.USE_MAP_MARKS = True
main.USE_ROUTE_ORDER = False
main.ATTACK_MODE = "stand"
main.ENABLE_HEAL = main.ENABLE_MANA = False
main.ENABLE_SPELL = main.ENABLE_AUTOCAST = False
main.ENABLE_LOOT = True
main.ENABLE_PARALISIA = False
main.ATTACK_CONFIRM = 2
main.STOP = False

saida = io.StringIO()
with redirect_stdout(saida):
    main.run_bot()
log = saida.getvalue()

print("roteiro: 0-1 vazia | 2-4 na lista | 5-10 engajado | 11+ vazia (morreu)\n")
for i, o_que in fita:
    print(f"  quadro {i:>2}: {o_que}")

saques = [i for i, o in fita if o == main.LOOT_HOTKEY]
miras = [i for i, o in fita if isinstance(o, tuple) and o[0] == "mira"]
falhas = []
print(f"\nmarcou o corpo: {'[loot] o bicho morreu' in log}")
print(f"saques ({main.LOOT_HOTKEY!r}): {saques}")
print(f"mirou o cursor: {miras}")
if "[loot] o bicho morreu" not in log:
    falhas.append("o corpo nunca foi marcado: a fiacao entre a morte e o loot "
                  "nao fecha")
if not saques:
    falhas.append("nunca apertou a tecla de saque")
if not miras:
    falhas.append("nunca mirou o cursor no corpo")

print("\nVEREDITO:", "OK - o loot acontece de ponta a ponta"
      if not falhas else "FALHOU: " + "; ".join(falhas))
