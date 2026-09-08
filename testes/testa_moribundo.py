# -*- coding: utf-8 -*-
"""Bicho quase morto: a barrinha dele encurta ate quase nada.

Pega a amostra real da battle list com alvo engajado e vai encurtando a barra de
vida, como acontece quando o bicho esta morrendo. O bot tem de continuar vendo a
entrada e continuar sabendo que TEM alvo - se ele perder isso, aperta a tecla de
ataque de novo e troca de bicho com o outro quase morto.
"""
import sys
import numpy as np
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

SP = AQUI

amostra = np.load(SP + "battle_target.png.npy")
altura, largura = amostra.shape[:2]


def encurta(img, quanto):
    """Corta a barra de vida de cada entrada para `quanto` pixels."""
    img = img.copy().astype(np.int16)
    brilho = img.max(axis=2)
    cheio = (brilho - img.min(axis=2)) > main.MIN_SAT
    barra = cheio & (brilho > main.BATTLE_BAR_MIN_BRIGHT)
    fundo = np.array([44, 44, 44], dtype=np.int16)    # cinza do painel
    for y in range(barra.shape[0]):
        for ini, fim in main._runs(barra[y]):
            if fim - ini + 1 >= 20:          # so as barras de vida, largas
                img[y, ini + quanto:fim + 1] = fundo
    return img.astype(np.uint8)


class Janela:
    _hWnd = 0


def prepara(img):
    main.client_rect = lambda win: (0, 0, largura + 0, altura + 380)
    main.grab = lambda regiao: img
    main._BATTLE_ANCHOR.clear()


print("larguras da barra e o que o bot enxerga:\n")
print(f"{'barra':>6} | {'entradas':>8} | {'tem alvo':>8}")
print("-" * 30)

# primeiro a amostra inteira, para o bot aprender a coluna das barras (ancora)
resultados = {}
prepara(amostra)
main.BATTLE_PANEL_W = largura
main.BATTLE_SEARCH_Y = (380, 380 + altura)
base = main.battle_state(Janela())
print(f"{'cheia':>6} | {base[0]:>8} | {str(base[1]):>8}")

for quanto in (20, 12, 8, 5, 3, 2, 1):
    img = encurta(amostra, quanto)
    main.grab = lambda regiao, _i=img: _i
    entradas, alvo, _hp, _sp, _as = main.battle_state(Janela())
    resultados[quanto] = (entradas, alvo)
    print(f"{quanto:>6} | {entradas:>8} | {str(alvo):>8}")

perdeu = [q for q, (_e, a) in resultados.items() if not a and q >= main.BATTLE_BAR_MIN_FRACO]
print(f"\nlarguras em que o bot PERDEU o alvo: {perdeu}")
print("VEREDITO:", "OK - segura o alvo ate o fim" if not perdeu else "FALHOU")
