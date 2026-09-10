# -*- coding: utf-8 -*-
"""Bicho declarado morto que REAPARECE: prova que a morte era falsa.

Relatado: "o monstro fica com HP mt baixo, o bot deixa de reconhecer que e pra
atacar ele ate o fim, dai clica enquanto ta em battle com ele e muda do chase
para stand no painel lateral".

Uma morte de verdade e uma falsa (a deteccao perdeu a entrada por um instante,
por exemplo o sprite ou a barra escurecendo demais no HP critico) imprimem a
MESMA linha no log - "morreu, posso trocar" - e por isso o bot.log de uma
cacada real nao da para separar as duas so lendo texto: a maioria das
"suspeitas" registradas sao mortes de verdade, o que e o esperado a cada
abate.

O sinal inequivoco e o MESMO sprite reaparecer pouco depois de uma morte ja
declarada - impossivel para uma morte de verdade. Aqui o bicho fica critico
(barra quase zerada, sprite as vezes some da leitura), a trava confirma
"morreu" por TARGET_GONE_READS leituras sem ele, e DEPOIS ele volta a
aparecer plenamente - o mesmo cenario que a suspeita de reconhecimento
descreve.
"""
import io
import os
import sys
from contextlib import redirect_stdout
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

SPRITE = np.random.default_rng(11).integers(0, 255, (17, 20, 3), dtype=np.uint8)


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


FASES = []


def fase(vezes, lista, alvo):
    for _ in range(vezes):
        FASES.append((list(lista), alvo))


fase(2, [], None)
fase(3, [SPRITE], None)
fase(6, [SPRITE], SPRITE)              # engajado, normal
# HP CRITICO: a entrada some da leitura por varias leituras seguidas - a
# deteccao perdeu a barra/sprite, mas o bicho continua vivo (e ainda esta la,
# so nao detectado). TARGET_GONE_READS(3) confirma "morreu" antes de ele
# realmente ter morrido. O sumico e mais CURTO que a folga pos-morte, que e
# justamente o caso que ela cobre: nenhum clique de rota escapa antes da
# ressurreicao confirmar o engano.
fase(main.GRACA_POS_MORTE_LEITURAS - 5, [], None)
# O BICHO CONTINUA VIVO: reaparece, com o MESMO sprite, ainda com vida baixa
fase(20, [SPRITE], SPRITE)
fase(40, [], None)                     # e a rota so retoma DEPOIS de tudo isso


def agora():
    return min(quadro["i"], len(FASES) - 1)


def battle_agora(_win):
    lista, alvo = FASES[agora()]
    return (len(lista), alvo is not None, 0.9 if alvo is not None else None,
            lista, alvo)


fita, quadro = [], {"i": 0}


def loop_sleep(_s):
    quadro["i"] += 1
    if quadro["i"] >= len(FASES):
        main.STOP = True


main.setup_windows = lambda: (Janela(), Janela())
main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
main.read_bars = lambda win: (1.0, 1.0)
main.battle_state = battle_agora
main.grab = lambda regiao: np.zeros((110, 108, 3), dtype=np.uint8)
main.viewport = lambda win: np.zeros((main.GAME_VIEW[3], main.GAME_VIEW[2], 3),
                                     dtype=np.uint8)
main.detect_creatures = lambda win, img=None: []
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
main.ENABLE_WALK = True
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
linhas = saida.getvalue().splitlines()

if os.environ.get("VERBOSO"):
    for l in linhas:
        if "[attack]" in l or "[loot]" in l:
            print("   " + l)

morreu = [i for i, l in enumerate(linhas) if "morreu, posso trocar" in l]
ressurreicao = [i for i, l in enumerate(linhas) if "RESSURREICAO" in l]
retomou = [i for i, l in enumerate(linhas) if "retomando o trajeto" in l]

print(f"o bicho some por {main.GRACA_POS_MORTE_LEITURAS - 5} leituras (HP "
      f"critico, dentro da folga de {main.GRACA_POS_MORTE_LEITURAS}) e "
      f"depois volta com o MESMO sprite\n")
print(f"mortes declaradas: {len(morreu)} (linha {morreu[:1]})")
print(f"ressurreicoes detectadas: {len(ressurreicao)} (linha "
      f"{ressurreicao[:1]})")
print(f"'retomando o trajeto': {len(retomou)} vez(es), nas linhas {retomou}")

falhas = []
if not morreu:
    falhas.append("o cenario nao chegou a declarar morte nenhuma - nao mede "
                  "nada")
if not ressurreicao:
    falhas.append(
        "o bicho reapareceu com o MESMO sprite depois de uma morte "
        "declarada, e isso nao foi detectado. Sem essa prova, uma morte "
        "falsa e uma morte de verdade sao indistinguiveis no log - e e "
        "exatamente esse caso que faz o bot tratar como morto um bicho "
        "que continua vivo e sendo atacado")
if morreu and ressurreicao:
    # NENHUM "retomando o trajeto" pode cair ENTRE a morte falsa e a prova de
    # que ela era falsa - e exatamente esse retomar, com o personagem ainda
    # lutando de verdade, que manda o clique de mapa que cancela o chase no
    # cliente.
    entre = [i for i in retomou if morreu[0] < i < ressurreicao[0]]
    if entre:
        falhas.append(
            f"'retomando o trajeto' saiu na(s) linha(s) {entre}, ENTRE a "
            f"morte falsa (linha {morreu[0]}) e a ressurreicao que provou o "
            f"engano (linha {ressurreicao[0]}). Isso e a rota clicando no "
            f"mapa com o bicho ainda vivo e sendo atacado - o clique que "
            f"cancela o chase no cliente")

print("\nVEREDITO:", "OK - a folga segura a rota ate a ressurreicao provar o "
      "engano" if not falhas else "FALHOU: " + "; ".join(falhas))
