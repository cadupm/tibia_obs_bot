# -*- coding: utf-8 -*-
"""O kite acontece no laco do bot, e mesmo com o ANDAR DESLIGADO.

Kite e comportamento de combate, nao de rota: quem liga o bot so para lutar
tambem quer kite. Este teste roda o laco de verdade com ENABLE_WALK desligado,
uma criatura colada no personagem, e confere que saem passos de fuga.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

BICHO = np.full((17, 20, 3), 40, dtype=np.uint8)
BICHO[3:8, 3:8] = (200, 30, 30)

VAZIA = (0, False, None, [], None)
ENGAJADO = (1, True, 0.9, [BICHO], BICHO)

NA_LISTA = (1, False, None, [BICHO], None)      # na lista, ainda sem moldura

ROTEIRO = ([VAZIA] * 2 + [NA_LISTA] * 4          # aparece: tem de atacar
           + [ENGAJADO] * 12                     # engajado: tem de kitar
           + [VAZIA] * 4)

fita = []
quadro = {"i": 0}


class Janela:
    _hWnd = 1
    title = "falso"
    isActive = True
    isMinimized = False
    left = top = 0
    width = height = 100


def viewport_com_bicho():
    """Uma tela de jogo de mentira: barrinha de vida no quadrado a esquerda."""
    _vx, _vy, vw, vh = main.GAME_VIEW
    img = np.full((vh, vw, 3), 30, dtype=np.uint8)
    meio_col, meio_lin = (vw // main.TILE_PX) // 2, (vh // main.TILE_PX) // 2
    x = (meio_col - 1) * main.TILE_PX + 20        # coluna a esquerda do meio
    # a barra e desenhada no quadrado ACIMA da criatura - medido nas duas barras
    # da captura de verdade, e o que o CREATURE_BAR_ABOVE desconta
    y = (meio_lin - main.CREATURE_BAR_ABOVE) * main.TILE_PX + 10
    img[y:y + 2, x:x + 28] = (0, 95, 0)           # medido no jogo: 28x2 (0,95,0)
    return img


TELA = viewport_com_bicho()


def battle_state(_win):
    return ROTEIRO[min(quadro["i"], len(ROTEIRO) - 1)]


def press(tecla):
    fita.append((quadro["i"], tecla))


def loop_sleep(_s):
    quadro["i"] += 1
    if quadro["i"] > len(ROTEIRO):
        main.STOP = True


main.setup_windows = lambda: (Janela(), Janela())
main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
main.read_bars = lambda win: (1.0, 1.0)
main.battle_state = battle_state
main.grab = lambda regiao: TELA
main.client_rect = lambda win: (0, 0, 1920, 1009)
main.is_usable = lambda win: True
main.focus_window = lambda win: True
main.restore_windows = lambda: None
main.keyboard = type("K", (), {"is_pressed": staticmethod(lambda k: False)})()
main.pyautogui = type("P", (), {"press": staticmethod(press)})()
main.time = type("T", (), {"time": staticmethod(lambda: quadro["i"] * 0.2),
                           "sleep": staticmethod(loop_sleep)})()
main.load_monsters = lambda caminho=None: {"bicho": BICHO}
main.load_waypoints = lambda caminho=None: []
main.ONLY_KNOWN_MONSTERS = True
main.AUTO_LEARN = False
main.ENABLE_WALK = False                  # <- o ponto do teste
main.ATTACK_MODE = "kite"
main.ENABLE_HEAL = main.ENABLE_MANA = False
main.ENABLE_SPELL = main.ENABLE_AUTOCAST = False
main.ATTACK_CONFIRM = 2
main.KITE_COOLDOWN = 0.0
main.STOP = False

main.run_bot()

print("\ncriatura de mentira: 1 SQM a esquerda do personagem")
print(f"KITE_DIST = {main.KITE_DIST} SQM, andar desligado\n")
for i, tecla in fita:
    print(f"  quadro {i:>2}: tecla {tecla}")

fugas = [t for _i, t in fita if t in main.KITE_PASSOS]
ataques = [t for _i, t in fita if t == main.ATTACK_HOTKEY]
paradas = [t for _i, t in fita if t == main.STOP_WALK_KEY]

falhas = []
if not fugas:
    falhas.append("nao deu nenhum passo de fuga")
if not ataques:
    falhas.append("nao atacou")
if paradas:
    falhas.append(f"mandou a tecla de parada ({paradas}) - em kite quem manda "
                  f"no movimento sao as setas")
if fugas and set(fugas) != {"right"}:
    falhas.append(f"fugiu para {set(fugas)}; com bicho a esquerda e right")

print(f"\npassos de fuga: {fugas}")
print(f"ataques: {len(ataques)} | teclas de parada: {len(paradas)}")
print("VEREDITO:", "OK - kita com o andar desligado" if not falhas
      else "FALHOU: " + "; ".join(falhas))
