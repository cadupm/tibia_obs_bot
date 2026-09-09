# -*- coding: utf-8 -*-
"""O corpo fica onde o bicho MORREU, e nao onde ele foi engajado.

A morte so e confirmada TARGET_GONE_READS leituras depois de a entrada sumir da
battle list, e a leitura de referencia - aquela em que o bicho ainda aparecia -
era escolhida por um NUMERO FIXO de leituras atras:

    historico[-(TARGET_GONE_READS + 1)]

Com bicho SOBREVIVENTE na lista, o historico continua enchendo depois da morte e
esse chute caia no lugar certo por coincidencia. Com UM BICHO SO ele para de
crescer quando a lista esvazia, e o chute caia QUATRO leituras antes da morte -
0.6s mais o debounce. Tempo de sobra para o bicho andar, e o bot ia buscar o
corpo onde ele estava quando foi ENGAJADO.

Agora a referencia e achada pela CONTAGEM de entradas: a ultima leitura com MAIS
entradas do que agora e, por definicao, a ultima em que o bicho que morreu ainda
constava. Sem chute.

Aqui o bicho ANDA de (4,0) ate (1,0) enquanto e atacado e morre em (1,0). O
teste exige que o corpo saia em (1,0) - onde ele morreu - e nao em (4,0), onde
foi engajado.
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
CHAO = np.random.default_rng(41).integers(40, 70, (VH, VW, 3), dtype=np.uint8)

BICHO = np.full((17, 20, 3), 40, dtype=np.uint8)
BICHO[3:8, 3:8] = (200, 30, 30)

# o caminho do bicho: engajado longe, chega colado, morre ali
ANDOU = [(4, 0), (3, 0), (2, 0), (1, 0)]
MORREU_EM = ANDOU[-1]


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


def tela_vivo(off):
    """Bicho de pe no quadrado, com barra de vida."""
    return barra(desenha(CHAO.copy(), off, (170, 40, 40)), off)


def tela_morto(off):
    """Corpo no quadrado: sprite de cadaver, SEM barra e SEM nome."""
    return desenha(CHAO.copy(), off, (95, 75, 55))


class Janela:
    isActive = True
    title = "falso"
    isMinimized = False


class OdoFalso:
    """Personagem parado: so o bicho anda, para o teste medir uma coisa so."""

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


def roda(sobrevivente):
    """
    O bicho anda de (4,0) a (1,0), e atacado e morre. Devolve o que o bot achou.

    `sobrevivente` diz se sobra outro bicho na battle list - e o que faz o
    historico continuar enchendo depois da morte, que era o caso em que o chute
    antigo funcionava por coincidencia.
    """
    fita, quadro = [], {"i": 0}
    extra = 1 if sobrevivente else 0
    # 2 leituras vazias, o bicho aparece e anda um quadrado por leitura,
    # engajado; depois some da lista e o resto e cave
    roteiro = [(0 + extra, False, None, [BICHO] * extra, None)] * 2
    telas = [CHAO.copy()] * 2
    for i, off in enumerate(ANDOU):
        engajado = i > 0
        roteiro.append((1 + extra, engajado, 0.9 if engajado else None,
                        [BICHO] * (1 + extra), BICHO if engajado else None))
        telas.append(tela_vivo(off))
    for _ in range(30):
        roteiro.append((0 + extra, False, None, [BICHO] * extra, None))
        telas.append(tela_morto(MORREU_EM))

    def agora():
        return min(quadro["i"], len(roteiro) - 1)

    def loop_sleep(_s):
        quadro["i"] += 1
        if quadro["i"] >= len(roteiro):
            main.STOP = True

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
    main.click_minimap = lambda w, p: fita.append(("mapa", p))
    main.click_game = lambda x, y, pausa=0.09, botao="esquerdo", mod="": \
        fita.append(("clique", (x, y)))
    main.time = type("T", (), {
        "time": staticmethod(lambda: quadro["i"] * 0.3),
        "sleep": staticmethod(loop_sleep)})()
    main.load_monsters = lambda caminho=None: {"bicho": BICHO}
    main.load_loot_flags = lambda caminho=None: {"bicho": True}
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
    main.LOOT_SO_MARCADOS = False
    main.LOOT_SO_SE_ACHOU = False
    main.ATTACK_CONFIRM = 2
    main.STOP = False

    saida = io.StringIO()
    with redirect_stdout(saida):
        main.run_bot()
    log = saida.getvalue()
    # o quadrado que o bot marcou, tirado do proprio log
    marcado = None
    for linha in log.splitlines():
        if "a barra de vida sumiu em [(" in linha:
            miolo = linha.split("sumiu em [(")[1].split(")")[0]
            x, y = (int(v) for v in miolo.split(","))
            marcado = (x, y)
            break
    return {"marcado": marcado, "log": log,
            "cliques": [a[1] for a in fita if a[0] == "clique"]}


falhas = []
print(f"o bicho anda {ANDOU[0]} -> {ANDOU[-1]} e morre em {MORREU_EM}\n")
print(f"  {'sobrevivente':<14} {'corpo marcado':<15} onde foi ENGAJADO")
for sobrevivente in (False, True):
    r = roda(sobrevivente)
    print(f"  {str(sobrevivente):<14} {str(r['marcado']):<15} {ANDOU[0]}")
    if r["marcado"] != MORREU_EM:
        falhas.append(
            f"sobrevivente={sobrevivente}: marcou {r['marcado']}, esperava "
            f"{MORREU_EM} (onde ele MORREU). {ANDOU[0]} e onde ele foi "
            f"ENGAJADO - se saiu isso, a leitura de referencia esta velha")
    if not r["cliques"]:
        falhas.append(f"sobrevivente={sobrevivente}: nao clicou em corpo nenhum")

# o quadrado do engajamento nao pode aparecer como corpo em nenhum momento
todos_logs = "".join(roda(s)["log"] for s in (False, True))
if f"sumiu em [{ANDOU[0]}" in todos_logs:
    falhas.append(f"o log aponta corpo em {ANDOU[0]}, que e onde o bicho foi "
                  f"engajado e nao onde morreu")

print("\nVEREDITO:", "OK - o corpo sai onde ele morreu, nao onde foi engajado"
      if not falhas else "FALHOU: " + "; ".join(falhas))
