# -*- coding: utf-8 -*-
"""Bicho que fica na battle list sem aparecer nao pode parar a rota para sempre.

Relatado em cacada, com o bot congelado:

    [attack] space (1 atacavel(is) na lista, sem alvo)
    [loot] 1 na battle list, mas nenhum bicho na tela e nenhum engajado: dou o
           saque por liberado
    "travado, nao le mais a rota depois desse log"

A entrada na battle list nao sai enquanto o bicho estiver vivo, e ele pode
estar fora da tela para sempre - fugiu, ficou preso atras de parede, esta noutro
andar. A regra da rota era "so ando com a lista LIMPA", e limpa ela nunca
ficava: o bot parava de andar e nao voltava mais.

O saque ja tinha essa mesma trava e ja tinha sido consertado pelo mesmo motivo
("bicho fora da tela nao alcanca o personagem e nao esta sendo atacado"). A
rota ficou de fora.

HONESTIDADE SOBRE O QUE ESTE TESTE MEDE: o codigo anterior tambem passa nele,
porque neste cenario a entrada nunca engaja e o bot acaba concluindo "NPC ou
player? paro de apertar" - e ai ele deixa de se considerar lutando e a rota
volta por esse outro caminho. Entao este arquivo nao e a reproducao de um
defeito: e uma GUARDA da propriedade "nada perto por muitas leituras seguidas
sempre solta a rota", que agora vale mesmo quando a lista nao esvazia. Sem ela,
qualquer mudanca futura em como "lutando" e calculado pode congelar o trajeto
de novo sem que nada caia.
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
CHAO = np.random.default_rng(13).integers(40, 70, (VH, VW, 3), dtype=np.uint8)
SPRITE = np.random.default_rng(3).integers(0, 255, (17, 20, 3), dtype=np.uint8)


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


fita, quadro = [], {"i": 0}
LEITURAS = 120


def loop_sleep(_s):
    quadro["i"] += 1
    if quadro["i"] >= LEITURAS:
        main.STOP = True


# UMA entrada na battle list o tempo todo, e NADA na tela: o bicho existe, esta
# vivo, e o bot nunca vai alcanca-lo. Sem alvo engajado - ele nao responde ao
# ataque, que e o que acontece com bicho fora de alcance.
main.setup_windows = lambda: (Janela(), Janela())
main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
main.read_bars = lambda win: (1.0, 1.0)
main.battle_state = lambda win: (1, False, None, [SPRITE], None)
main.grab = lambda regiao: CHAO.copy()
main.detect_creatures = lambda win, img=None: []      # nada na tela
main.acha_moldura_do_alvo = lambda img: None
main.Odometro = OdoFalso
main.client_rect = lambda win: (0, 0, 1920, 1009)
main.detect_marks = lambda win, mm=None, cor=None: []
main.is_usable = lambda win: True
main.focus_window = lambda win: True
main.restore_windows = lambda: None
main.quem_tapa = lambda leitura, teclado=None, minimo=0.01: []
main.confere_a_grade = lambda leitura: None
main.le_maximos = lambda leitura: 0
main.keyboard = type("K", (), {"is_pressed": staticmethod(lambda k: False)})()
main.pyautogui = type("P", (), {
    "press": staticmethod(lambda t: fita.append((quadro["i"], "tecla", t))),
    "keyDown": staticmethod(lambda t: None),
    "keyUp": staticmethod(lambda t: None)})()
main.click_minimap = lambda w, p: fita.append((quadro["i"], "mapa", p))
main.click_game = lambda x, y, pausa=0.09, botao="esquerdo", mod="": \
    fita.append((quadro["i"], botao, (x, y)))
main.time = type("T", (), {"time": staticmethod(lambda: quadro["i"] * 0.3),
                           "sleep": staticmethod(loop_sleep)})()
main.load_monsters = lambda caminho=None: {"bicho": SPRITE}
main.load_loot_flags = lambda caminho=None: {"bicho": True}
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
main.STOP = False

saida = io.StringIO()
with redirect_stdout(saida):
    main.run_bot()
linhas = saida.getvalue().splitlines()

if os.environ.get("VERBOSO"):
    for l in linhas:
        if "[walk]" in l or "[loot]" in l or "[attack]" in l:
            print("   " + l)

voltou = [l for l in linhas if "volto a andar a rota" in l
          or "retomando o trajeto" in l]
parou = [l for l in linhas if "lutando primeiro" in l
         or "paro de clicar" in l]

print(f"1 entrada na battle list o tempo todo, nada na tela, "
      f"{LEITURAS} leituras")
print(f"WALK_RESUME_READS = {main.WALK_RESUME_READS}\n")
print(f"parou para lutar: {len(parou)}")
for l in parou[:2]:
    print("   " + l.strip())
print(f"voltou a andar: {len(voltou)}")
for l in voltou[:2]:
    print("   " + l.strip())

falhas = []
if not parou:
    falhas.append("nem chegou a parar para lutar: o cenario nao mede nada")
if not voltou:
    falhas.append(
        f"a rota nunca voltou em {LEITURAS} leituras. A entrada na battle list "
        f"nao sai enquanto o bicho estiver vivo, e ele pode estar fora da tela "
        f"para sempre - com a regra so de 'lista limpa' o bot para de andar e "
        f"nao volta mais")

print("\nVEREDITO:", "OK - bicho que nao aparece nao trava a rota"
      if not falhas else "FALHOU: " + "; ".join(falhas))
