# -*- coding: utf-8 -*-
"""Bicho sozinho na battle list, com barra mais estreita que "saudavel".

Relatado: "ta dizendo que nao tem monstro na battle list mas ele ta la" - com o
Lizard Executioner sozinho, o painel mostrava "battle list 0 - vazia" e o log
dizia "battle list vazia; nada para aprender". O usuario notou o padrao certo:
"so ataca o Lizard Executioner quando tem mais de um monstro na battle list".

Medido ao vivo, com o bicho sozinho na tela: o sprite dele tem 52 px coloridos
(o minimo exigido e 20 - nao e escuro, passa facil) mas a barra tem so 42 px de
largura, contra BATTLE_BAR_HEALTHY=100 exigido para ENSINAR a coluna da battle
list (a "ancora"). Sem ancora aprendida, NENHUM candidato e aceito - nem o
proprio, por mais que ele tenha passado nos filtros de sprite. Com mais de um
bicho, bastava outro ter barra larga (>=100px) para destravar a coluna, e dai o
estreito passava a ser aceito tambem, por estar na mesma coluna.

Este teste reproduz os numeros medidos numa imagem sintetica - o jogo muda de
estado a cada segundo, e o cenario exato (um bicho so, barra de 42px) nao da
para garantir ao vivo na hora de rodar a suite.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main


class Janela:
    isActive = True
    title = "falso"
    isMinimized = False


CW, CH = 1920, 1009


def monta_tela_com_um_bicho(largura_barra):
    """
    Uma battle list com UM candidato: sprite valido, barra da largura pedida.

    Reproduz a geometria que battle_state() espera: a barra e uma faixa
    horizontal ESTREITA (poucas linhas) e BRILHANTE, e o sprite fica citado
    numa caixa a esquerda dela (fatia = 15 linhas acima ate a barra, 20
    colunas a esquerda do inicio dela).
    """
    x0 = max(CW - main.BATTLE_PANEL_W, 0)
    y0, y1 = main.BATTLE_SEARCH_Y[0], min(main.BATTLE_SEARCH_Y[1], CH)
    alt, larg = y1 - y0, CW - x0
    img = np.full((alt, larg, 3), 20, dtype=np.uint8)   # fundo escuro/neutro

    gy0 = 150                       # linha onde a barra comeca (dentro da faixa)
    bx0 = 60                        # coluna onde a barra comeca
    # o SPRITE primeiro: caixa colorida a esquerda de onde a barra vai ficar.
    # SATURADA (passa "cheio") mas ABAIXO de BATTLE_BAR_MIN_BRIGHT - um sprite
    # de bicho de verdade nao e um bloco solido brilhante, e pintar um aqui
    # (erro do primeiro rascunho deste teste) fundia o sprite com a barra num
    # bloco alto demais, descartado como botao de painel antes mesmo de
    # chegar no teste que este arquivo quer exercitar.
    sy0, sy1 = max(gy0 - 15, 0), gy0 + 2
    sx0, sx1 = max(bx0 - 23, 0), max(bx0 - 3, 0)
    img[sy0:sy1, sx0:sx1] = (70, 35, 15)
    # a BARRA por cima: 3 linhas, verde brilhante e saturado (bicho vivo)
    img[gy0:gy0 + 3, bx0:bx0 + largura_barra] = (0, 200, 0)
    return img


falhas = []
for largura in (42, 130):
    tela = monta_tela_com_um_bicho(largura)
    main.client_rect = lambda win: (0, 0, CW, CH)
    main.grab = lambda regiao, _t=tela: _t
    main._BATTLE_ANCHOR.clear()
    main._BATTLE_TRACK = 0

    entradas, atacando, _hp, sprites, _alvo = main.battle_state(Janela())
    esperado_saudavel = largura >= main.BATTLE_BAR_HEALTHY
    print(f"barra de {largura}px ({'>=' if esperado_saudavel else '<'} "
          f"BATTLE_BAR_HEALTHY={main.BATTLE_BAR_HEALTHY}): "
          f"entradas={entradas}  ancora={main._BATTLE_ANCHOR}")
    if entradas != 1:
        falhas.append(
            f"barra de {largura}px sozinha na lista: {entradas} entrada(s), "
            f"esperava 1. O bicho estava la, com sprite valido - so a barra "
            f"era mais estreita que BATTLE_BAR_HEALTHY, e sem outro bicho "
            f"para ensinar a coluna a lista nunca aprendia a propria")

# ----------------------------------------------------- e a coluna ARRENDA
# uma vez aprendida (mesmo por bootstrap estreito), o bicho ESTREITO sozinho
# continua sendo aceito nas leituras seguintes, sem precisar de outro bicho
# de novo - a ancora persiste.
main._BATTLE_ANCHOR.clear()
main._BATTLE_TRACK = 0
tela_estreita = monta_tela_com_um_bicho(42)
main.grab = lambda regiao, _t=tela_estreita: _t
primeira, _, _, _, _ = main.battle_state(Janela())
segunda, _, _, _, _ = main.battle_state(Janela())
print(f"\nduas leituras seguidas, so o bicho estreito: {primeira}, {segunda}")
if primeira != 1 or segunda != 1:
    falhas.append(f"nao ficou estavel: {primeira} depois {segunda}, esperava "
                  f"1 nas duas")

print("\nVEREDITO:", "OK - bicho sozinho com barra estreita nao fica invisivel"
      if not falhas else "FALHOU: " + "; ".join(falhas))
