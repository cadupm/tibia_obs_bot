# -*- coding: utf-8 -*-
"""O loot vale nos tres modos de luta, e sem depender de andar a rota.

Duas dependencias escondidas faziam o saque existir so em parte das
configuracoes, e nenhuma delas tinha a ver com saquear:

  1. o loot era chamado DENTRO do `if ENABLE_WALK:`. Com o andar desligado -
     quem cava um ponto fixo, ou quem so quer o bot lutando - o bot nao
     saqueava nada, e nada no log dizia por que;
  2. o odometro so era criado com ENABLE_WALK ligado. Sem ele o bot marcava
     todo corpo na origem, ou seja debaixo do proprio pe, e saqueava o chao.

Este teste roda o laco de verdade (run_bot) nas seis combinacoes de modo de
luta x andar ligado/desligado, e exige o mesmo resultado em todas: um bicho
morreu, o corpo foi localizado pela BARRA QUE SUMIU, e o bot clicou nele - uma
vez.
"""
import io
import os
import sys
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
ROTEIRO = [VAZIA] * 2 + [NA_LISTA] * 3 + [ENGAJADO] * 6 + [VAZIA] * 30


class Janela:
    isActive = True
    title = "falso"
    isMinimized = False


class OdoFalso:
    """Nao anda: o corpo fica onde morreu, colado no personagem."""

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


def chao():
    """Textura fixa de caverna: o chao nao pode mudar sozinho, senao a busca
    do corpo nao teria como separar o que mudou."""
    rng = np.random.default_rng(3)
    _vx, _vy, vw, vh = main.GAME_VIEW
    return rng.integers(40, 70, (vh, vw, 3), dtype=np.uint8)


CHAO = chao()


def quadrado(img, dx, dy, cor, tamanho=44):
    """Desenha um bicho ou um corpo no quadrado dado."""
    _vx, _vy, vw, vh = main.GAME_VIEW
    meio_col, meio_lin = (vw // main.TILE_PX) // 2, (vh // main.TILE_PX) // 2
    x0 = (meio_col + dx) * main.TILE_PX + (main.TILE_PX - tamanho) // 2
    y0 = (meio_lin + dy) * main.TILE_PX + (main.TILE_PX - tamanho) // 2
    img[y0:y0 + tamanho, x0:x0 + tamanho] = cor
    return img


def barra(img, dx, dy):
    """A moldura da barra de vida, que e como o bot enxerga a criatura."""
    _vx, _vy, vw, vh = main.GAME_VIEW
    meio_col, meio_lin = (vw // main.TILE_PX) // 2, (vh // main.TILE_PX) // 2
    x = (meio_col + dx) * main.TILE_PX + 18
    y = (meio_lin + dy - main.CREATURE_BAR_ABOVE) * main.TILE_PX + 10
    img[y:y + 4, x:x + 31] = (0, 0, 0)
    img[y + 1:y + 3, x + 1:x + 30] = (0, 95, 0)
    return img


# BICHO VIVO e CORPO no mesmo quadrado, sobre o mesmo chao: a diferenca entre
# os dois e o unico sinal de onde ele caiu, e e o que o bot usa.
TELA_VIVO = barra(quadrado(CHAO.copy(), 1, 0, (170, 40, 40)), 1, 0)
TELA_MORTO = quadrado(CHAO.copy(), 1, 0, (95, 75, 55))


def roda(modo, andar):
    """Roda o laco inteiro e devolve o que o bot fez pelo loot."""
    fita, quadro = [], {"i": 0}

    def loop_sleep(_s):
        quadro["i"] += 1
        if quadro["i"] >= len(ROTEIRO):
            main.STOP = True

    main.setup_windows = lambda: (Janela(), Janela())
    main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
    main.read_bars = lambda win: (1.0, 1.0)
    main.battle_state = lambda win: ROTEIRO[min(quadro["i"],
                                                len(ROTEIRO) - 1)]
    main.Odometro = OdoFalso
    main.client_rect = lambda win: (0, 0, 1920, 1009)
    # a tela acompanha o roteiro: com bicho na lista, o bicho vivo; depois de
    # ele sair, o corpo no mesmo quadrado
    main.grab = lambda regiao: (
        TELA_VIVO if ROTEIRO[min(quadro["i"], len(ROTEIRO) - 1)][0] > 0
        else TELA_MORTO)
    main.detect_marks = lambda win, mm=None, cor=None: []
    main.is_usable = lambda win: True
    main.focus_window = lambda win: True
    main.restore_windows = lambda: None
    main.keyboard = type("K", (), {
        "is_pressed": staticmethod(lambda k: False)})()
    main.pyautogui = type("P", (), {
        "press": staticmethod(lambda t: fita.append(("tecla", t))),
        "keyDown": staticmethod(lambda t: None),
        "keyUp": staticmethod(lambda t: None)})()
    main.click_minimap = lambda w, p: fita.append(("mapa", p))
    main.mira_mouse = lambda x, y: fita.append(("mira", (x, y)))
    main.click_game = lambda x, y, pausa=0.09, botao="esquerdo", mod="": \
        fita.append(("clique", botao))
    main.time = type("T", (), {
        "time": staticmethod(lambda: quadro["i"] * 0.3),
        "sleep": staticmethod(loop_sleep)})()
    main.load_monsters = lambda caminho=None: {"bicho": BICHO}
    main.load_waypoints = lambda caminho=None: []
    main.load_evitar = lambda caminho=None: {}
    main.ONLY_KNOWN_MONSTERS = True
    main.AUTO_LEARN = False
    main.USE_MAP_MARKS = andar
    main.USE_ROUTE_ORDER = False
    main.ENABLE_WALK = andar
    main.ATTACK_MODE = modo
    main.ENABLE_HEAL = main.ENABLE_MANA = False
    main.ENABLE_SPELL = main.ENABLE_AUTOCAST = False
    main.ENABLE_LOOT = True
    main.ENABLE_PARALISIA = False
    main.PARAR_SE_MUDAR_ANDAR = False
    main.ATTACK_CONFIRM = 2
    main.STOP = False

    saida = io.StringIO()
    with redirect_stdout(saida):
        main.run_bot()
    log = saida.getvalue()
    return {
        "achou": ("a barra de vida sumiu em " in log
                  or "; nenhuma barra sumiu" in log),
        "pela_barra": "a barra de vida sumiu em " in log,
        "marcou": "[loot] bicho morreu" in log,
        "cliques": sum(1 for a in fita if a[0] == "clique"),
        "teclas": sum(1 for a in fita if a[0] == "tecla"
                      and a[1] != main.STOP_WALK_KEY),
        "log": log,
    }


falhas = []
print("um bicho morre colado; o que o bot faz pelo corpo:\n")
print(f"  {'modo':<7} {'andar':<7} {'p/ barra':<9} {'marcou':<7} "
      f"{'cliques':>7}")
resultados = {}
for modo in ("stand", "chase", "kite"):
    for andar in (True, False):
        r = roda(modo, andar)
        resultados[(modo, andar)] = r
        print(f"  {modo:<7} {str(andar):<7} {str(r['pela_barra']):<9} "
              f"{str(r['marcou']):<7} {r['cliques']:>7}")
        rotulo = f"{modo}/andar={andar}"
        if not r["pela_barra"]:
            falhas.append(f"{rotulo}: nao localizou o corpo pela BARRA QUE "
                          f"SUMIU. Bicho morto perde a barra de vida, entao o "
                          f"quadrado que tinha barra e nao tem mais e onde ele "
                          f"caiu - e o sinal direto, sem limiar")
        if not r["marcou"]:
            falhas.append(f"{rotulo}: nao marcou o corpo - a fiacao entre a "
                          f"morte e o loot nao fecha")
        if not r["cliques"]:
            falhas.append(f"{rotulo}: nao clicou no corpo")
        if r["cliques"] != main.LOOT_CLIQUES:
            falhas.append(f"{rotulo}: {r['cliques']} clique(s) no corpo, "
                          f"esperava exatamente {main.LOOT_CLIQUES}")

# o gesto tem de ser o MESMO: nao e so "funciona em todos", e "funciona igual"
# o gesto e o CLIQUE. As outras teclas do laco (atacar, andar, fechar menu) nao
# sao saque e mudam legitimamente entre os modos.
gestos = {k: v["cliques"] for k, v in resultados.items()}
distintos = set(gestos.values())
print(f"\ngestos distintos entre as 6 combinacoes: {len(distintos)} "
      f"{sorted(distintos)}")
if len(distintos) != 1:
    falhas.append(f"o saque nao e igual em todas as combinacoes: {gestos}. O "
                  f"modo de luta muda de onde se parte, nao o que se faz com "
                  f"o corpo")

# ------------- NUNCA FICAR SEM AGIR. A identificacao na tela pode nao fechar:
# os limiares vem de cenario sintetico, e a sprite do bicho e maior que um
# quadrado, entao o vizinho tambem muda. Nesse caso o bot tem de cair no palpite
# da odometria e clicar UM ponto, e nao deixar de fazer nada - foi assim que uma
# versao que pegava loot virou uma que nao pegava.
print("\ncom o quadrado NAO mudando na morte (identificacao nao fecha)")
# TELA_VIVO o tempo todo: o bot VE a criatura enquanto ela esta na lista - sem
# isso nem chega a existir corpo para procurar, que e outra falha - e o quadrado
# nao muda na morte, que e o caso em que a identificacao nao fecha. Chao puro
# aqui nao serve: sem a barra de vida o bot nunca ve o bicho, e o teste mediria
# a falha errada.
CONGELADA = TELA_VIVO
for so_se_achou in (False, True):
    main.LOOT_SO_SE_ACHOU = so_se_achou
    fita_c, quadro_c = [], {"i": 0}

    def sleep_c(_s, _q=quadro_c):
        _q["i"] += 1
        if _q["i"] >= len(ROTEIRO):
            main.STOP = True

    main.grab = lambda regiao: CONGELADA
    main.battle_state = lambda win, _q=quadro_c: ROTEIRO[
        min(_q["i"], len(ROTEIRO) - 1)]
    main.time = type("T", (), {
        "time": staticmethod(lambda _q=quadro_c: _q["i"] * 0.3),
        "sleep": staticmethod(sleep_c)})()
    main.click_game = lambda x, y, pausa=0.09, botao="esquerdo", mod="": \
        fita_c.append(("clique", botao))
    main.STOP = False
    saida = io.StringIO()
    with redirect_stdout(saida):
        main.run_bot()
    n = sum(1 for a in fita_c if a[0] == "clique")
    print(f"  LOOT_SO_SE_ACHOU={so_se_achou}: {n} clique(s) no corpo")
    if not so_se_achou and n == 0:
        falhas.append("sem identificar o quadrado na tela o bot nao fez NADA. "
                      "Tem de cair no palpite da odometria e clicar um ponto: "
                      "nao decidir nao pode virar nao agir")
    if so_se_achou and n:
        falhas.append(f"com LOOT_SO_SE_ACHOU ligado ele clicou {n}x sem ter "
                      f"identificado o quadrado")
main.LOOT_SO_SE_ACHOU = False

print("\nVEREDITO:", "OK - o mesmo saque em stand, chase e kite, com ou sem rota"
      if not falhas else "FALHOU: " + "; ".join(falhas))
