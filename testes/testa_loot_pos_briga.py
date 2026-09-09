# -*- coding: utf-8 -*-
"""Acabou a battle list: TODOS os corpos que ficaram sao saqueados.

Pedido depois de uma cacada: "ele ataca antes de lootear, ai perde o tracking;
temos que garantir que quando acabar os monstros da battle list vamos lootear
todos que ja morreram e nao foram looteados".

O cliente engaja o proximo bicho sozinho, e contra isso o bot nao tem gesto: a
moldura passa e a briga continua. Entao o saque na hora da morte e bom quando
da, e nao pode ser a unica chance. A garantia e a outra ponta: com a lista
vazia, a fila de corpos e drenada ate o fim, e so depois a rota volta a andar.

Duas coisas quebravam essa garantia e as duas estao aqui:

  1. A FILA TINHA TETO BAIXO (LOOT_MAX_CORPOS = 4) e descartava os MAIS VELHOS
     em silencio. Cinco bichos numa briga - normal numa caverna - e o primeiro
     a morrer some da fila sem nunca ter sido clicado.
  2. A VALIDADE CONTAVA NO RELOGIO DE PAREDE desde a morte. Uma briga longa
     vence o prazo dos primeiros corpos enquanto ela ainda esta acontecendo, e
     ao terminar o bot larga o que nunca teve chance de buscar.

O mundo e fisico: clicar num corpo manda o cliente andar ate ele, um quadrado
por leitura, e a briga cancela a caminhada.
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
CHAO = np.random.default_rng(37).integers(40, 70, (VH, VW, 3), dtype=np.uint8)

# cinco bichos, cada um morrendo no proprio quadrado - dois deles longe
NOMES = ["A", "B", "C", "D", "E"]
MORRE_EM = {"A": (4, 0), "B": (1, 1), "C": (-1, 0), "D": (0, -3), "E": (1, 0)}
SPRITES = {n: np.random.default_rng(200 + i).integers(
    0, 255, (17, 20, 3), dtype=np.uint8) for i, n in enumerate(NOMES)}
for i, a in enumerate(NOMES):
    for b in NOMES[i + 1:]:
        assert not main.sprite_igual(SPRITES[a], SPRITES[b]), \
            "os sprites do teste tem de ser distinguiveis"


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


MUNDO = {"ch": [0, 0], "indo": None}


class OdoFalso:
    def __init__(self, _win=None):
        self.parado = 9

    @property
    def pos(self):
        return [MUNDO["ch"][0] * main.MINIMAP_PX_SQM,
                MUNDO["ch"][1] * main.MINIMAP_PX_SQM]

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


def fase(vezes, vivos, corpos, lista, alvo):
    for _ in range(vezes):
        FASES.append((list(vivos), list(corpos), list(lista), alvo))


fase(2, [], [], [], None)
fase(2, NOMES, [], NOMES, None)                 # os cinco aparecem
# UMA BRIGA LONGA, com o cliente passando a moldura para o proximo sozinho.
# Eles morrem um a um e a lista so esvazia no fim.
vivos, corpos = list(NOMES), []
fase(10, vivos, corpos, vivos, vivos[0])
for morto in NOMES:
    vivos = [n for n in vivos if n != morto]
    corpos.append(MORRE_EM[morto])
    fase(14, vivos, corpos, vivos, vivos[0] if vivos else None)
fase(120, [], corpos, [], None)                 # lista VAZIA: hora de recolher


def tela_agora():
    vivos, corpos, _lista, _alvo = FASES[agora()]
    ch = MUNDO["ch"]
    img = CHAO.copy()
    for onde in corpos:
        desenha(img, (onde[0] - ch[0], onde[1] - ch[1]), (95, 75, 55))
    for nome in vivos:
        onde = MORRE_EM[nome]
        off = (onde[0] - ch[0], onde[1] - ch[1])
        desenha(img, off, (170, 40, 40))
        barra(img, off)
    return img


fita, quadro = [], {"i": 0}


def agora():
    return min(quadro["i"], len(FASES) - 1)


def battle_agora(_win):
    _vivos, _corpos, lista, alvo = FASES[agora()]
    return (len(lista), alvo is not None, 0.9 if alvo else None,
            [SPRITES[n] for n in lista],
            SPRITES[alvo] if alvo else None)


def loop_sleep(_s):
    quadro["i"] += 1
    if FASES[min(quadro["i"], len(FASES) - 1)][0]:
        MUNDO["indo"] = None               # briga cancela a caminhada
    indo = MUNDO["indo"]
    if indo is not None:
        falta = (indo[0] - MUNDO["ch"][0], indo[1] - MUNDO["ch"][1])
        if max(abs(falta[0]), abs(falta[1])) <= 1:
            MUNDO["indo"] = None
        else:
            MUNDO["ch"][0] += (falta[0] > 0) - (falta[0] < 0)
            MUNDO["ch"][1] += (falta[1] > 0) - (falta[1] < 0)
    if quadro["i"] >= len(FASES):
        main.STOP = True


def clica_jogo(x, y, pausa=0.09, botao="esquerdo", mod=""):
    fita.append((agora(), botao, (x, y)))
    alvo = (round((x - _vx) / main.TILE_PX - 0.5) - MEIO_COL,
            round((y - _vy) / main.TILE_PX - 0.5) - MEIO_LIN)
    MUNDO["indo"] = [MUNDO["ch"][0] + alvo[0], MUNDO["ch"][1] + alvo[1]]


def aperta(t):
    fita.append((agora(), "tecla", t))
    if t == main.STOP_WALK_KEY:
        MUNDO["indo"] = None


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
    "press": staticmethod(aperta),
    "keyDown": staticmethod(lambda t: None),
    "keyUp": staticmethod(lambda t: None)})()
main.click_minimap = lambda w, p: fita.append((agora(), "mapa", p))
main.click_game = clica_jogo
main.time = type("T", (), {"time": staticmethod(lambda: quadro["i"] * 0.3),
                           "sleep": staticmethod(loop_sleep)})()
main.load_monsters = lambda caminho=None: dict(SPRITES)
main.load_loot_flags = lambda caminho=None: {n: True for n in NOMES}
main.load_waypoints = lambda caminho=None: []
main.load_evitar = lambda caminho=None: {}
main.ONLY_KNOWN_MONSTERS = True
main.AUTO_LEARN = False
main.ENABLE_WALK = True
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
linhas = log.splitlines()

if os.environ.get("VERBOSO"):
    for l in linhas:
        if "[loot]" in l or "[walk]" in l:
            print("   " + l)

marcados = [l for l in linhas if "bicho morreu a" in l]
saqueados = [l for l in linhas if "Saqueado" in l]
perdidos = [l for l in linhas if "ficou para tras na rota" in l
            or "largo ele" in l or "; sigo" in l]
cliques = [f for f in fita if f[1] == main.LOOT_BOTAO]

print(f"{len(NOMES)} bichos morrem numa briga so, em {list(MORRE_EM.values())}")
print(f"teto da fila: LOOT_MAX_CORPOS = {main.LOOT_MAX_CORPOS}\n")
print(f"mortes registradas: {len(marcados)} de {len(NOMES)}")
print(f"corpos saqueados:   {len(saqueados)}")
for l in saqueados:
    print("   " + l.strip())
if perdidos:
    print(f"\ncorpos perdidos: {len(perdidos)}")
    for l in perdidos:
        print("   " + l.strip())
print(f"\ncliques de saque: {len(cliques)}")

falhas = []
if len(marcados) < len(NOMES):
    falhas.append(f"{len(marcados)} morte(s) registrada(s) de {len(NOMES)}: "
                  f"corpo que nao entra na fila nunca vai ser saqueado")
if len(saqueados) < len(NOMES):
    falhas.append(
        f"saqueou {len(saqueados)} de {len(NOMES)}. Acabada a battle list, "
        f"TODOS os que morreram e nao foram saqueados tem de ser recolhidos - "
        f"e o teto da fila e a validade contada no relogio de parede sao os "
        f"dois jeitos de perder corpo em silencio")
if perdidos:
    falhas.append(f"largou {len(perdidos)} corpo(s) sem saquear: {perdidos}")

print("\nVEREDITO:", "OK - acabada a lista, todos os corpos sao recolhidos"
      if not falhas else "FALHOU: " + "; ".join(falhas))
