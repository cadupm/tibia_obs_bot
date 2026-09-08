# -*- coding: utf-8 -*-
"""Trocar as teclas das diagonais nao pode derrubar o bot.

Erro visto em jogo: com KITE_DIAGONAIS_TECLAS mudado para "q,e,z,c" na GUI, a
decisao passou a devolver as teclas novas, mas tres lugares continuavam
consultando a tabela montada no import (com o teclado numerico) - KeyError: 'q',
e o bot morria no meio da cacada, que e o pior lugar para parar.

Aqui se percorre o caminho inteiro com teclas trocadas, incluindo a parte que
estourava: registrar parede depois de um passo que nao andou.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

falhas = []


class Janela:
    isActive = True
    title = "falso"


class OdoParado:
    """Nunca sai do lugar: e assim que se chega no caminho da parede."""

    def __init__(self):
        self.pos = [0, 0]
        self.parado = 9

    def atualiza(self):
        pass


class SemEspera:
    def ready(self):
        return True

    def mark(self):
        pass


def viewport_com_bicho(dx, dy):
    _vx, _vy, vw, vh = main.GAME_VIEW
    img = np.full((vh, vw, 3), 30, dtype=np.uint8)
    meio_col, meio_lin = (vw // main.TILE_PX) // 2, (vh // main.TILE_PX) // 2
    x = (meio_col + dx) * main.TILE_PX + 18
    y = (meio_lin + dy - main.CREATURE_BAR_ABOVE) * main.TILE_PX + 10
    img[y:y + 4, x:x + 31] = (0, 0, 0)
    img[y + 1:y + 3, x + 1:x + 30] = (0, 95, 0)
    return img


apertadas = []
main.client_rect = lambda win: (0, 0, 1920, 1009)
main.focus_window = lambda win: True
main.pyautogui = type("P", (), {
    "press": staticmethod(lambda t: apertadas.append(t))})()
main.click_minimap = lambda win, passo: apertadas.append(("clique", passo))
relogio = {"t": 0.0}
main.time = type("T", (), {"time": staticmethod(lambda: relogio["t"]),
                           "sleep": staticmethod(lambda s: None)})()

for teclas in ("num7,num9,num1,num3", "q,e,z,c", "home,pageup,end,pagedown",
               ""):
    main.KITE_DIAGONAIS_TECLAS = teclas
    main.KITE_DIAGONAIS = bool(teclas)
    main.atualiza_passos()
    diagonais = [t for t, r in main.KITE_PASSOS.items() if 0 not in r]
    print(f"\nteclas configuradas: {teclas or '(nenhuma)'}")
    print(f"  diagonais montadas: {diagonais}")

    # bicho colado a esquerda e nada anda: o bot tem de tentar, concluir parede
    # e seguir tentando outros lados, SEM estourar
    main.grab = lambda regiao, _t=viewport_com_bicho(-1, 0): _t
    odo, estado = OdoParado(), {}
    apertadas.clear()
    try:
        for _ in range(12):
            relogio["t"] += 0.4
            main.kite(Janela(), Janela(), SemEspera(), {}, odo=odo,
                      estado=estado)
    except Exception as erro:
        falhas.append(f"{teclas or '(nenhuma)'}: {type(erro).__name__}: {erro}")
        print(f"  ESTOUROU: {type(erro).__name__}: {erro}")
        continue
    usadas = sorted(set(t for t in apertadas if isinstance(t, str)))
    print(f"  teclas apertadas: {usadas}")
    print(f"  lados dados por parede: {sorted(estado.get('bloqueados', {}))}")
    fora = [t for t in usadas if t not in main.KITE_PASSOS]
    if fora:
        falhas.append(f"{teclas}: apertou tecla fora da configuracao: {fora}")

print("\nVEREDITO:", "OK - troca de teclas nao derruba nem sai da configuracao"
      if not falhas else "FALHOU: " + "; ".join(falhas))
