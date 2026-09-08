# -*- coding: utf-8 -*-
"""Uma leitura ruim nao pode matar a cacada.

Aconteceu em jogo: um KeyError numa leitura derrubou o bot no meio de uma cave -
e o personagem fica la, parado, sendo comido. Erro isolado tem de entrar no log
e a volta seguinte tentar de novo; erros em SEQUENCIA significam que algo mudou
de verdade (janela fechada, layout diferente) e ai se para.
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


def prepara():
    main.setup_windows = lambda: (Janela(), Janela())
    main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
    main.read_bars = lambda win: (1.0, 1.0)
    main.Odometro = OdoFalso
    main.is_usable = lambda win: True
    main.focus_window = lambda win: True
    main.restore_windows = lambda: None
    main.keyboard = type("K", (), {"is_pressed": staticmethod(lambda k: False)})()
    main.pyautogui = type("P", (), {"press": staticmethod(lambda t: None)})()
    main.load_monsters = lambda caminho=None: {}
    main.load_waypoints = lambda caminho=None: []
    main.load_evitar = lambda caminho=None: {}
    main.detect_marks = lambda win, mm=None, cor=None: []
    main.detect_creatures = lambda win, img=None: []
    main.grab = lambda regiao: np.zeros((110, 108, 3), dtype=np.uint8)
    main.ENABLE_WALK = False
    main.ENABLE_HEAL = main.ENABLE_MANA = False
    main.ENABLE_SPELL = main.ENABLE_AUTOCAST = False
    main.ATTACK_MODE = "stand"
    main.STOP = False


falhas = []

# ----------------------------------------- 1) erro isolado: continua rodando
prepara()
quadro = {"i": 0}


def battle_com_um_erro(_win):
    quadro["i"] += 1
    if quadro["i"] == 3:
        raise KeyError("q")               # o erro que aconteceu em jogo
    if quadro["i"] > 12:
        main.STOP = True
    return VAZIA


main.battle_state = battle_com_um_erro
main.time = type("T", (), {"time": staticmethod(lambda: quadro["i"] * 0.2),
                           "sleep": staticmethod(lambda s: None)})()
saida = io.StringIO()
with redirect_stdout(saida):
    main.run_bot()
log = saida.getvalue()
print(f"erro isolado: o laco rodou {quadro['i']} leituras")
print(f"  registrou o erro no log: {'[erro] KeyError' in log}")
print(f"  parou por causa dele:    {'erros seguidos demais' in log}")
if quadro["i"] < 12:
    falhas.append(f"morreu no erro isolado (parou na leitura {quadro['i']})")
if "[erro] KeyError" not in log:
    falhas.append("nao registrou o erro no log")

# ------------------------------- 2) erro em toda leitura: para e nao insiste
prepara()
contas = {"i": 0}


def battle_sempre_com_erro(_win):
    contas["i"] += 1
    raise KeyError("c")


main.battle_state = battle_sempre_com_erro
main.time = type("T", (), {"time": staticmethod(lambda: contas["i"] * 0.2),
                           "sleep": staticmethod(lambda s: None)})()
saida = io.StringIO()
with redirect_stdout(saida):
    main.run_bot()
log = saida.getvalue()
print(f"\nerro em toda leitura: tentou {contas['i']} vezes "
      f"(limite {main.ERROS_SEGUIDOS_MAX})")
print(f"  parou de vez: {'erros seguidos demais' in log}")
if contas["i"] != main.ERROS_SEGUIDOS_MAX:
    falhas.append(f"tentou {contas['i']} vezes, esperava "
                  f"{main.ERROS_SEGUIDOS_MAX}")
if "erros seguidos demais" not in log:
    falhas.append("nao parou depois dos erros seguidos")

print("\nVEREDITO:", "OK - aguenta erro isolado e para no persistente"
      if not falhas else "FALHOU: " + "; ".join(falhas))
