# -*- coding: utf-8 -*-
"""Cura: comecar com a vida baixa, e a prioridade da emergencia.

Duas perguntas, medidas no laco de verdade:

  1. comecando ABAIXO do limite de cura, o bot ainda ataca e anda? Ou fica so
     curando e o resto nao acontece?
  2. passando do limite da emergencia, ela sai NA HORA - ou espera o cooldown
     da cura normal que acabou de sair?
"""
import io, os, sys
from contextlib import redirect_stdout
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

BICHO = np.full((17, 20, 3), 40, dtype=np.uint8)
BICHO[3:8, 3:8] = (200, 30, 30)
NA_LISTA = (1, False, None, [BICHO], None)

MAX = 1000
vida = {"hp": 1.0}
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


def prepara(hp_inicial):
    vida["hp"] = hp_inicial
    fita.clear()
    quadro["i"] = 0
    main.setup_windows = lambda: (Janela(), Janela())
    main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
    main.read_bars = lambda win: (vida["hp"], 1.0)
    main.battle_state = lambda win: NA_LISTA
    main.Odometro = OdoFalso
    main.is_usable = lambda win: True
    main.focus_window = lambda win: True
    main.restore_windows = lambda: None
    main.keyboard = type("K", (), {"is_pressed": staticmethod(lambda k: False)})()
    main.pyautogui = type("P", (), {
        "press": staticmethod(lambda t: fita.append((quadro["i"], t)))})()
    main.click_minimap = lambda w, p: fita.append((quadro["i"], ("clique", p)))
    main.detect_marks = lambda win, mm=None, cor=None: [(0, 20)]
    main.detect_creatures = lambda win, img=None: [(1, 0)]
    main.grab = lambda regiao: np.zeros((110, 108, 3), dtype=np.uint8)
    main.load_monsters = lambda caminho=None: {"bicho": BICHO}
    main.load_waypoints = lambda caminho=None: []
    main.load_evitar = lambda caminho=None: {}
    main.HP_MAX, main.MANA_MAX = MAX, MAX
    main.ENABLE_HEAL = True
    main.HEAL_HOTKEY, main.HEAL_THRESHOLD = "f2", 900
    main.HEAL_STRONG_HOTKEY, main.HEAL_STRONG_THRESHOLD = "f5", 700
    main.HEAL_COOLDOWN = 1.0
    main.ENABLE_MANA = False
    main.ENABLE_SPELL = main.ENABLE_AUTOCAST = False
    main.ENABLE_LOOT = False
    main.ENABLE_WALK = True
    main.USE_MAP_MARKS = True
    main.ATTACK_MODE = "stand"
    main.ATTACK_CONFIRM = 1
    main.ONLY_KNOWN_MONSTERS = True
    main.AUTO_LEARN = False
    main.WALK_RESUME_READS = 1
    main.STOP = False


def roda(passos=40, muda_vida=None):
    def loop_sleep(_s):
        quadro["i"] += 1
        if muda_vida:
            muda_vida(quadro["i"])
        if quadro["i"] >= passos:
            main.STOP = True

    main.time = type("T", (), {
        "time": staticmethod(lambda: quadro["i"] * 0.5),
        "sleep": staticmethod(loop_sleep)})()
    saida = io.StringIO()
    with redirect_stdout(saida):
        main.run_bot()
    return saida.getvalue()


falhas = []

# ------------------- 1) comecar com a vida abaixo do limite de cura
prepara(hp_inicial=0.75)               # 750 de 1000: abaixo de 900, acima de 700
log = roda()
teclas = [t for _q, t in fita if isinstance(t, str)]
print(f"comecando com 75% de vida (limite de cura em 90%):")
print(f"  curas: {teclas.count('f2')} | emergencias: {teclas.count('f5')}")
print(f"  ataques: {teclas.count('space')}")
print(f"  parou de andar: {teclas.count(main.STOP_WALK_KEY)}")
if not teclas.count("f2"):
    falhas.append("nao curou comecando abaixo do limite")
if not teclas.count("space"):
    falhas.append("comecando com vida baixa, NAO ATACOU")

# ------------------- 2) prioridade: a emergencia nao espera a cura normal
def cai_a_vida(i):
    if i == 3:
        vida["hp"] = 0.65             # 650: passou do limite da emergencia


prepara(hp_inicial=0.85)               # comeca curando normal
log = roda(passos=14, muda_vida=cai_a_vida)
ordem = [(q, t) for q, t in fita if t in ("f2", "f5")]
print(f"\nvida caindo de 85% para 65% na leitura 3:")
print(f"  sequencia de curas: {ordem}")
primeira_normal = next((q for q, t in ordem if t == "f2"), None)
primeira_forte = next((q for q, t in ordem if t == "f5"), None)
print(f"  primeira normal na leitura {primeira_normal}, "
      f"primeira emergencia na {primeira_forte}")
if primeira_forte is None:
    falhas.append("nunca deu a emergencia depois de passar do limite")
elif primeira_forte > 4:
    falhas.append(f"a emergencia esperou ate a leitura {primeira_forte} "
                  f"(a vida passou do limite na 3): ficou presa no cooldown "
                  f"da cura normal")

print("\nVEREDITO:", "OK - cura, ataca, e a emergencia tem prioridade"
      if not falhas else "FALHOU: " + "; ".join(falhas))
