# -*- coding: utf-8 -*-
"""Parar e comecar de novo tem de comecar limpo.

Relatado: "a battle list ficava travando o inicio do bot quando para e
recomecava; deveria zerar as variaveis globais ao parar".

O bot roda dentro do mesmo processo da GUI, entao parar e comecar nao recria o
modulo: tudo o que ele APRENDEU continua la. O pior deles e a coluna das barras
da battle list (_BATTLE_ANCHOR). Ela e aprendida uma vez - e so quando ainda
NAO HA ancora -, entao aprendida errada, com o painel por cima ou o cliente
redesenhando, fica errada para sempre e nenhuma leitura seguinte a corrige.

Aqui a sessao 1 aprende uma ancora envenenada e a sessao 2 tem de ignora-la.
"""
import io
import os
import sys
from contextlib import redirect_stdout
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main


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
    main.battle_state = lambda win: (0, False, None, [], None)
    main.grab = lambda regiao: np.zeros((110, 108, 3), dtype=np.uint8)
    main.viewport = lambda win: np.zeros((main.GAME_VIEW[3],
                                          main.GAME_VIEW[2], 3),
                                         dtype=np.uint8)
    main.detect_creatures = lambda win, img=None: []
    main.acha_moldura_do_alvo = lambda img: None
    main.client_rect = lambda win: (0, 0, 1920, 1009)
    main.detect_marks = lambda win, mm=None, cor=None: []
    main.is_usable = lambda win: True
    main.focus_window = lambda win: True
    main.restore_windows = lambda: None
    main.quem_tapa = lambda leitura, teclado=None, minimo=0.01: []
    main.confere_a_grade = lambda leitura: None
    main.le_maximos = lambda leitura: 0
    main.keyboard = type("K", (), {
        "is_pressed": staticmethod(lambda k: False)})()
    main.pyautogui = type("P", (), {
        "press": staticmethod(lambda t: None),
        "keyDown": staticmethod(lambda t: None),
        "keyUp": staticmethod(lambda t: None)})()
    main.load_monsters = lambda caminho=None: {}
    main.load_loot_flags = lambda caminho=None: {}
    main.load_waypoints = lambda caminho=None: []
    main.load_evitar = lambda caminho=None: {}
    main.Odometro = OdoFalso
    main.ENABLE_WALK = False
    main.ENABLE_HEAL = main.ENABLE_MANA = False
    main.ENABLE_SPELL = main.ENABLE_AUTOCAST = False
    main.ENABLE_PARALISIA = False
    main.ENABLE_LOOT = True


def uma_sessao(voltas=4):
    """Roda o laco por algumas leituras e para, como o botao Parar faz."""
    conta = {"i": 0}

    def dorme(_s):
        conta["i"] += 1
        if conta["i"] >= voltas:
            main.STOP = True

    main.time = type("T", (), {
        "time": staticmethod(lambda: conta["i"] * 0.3),
        "sleep": staticmethod(dorme)})()
    main.STOP = False
    saida = io.StringIO()
    with redirect_stdout(saida):
        main.run_bot()
    return saida.getvalue()


falhas = []
prepara()

# ---- SESSAO 1: aprende uma ancora envenenada e uma barra "gigante"
ENVENENADA = (1234, 5678)
main._BATTLE_ANCHOR[ENVENENADA] = 999
main._BATTLE_TRACK = 12345
main._BARS_CACHE["qualquer"] = "lixo"
main._CALIBRA["avisou"] = True
main._CALIBRA["sem_coluna"] = 40
print("antes de recomecar, o modulo carrega o aprendido da sessao passada:")
print(f"  _BATTLE_ANCHOR = {dict(main._BATTLE_ANCHOR)}")
print(f"  _BATTLE_TRACK  = {main._BATTLE_TRACK}")
print(f"  _BARS_CACHE    = {main._BARS_CACHE}")
print(f"  _CALIBRA       = {main._CALIBRA}")

# ---- SESSAO 2: o arranque tem de limpar tudo isso
uma_sessao()
print("\ndepois de comecar de novo:")
print(f"  _BATTLE_ANCHOR = {dict(main._BATTLE_ANCHOR)}")
print(f"  _BATTLE_TRACK  = {main._BATTLE_TRACK}")
print(f"  _BARS_CACHE    = {main._BARS_CACHE}")
print(f"  _CALIBRA       = {main._CALIBRA}")

if main._BATTLE_ANCHOR.get(ENVENENADA) is not None:
    falhas.append(
        "a coluna aprendida da battle list sobreviveu ao recomeco. Ela so e "
        "aprendida quando NAO HA ancora, entao aprendida errada uma vez fica "
        "errada para sempre - e o bot le a battle list no lugar errado desde "
        "a primeira leitura da sessao nova")
if main._BATTLE_TRACK:
    falhas.append(f"_BATTLE_TRACK ficou em {main._BATTLE_TRACK}: e a maior "
                  f"barra ja vista, que serve de 100% do alvo. Vinda de outra "
                  f"sessao, a vida do alvo sai errada")
if main._BARS_CACHE:
    falhas.append(f"_BARS_CACHE ficou com {main._BARS_CACHE}: a regiao das "
                  f"barras de vida e mana e medida na tela e nao pode vir da "
                  f"sessao passada")
if main._CALIBRA.get("avisou") or main._CALIBRA.get("sem_coluna"):
    falhas.append(f"_CALIBRA ficou em {main._CALIBRA}: os avisos de calibracao "
                  f"nao saem duas vezes na mesma sessao, mas tem de sair de "
                  f"novo numa sessao nova")

# ---- e a fila de corpos nao atravessa sessao
prepara()
main.ENABLE_LOOT = True
log = uma_sessao()
if "corpo(s) na fila" in log:
    falhas.append("comecou a sessao com corpo na fila")

print("\nVEREDITO:", "OK - recomecar comeca limpo"
      if not falhas else "FALHOU: " + "; ".join(falhas))
