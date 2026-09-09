# -*- coding: utf-8 -*-
"""Corpo que nao se resolve nao pode segurar a rota para sempre.

Relatado em cacada: "algo aconteceu que o andar da rota ta sendo prejudicado
pelo loot; a battle list mesmo vazia apresentou 2 bichos para serem looteados
que nao foram, nao deve travar o flow".

O bot.log mostrou o ciclo: o corpo esta longe, o bot clica, o cliente comeca a
andar, um bicho aparece, a briga cancela a caminhada, e na proxima folga ele
clica de novo. Enquanto isso loot() devolve True - e loot() devolvendo True e o
que faz a rota esperar.

Os dois prazos que deviam cortar isso somavam tempo entre leituras CONSECUTIVAS
naquele corpo (para que uma briga no meio nao custasse o corpo). Numa caverna
movimentada as leituras nunca sao consecutivas, entao nenhuma conta avanca e o
corpo fica imortal: o efeito foi o oposto do pretendido.

O mundo aqui e o pior caso honesto: o personagem NAO ANDA (o corpo esta atras
de uma parede, digamos), e bicho aparece de vez em quando cortando o tempo. O
exigido e que o bot desista - por tentativas ou pelo relogio - e volte a andar
a rota.
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
CHAO = np.random.default_rng(91).integers(40, 70, (VH, VW, 3), dtype=np.uint8)
SPRITE = np.random.default_rng(7).integers(0, 255, (17, 20, 3), dtype=np.uint8)

MORRE_EM = (4, -2)          # longe: exige caminhada que nunca acontece


def desenha(img, off, cor, tamanho=44):
    x0 = (MEIO_COL + off[0]) * main.TILE_PX + (main.TILE_PX - tamanho) // 2
    y0 = (MEIO_LIN + off[1]) * main.TILE_PX + (main.TILE_PX - tamanho) // 2
    if 0 <= y0 < VH - tamanho and 0 <= x0 < VW - tamanho:
        img[y0:y0 + tamanho, x0:x0 + tamanho] = cor
    return img


def barra(img, off):
    x = (MEIO_COL + off[0]) * main.TILE_PX + 18
    y = (MEIO_LIN + off[1] - main.CREATURE_BAR_ABOVE) * main.TILE_PX + 10
    if 0 <= y < VH - 4 and 0 <= x < VW - 31:
        img[y:y + 4, x:x + 31] = (0, 0, 0)
        img[y + 1:y + 3, x + 1:x + 30] = (0, 95, 0)
    return img


class Janela:
    isActive = True
    title = "falso"
    isMinimized = False


class OdoFalso:
    """O PERSONAGEM NAO ANDA. E o pior caso: o clique no corpo nao aproxima."""

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


# ---------------------------------------------------------------- roteiro
FASES = []


def fase(vezes, vivo, corpos, lista):
    for _ in range(vezes):
        FASES.append((vivo, list(corpos), lista))


# DOIS bichos na lista desde o comeco: o que vai morrer longe, e um segundo que
# NUNCA morre. O segundo e o que corta o tempo - ele aparece e some da TELA sem
# sair da battle list, que e o padrao que o bot.log mostrou: "N na battle list,
# mas nenhum bicho na tela e nenhum engajado: dou o saque por liberado",
# alternando com leituras em que ele aparece e o bot volta a lutar.
fase(2, None, [], 0)
fase(2, MORRE_EM, [], 2)
fase(6, MORRE_EM, [], 2)                       # engajado ate morrer
for _ in range(30):
    fase(6, None, [MORRE_EM], 1)               # folga: o bot tenta o corpo
    fase(4, (1, 1), [MORRE_EM], 1)             # o outro aparece: o bot larga
# no fim o segundo bicho vai embora e a lista esvazia: e aqui que a rota TEM de
# voltar a andar. Com corpo pendente na fila ela nao volta, porque loot()
# devolvendo True segura o trajeto - e era esse o travamento relatado.
fase(40, None, [MORRE_EM], 0)


def tela_agora():
    vivo, corpos, _l = FASES[agora()]
    img = CHAO.copy()
    for onde in corpos:
        desenha(img, onde, (95, 75, 55))
    if vivo is not None:
        desenha(img, vivo, (170, 40, 40))
        barra(img, vivo)
    return img


fita, quadro = [], {"i": 0}


def agora():
    return min(quadro["i"], len(FASES) - 1)


def battle_agora(_win):
    vivo, _c, lista = FASES[agora()]
    engajado = vivo is not None
    return (lista, engajado, 0.9 if engajado else None,
            [SPRITE] * lista, SPRITE if engajado else None)


def loop_sleep(_s):
    quadro["i"] += 1
    if quadro["i"] >= len(FASES):
        main.STOP = True


main.setup_windows = lambda: (Janela(), Janela())
main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
main.read_bars = lambda win: (1.0, 1.0)
main.battle_state = battle_agora
main.grab = lambda regiao: tela_agora()
main.Odometro = OdoFalso
main.client_rect = lambda win: (0, 0, 1920, 1009)
main.detect_marks = lambda win, mm=None, cor=None: []
main.is_usable = lambda win: True
main.focus_window = lambda win: True
main.restore_windows = lambda: None
main.keyboard = type("K", (), {"is_pressed": staticmethod(lambda k: False)})()
main.pyautogui = type("P", (), {
    "press": staticmethod(lambda t: fita.append((agora(), "tecla", t))),
    "keyDown": staticmethod(lambda t: None),
    "keyUp": staticmethod(lambda t: None)})()
main.click_minimap = lambda w, p: fita.append((agora(), "mapa", p))
main.click_game = lambda x, y, pausa=0.09, botao="esquerdo", mod="": \
    fita.append((agora(), botao, (x, y)))
main.time = type("T", (), {"time": staticmethod(lambda: quadro["i"] * 0.3),
                           "sleep": staticmethod(loop_sleep)})()
main.load_monsters = lambda caminho=None: {"bicho": SPRITE}
main.load_loot_flags = lambda caminho=None: {"bicho": True}
main.load_waypoints = lambda caminho=None: []
main.load_evitar = lambda caminho=None: {}
main.ONLY_KNOWN_MONSTERS = True
main.AUTO_LEARN = False
main.ENABLE_WALK = True            # a rota tem de voltar a andar
main.USE_MAP_MARKS = False
main.USE_ROUTE_ORDER = False
main.ATTACK_MODE = "stand"
main.ENABLE_HEAL = main.ENABLE_MANA = False
main.ENABLE_SPELL = main.ENABLE_AUTOCAST = False
main.ENABLE_PARALISIA = False
main.ENABLE_LOOT = True
main.LOOT_SO_MARCADOS = False
main.ATTACK_CONFIRM = 2
main.STOP = False

saida = io.StringIO()
with redirect_stdout(saida):
    main.run_bot()
log = saida.getvalue()
linhas = log.splitlines()

if os.environ.get("VERBOSO"):
    for l in linhas:
        if "[loot]" in l or "[walk]" in l:
            print("   " + l)

# so os cliques NAQUELE corpo: no fim do roteiro o segundo bicho sai da battle
# list, o que e uma morte como outra qualquer, e o corpo dele tambem e clicado
ponto_do_corpo = main.ponto_do_quadrado(Janela(), MORRE_EM)
cliques = [f for f in fita
           if f[1] == main.LOOT_BOTAO and f[2] == ponto_do_corpo]
largou = [l for l in linhas if "largo ele" in l or "ficou para tras" in l]
retomou = [l for l in linhas if "retomando o trajeto" in l]
tempo = len(FASES) * 0.3

print(f"o corpo fica em {MORRE_EM} e o personagem NAO anda; briga cortando o "
      f"tempo o tempo todo")
print(f"duracao do roteiro: {tempo:.0f}s   (LOOT_VALIDADE="
      f"{main.LOOT_VALIDADE:.0f}s, LOOT_APROXIMACOES={main.LOOT_APROXIMACOES})\n")
print(f"cliques no corpo de {MORRE_EM}: {len(cliques)}")
print(f"desistiu? {bool(largou)}")
for l in largou:
    print("   " + l.strip())
print(f"a rota voltou a andar? {bool(retomou)}")

falhas = []
if not largou:
    falhas.append(
        f"o bot nunca largou o corpo em {len(FASES)} leituras ({tempo:.0f}s): "
        f"enquanto ele nao larga, loot() devolve True e a rota fica parada "
        f"atras de um corpo que ele nao consegue alcancar")
if len(cliques) > main.LOOT_APROXIMACOES:
    falhas.append(f"{len(cliques)} cliques no mesmo corpo, o limite e "
                  f"{main.LOOT_APROXIMACOES}: cada aproximacao nova conta uma, e "
                  f"depois disso e teimosia")
if not retomou:
    falhas.append("a rota nunca foi retomada: largar o corpo so serve se o "
                  "trajeto voltar a andar depois")

print("\nVEREDITO:", "OK - desiste do corpo inalcancavel e volta a andar"
      if not falhas else "FALHOU: " + "; ".join(falhas))
