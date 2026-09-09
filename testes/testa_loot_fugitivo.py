# -*- coding: utf-8 -*-
"""Um bicho fugiu da tela e a entrada dele ficou na battle list. O corpo do que
morreu tem de ser saqueado do mesmo jeito.

Tirado de um log de cacada de verdade:

    [loot] bicho morreu a -4,-5 SQM; 1 corpo(s) na fila
    [kite] 1 na battle list e nenhum bicho na tela: correu para fora do alcance
    [stop] parada solicitada por codigo

O corpo foi marcado certo e o saque NUNCA aconteceu: o loot esperava a battle
list VAZIA, e a entrada do fugitivo nao sai enquanto ele estiver vivo. O corpo
envelhecia no chao ate vencer LOOT_VALIDADE.

As tres razoes de esperar valem para bicho PERTO, nao para entrada na lista:
clique na tela durante o ataque troca chase por stand no cliente; parado em cima
do corpo com bicho do lado o personagem apanha de graca; e alvo engajado nao se
abandona. Bicho fora da tela esta a mais de 7 SQM de lado ou 5 de altura - nao
alcanca o personagem e nao esta sendo atacado.

O que se mede aqui:
  - com o fugitivo na lista e NADA na tela, o corpo e saqueado;
  - com bicho na tela, o saque espera (a razao de esperar continua valendo);
  - com alvo ENGAJADO, o saque espera - mesmo que a tela nao mostre nada.
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
CHAO = np.random.default_rng(11).integers(40, 70, (VH, VW, 3), dtype=np.uint8)

BICHO = np.full((17, 20, 3), 40, dtype=np.uint8)
BICHO[3:8, 3:8] = (200, 30, 30)


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


MORTO_EM = (1, 0)
# dois bichos: o que morre (colado) e o que foge (tambem colado, no comeco)
FUGITIVO_EM = (2, 0)
TELA_DOIS = barra(barra(desenha(desenha(CHAO.copy(), MORTO_EM, (170, 40, 40)),
                               FUGITIVO_EM, (170, 40, 40)),
                        MORTO_EM), FUGITIVO_EM)
# depois: o corpo no lugar do que morreu, e o fugitivo FORA DA TELA
TELA_SO_CORPO = desenha(CHAO.copy(), MORTO_EM, (95, 75, 55))
# variante: o fugitivo continua VISIVEL na tela
TELA_COM_BICHO = barra(desenha(desenha(CHAO.copy(), MORTO_EM, (95, 75, 55)),
                               FUGITIVO_EM, (170, 40, 40)), FUGITIVO_EM)


class Janela:
    isActive = True
    title = "falso"
    isMinimized = False


class OdoFalso:
    """O laco cria DOIS odometros: o da rota/loot e o do kite. Guardar so o
    ultimo fazia o clique de mapa mover o do kite e o loot nunca chegar no
    corpo - 14 cliques com a distancia parada em 2 SQM."""

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


def roda(fugitivo_visivel, fugitivo_engajado):
    """
    Dois bichos, um morre, o outro fica na lista. Devolve o que o bot fez.

    `fugitivo_visivel` diz se o sobrevivente aparece na tela do jogo;
    `fugitivo_engajado` se a moldura vermelha esta nele.
    """
    fita, quadro = [], {"i": 0}
    OdoFalso.todos = []
    # 2 na lista engajado -> 1 na lista (um morreu) pelo resto do roteiro
    # O FUGITIVO PRECISA CONTINUAR RESPONDENDO ao ataque, senao depois de
    # ATTACK_GIVEUP pressionadas sem engajar o bot conclui que a lista nao
    # responde (NPC, player) e para de considerar que esta lutando - e ai o
    # saque libera pelo motivo errado. Com ele visivel na tela a moldura
    # aparece de vez em quando, como aconteceria com um bicho de verdade.
    def entrada(i):
        engajado = fugitivo_engajado or (fugitivo_visivel and i % 3 == 0)
        return (1, engajado, 0.9 if engajado else None,
                [BICHO], BICHO if engajado else None)

    roteiro = ([(2, True, 0.9, [BICHO, BICHO], BICHO)] * 8
               + [entrada(i) for i in range(40)])
    telas = ([TELA_DOIS] * 8
             + [(TELA_COM_BICHO if fugitivo_visivel else TELA_SO_CORPO)] * 40)

    def agora():
        return min(quadro["i"], len(roteiro) - 1)

    def loop_sleep(_s):
        quadro["i"] += 1
        if quadro["i"] >= len(roteiro):
            main.STOP = True

    def clica_mapa(_w, passo):
        fita.append(("mapa", passo))
        for odo in OdoFalso.todos:        # o personagem e um, os odometros dois
            odo.pos[0] += passo[0]
            odo.pos[1] += passo[1]

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
    main.keyboard = type("K", (), {
        "is_pressed": staticmethod(lambda k: False)})()
    main.pyautogui = type("P", (), {
        "press": staticmethod(lambda t: fita.append(("tecla", t))),
        "keyDown": staticmethod(lambda t: None),
        "keyUp": staticmethod(lambda t: None)})()
    main.click_minimap = clica_mapa
    main.click_game = lambda x, y, pausa=0.09, botao="esquerdo", mod="": \
        fita.append(("clique", (x, y)))
    main.time = type("T", (), {
        "time": staticmethod(lambda: quadro["i"] * 0.3),
        "sleep": staticmethod(loop_sleep)})()
    main.load_monsters = lambda caminho=None: {"bicho": BICHO}
    main.load_waypoints = lambda caminho=None: []
    main.load_evitar = lambda caminho=None: {}
    main.ONLY_KNOWN_MONSTERS = True
    main.AUTO_LEARN = False
    main.ENABLE_WALK = False
    main.USE_MAP_MARKS = False
    main.USE_ROUTE_ORDER = False
    main.ATTACK_MODE = "kite"
    main.ENABLE_HEAL = main.ENABLE_MANA = False
    main.ENABLE_SPELL = main.ENABLE_AUTOCAST = False
    main.ENABLE_PARALISIA = False
    main.ENABLE_LOOT = True
    main.LOOT_SO_SE_ACHOU = False
    main.ATTACK_CONFIRM = 2
    main.STOP = False

    saida = io.StringIO()
    with redirect_stdout(saida):
        main.run_bot()
    log = saida.getvalue()
    return {
        "marcou": "[loot] bicho morreu" in log,
        "saqueou": "Saqueado" in log,
        "cliques": sum(1 for a in fita if a[0] == "clique"),
        "log": log,
    }


falhas = []
print("dois bichos, um morre, o outro fica na battle list:\n")
print(f"  {'fugitivo':<24} {'marcou':<7} {'saqueou':<8} cliques")

casos = (("fora da tela, solto", False, False),
         ("visivel na tela", True, False),
         ("engajado (moldura)", False, True))
for rotulo, visivel, engajado in casos:
    r = roda(visivel, engajado)
    print(f"  {rotulo:<24} {str(r['marcou']):<7} {str(r['saqueou']):<8} "
          f"{r['cliques']}")
    if not r["marcou"]:
        falhas.append(f"{rotulo}: nao marcou o corpo")
    if rotulo.startswith("fora da tela"):
        if not r["saqueou"]:
            falhas.append("fugitivo FORA DA TELA e o saque nao aconteceu: "
                          "bicho a mais de 7 SQM nao alcanca o personagem nem "
                          "esta sendo atacado, e o corpo do lado envelhece "
                          "ate vencer o prazo. Era o caso do log de cacada")
    else:
        if r["saqueou"]:
            falhas.append(f"{rotulo}: saqueou com bicho perto. Clique na tela "
                          f"durante o ataque troca chase por stand no "
                          f"cliente, e parado no corpo se apanha de graca")

print("\nVEREDITO:", "OK - fugitivo longe nao trava o saque; bicho perto trava"
      if not falhas else "FALHOU: " + "; ".join(falhas))
