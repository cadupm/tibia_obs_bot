# -*- coding: utf-8 -*-
"""Chase que cai sozinho: o bot confere de tempos em tempos e religa.

Pedido: "podemos garantir que ta sempre no chase quando ta mesmo se sair?
checar a cada 10seg?" - virou CHASE_CHECK_SEGUNDOS (30s por padrao).

O cliente desenha dois bonecos empilhados no painel de equipamento - parado
(Stand) e correndo (Chase) - e so o ativo fica colorido. Medido no cliente do
usuario, com os dois estados reais: ligado forma um bloco de ~75 px verdes
saturados na caixa do boneco correndo; desligado nao tem NENHUM. Sem limiar
para calibrar - e diferenca de conjuntos, como a barra de vida.

Este arquivo mede duas coisas:
  1. chase_ligado() acerta os dois estados, numa imagem sintetica que
     reproduz a cor medida (nao a foto real, que e uma captura de tela e nao
     vai para o repositorio);
  2. no laco de verdade, com o watchdog ligado, achar o chase desligado
     dispara a tecla configurada - e achar ligado nao dispara nada.
"""
import io
import os
import sys
from contextlib import redirect_stdout
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

falhas = []


# ------------------------------------------------- 1) o detector, isolado
def caixa_do_icone(ligado):
    """
    Reproduz a caixa do boneco: fundo cinza do painel, com o sprite colorido
    SO quando ligado. O sprite de verdade tem sombreado interno (medido: G
    variando de 91 a 254) - aqui variam tons de verde tambem, para o teste nao
    passar so por acaso com uma cor solida.
    """
    _, _, w, h = main.CHASE_ICON
    img = np.full((h, w, 3), 40, dtype=np.uint8)      # fundo cinza do painel
    if ligado:
        rng = np.random.default_rng(3)
        tons = rng.integers(40, 110, (h - 4, w - 4))   # variacao de sombreado
        img[2:h - 2, 2:w - 2, 1] = tons + 90            # canal G bem mais alto
        img[2:h - 2, 2:w - 2, 0] = tons - 5
        img[2:h - 2, 2:w - 2, 2] = tons - 5
    return img


print("chase_ligado() numa caixa sintetica, cor e variacao medidas no cliente "
      "real:\n")
for ligado in (True, False):
    img = caixa_do_icone(ligado)
    lido = main.chase_ligado(None, img=img)
    print(f"  caixa {'LIGADA' if ligado else 'DESLIGADA'}: chase_ligado() = "
          f"{lido}")
    if lido != ligado:
        falhas.append(f"caixa {'ligada' if ligado else 'desligada'}: "
                      f"chase_ligado() devolveu {lido}")

if main.chase_ligado(None, img=np.zeros((0, 0, 3), dtype=np.uint8)) is not None:
    falhas.append("imagem invalida/vazia devia devolver None, nao um booleano "
                  "- None nao e False, e quem chama nao pode religar baseado "
                  "em 'nao consegui ver'")


# --------------------------------------------- 2) o watchdog, no laco real
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


def roda(chase_esta_ligado, leituras=30):
    fita, quadro = [], {"i": 0}

    def loop_sleep(_s):
        quadro["i"] += 1
        if quadro["i"] >= leituras:
            main.STOP = True

    main.setup_windows = lambda: (Janela(), Janela())
    main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
    main.read_bars = lambda win: (1.0, 1.0)
    main.battle_state = lambda win: (0, False, None, [], None)
    main.grab = lambda regiao: np.zeros((110, 108, 3), dtype=np.uint8)
    main.viewport = lambda win: np.zeros((main.GAME_VIEW[3], main.GAME_VIEW[2],
                                          3), dtype=np.uint8)
    main.detect_creatures = lambda win, img=None: []
    main.acha_moldura_do_alvo = lambda img: None
    main.chase_ligado = lambda win: chase_esta_ligado
    main.Odometro = OdoFalso
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
        "press": staticmethod(lambda t: fita.append((quadro["i"], "tecla", t))),
        "keyDown": staticmethod(lambda t: None),
        "keyUp": staticmethod(lambda t: None)})()
    main.click_minimap = lambda w, p: fita.append((quadro["i"], "mapa", p))
    main.click_game = lambda x, y, pausa=0.09, botao="esquerdo", mod="": \
        fita.append((quadro["i"], botao, (x, y)))
    main.time = type("T", (), {
        "time": staticmethod(lambda: quadro["i"] * 0.3),
        "sleep": staticmethod(loop_sleep)})()
    main.load_monsters = lambda caminho=None: {}
    main.load_loot_flags = lambda caminho=None: {}
    main.load_waypoints = lambda caminho=None: []
    main.load_evitar = lambda caminho=None: {}
    main.ONLY_KNOWN_MONSTERS = True
    main.AUTO_LEARN = False
    main.ENABLE_WALK = False
    main.USE_MAP_MARKS = False
    main.USE_ROUTE_ORDER = False
    main.ATTACK_MODE = "chase"
    main.ENABLE_HEAL = main.ENABLE_MANA = False
    main.ENABLE_SPELL = main.ENABLE_AUTOCAST = False
    main.ENABLE_PARALISIA = False
    main.ENABLE_LOOT = False
    main.ENABLE_CHASE_WATCHDOG = True
    main.CHASE_HOTKEY = "="
    main.CHASE_CHECK_SEGUNDOS = 0.01     # baixo de proposito: confere toda leitura
    main.STOP = False

    saida = io.StringIO()
    with redirect_stdout(saida):
        main.run_bot()
    return {"fita": fita, "log": saida.getvalue()}


print("\ncom o chase LIGADO o tempo todo:")
r = roda(True)
teclas = [f for f in r["fita"] if f[1] == "tecla" and f[2] == "="]
print(f"  tecla '=' apertada: {len(teclas)} vez(es)")
if teclas:
    falhas.append(f"com chase ligado, apertou '=' {len(teclas)} vez(es) - "
                  f"nao devia mexer em nada")

print("\ncom o chase DESLIGADO o tempo todo:")
r = roda(False)
teclas = [f for f in r["fita"] if f[1] == "tecla" and f[2] == "="]
print(f"  tecla '=' apertada: {len(teclas)} vez(es)")
religou = [l for l in r["log"].splitlines() if "religar" in l]
for l in religou[:2]:
    print("   " + l.strip())
if not teclas:
    falhas.append("com chase desligado o tempo todo, o watchdog nunca "
                  "apertou a tecla de religar")

print("\nVEREDITO:", "OK - o watchdog so mexe quando o chase esta desligado"
      if not falhas else "FALHOU: " + "; ".join(falhas))
