# -*- coding: utf-8 -*-
"""Calibrar CREATURE_BAR_ABOVE pela barra do PROPRIO personagem.

O bot converte a posicao da barra de vida no quadrado da criatura somando
CREATURE_BAR_ABOVE. Errado por um, TODA posicao sai errada por um quadrado em y
- e o loot clica no quadrado do lado. Num log de cacada de verdade, o palpite
(que vem dessa conversao) e a escolha pela mudanca de tela discordavam sempre em
y, sempre por 1, nunca em x:

    corpo em (0, -1) ... palpite era (0, -2)
    corpo em (-3, 0) ... palpite era (-3, 1)
    corpo em (3, -2) ... palpite era (3, -1)

Nao ha por que adivinhar o valor: o personagem esta SEMPRE no quadrado do meio
da tela, e o cliente desenha barra sobre ele. Passada pela mesma conversao, a
barra dele tem de cair em (0, 0). Caindo em (0, -1), a constante esta um a
menos.

Aqui o desvio e CONHECIDO de proposito - o cenario desenha a barra do
personagem deslocada de propria mao - e se mede se a calibracao o descobre.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

_vx, _vy, VW, VH = main.GAME_VIEW
MEIO_COL, MEIO_LIN = (VW // main.TILE_PX) // 2, (VH // main.TILE_PX) // 2
CHAO = np.random.default_rng(31).integers(40, 70, (VH, VW, 3), dtype=np.uint8)


def barra_em(img, col, lin):
    """Desenha a moldura da barra no quadrado (col, lin) da grade."""
    x = col * main.TILE_PX + 18
    y = lin * main.TILE_PX + 10
    img[y:y + 4, x:x + 31] = (0, 0, 0)
    img[y + 1:y + 3, x + 1:x + 30] = (0, 95, 0)
    return img


falhas = []
print(f"CREATURE_BAR_ABOVE = {main.CREATURE_BAR_ABOVE} | grade "
      f"{VW // main.TILE_PX}x{VH // main.TILE_PX}, meio em "
      f"({MEIO_COL}, {MEIO_LIN})\n")

main.client_rect = lambda win: (0, 0, 1920, 1009)

# Para cada desvio de verdade, o cenario desenha a barra do personagem no lugar
# que ela ocuparia com esse desvio, e a calibracao tem de descobri-lo.
print("desvio de verdade -> desvio medido pela barra do personagem:")
for real in (-1, 0, 1):
    img = CHAO.copy()
    # com desvio `real`, a conversao (barra // tile + CREATURE_BAR_ABOVE) cai
    # `real` quadrados abaixo do personagem; entao a barra dele esta desenhada
    # `real` quadrados abaixo de onde a constante atual espera
    linha_da_barra = MEIO_LIN - main.CREATURE_BAR_ABOVE + real
    barra_em(img, MEIO_COL, linha_da_barra)
    main.grab = lambda regiao, _i=img: _i
    main.detect_creatures(None)
    medido = main.desvio_da_barra()
    sugerido = (main.CREATURE_BAR_ABOVE - medido
                if medido is not None else None)
    print(f"  {real:+d} -> medido {medido if medido is None else f'{medido:+d}'}"
          f" | sugere CREATURE_BAR_ABOVE={sugerido}")
    if medido != real:
        falhas.append(f"desvio de verdade {real:+d} foi medido como {medido}: "
                      f"sem acertar isto, toda posicao de criatura sai errada "
                      f"por um quadrado em y e o loot clica ao lado")
    if real == 0 and sugerido != main.CREATURE_BAR_ABOVE:
        falhas.append(f"sem desvio, a sugestao mudou a constante para "
                      f"{sugerido}")

# --------------------- a barra do personagem desligada: diz que nao sabe
main.grab = lambda regiao: CHAO.copy()
main.detect_creatures(None)
print(f"\nsem nenhuma barra na tela: desvio medido = "
      f"{main.desvio_da_barra()}")
if main.desvio_da_barra() is not None:
    falhas.append("sem barra nenhuma ele opinou um desvio: a barra sobre o "
                  "personagem pode estar desligada no cliente, e ai nao ha o "
                  "que medir")

# --------------------- bicho na mesma coluna nao rouba a medida
# Com bicho em cima ou embaixo do personagem, duas barras caem na coluna zero.
# A do personagem e a mais perto da linha dele - a outra esta a SQM de
# distancia.
img = barra_em(CHAO.copy(), MEIO_COL, MEIO_LIN - main.CREATURE_BAR_ABOVE)
img = barra_em(img, MEIO_COL, MEIO_LIN - main.CREATURE_BAR_ABOVE + 3)
main.grab = lambda regiao, _i=img: _i
criaturas = main.detect_creatures(None)
medido = main.desvio_da_barra()
print(f"personagem + bicho 3 SQM abaixo, mesma coluna: criaturas={criaturas}, "
      f"desvio medido={medido:+d}")
if medido != 0:
    falhas.append(f"com bicho na mesma coluna o desvio saiu {medido:+d}: a "
                  f"barra do personagem e a mais perto da linha dele")
if (0, 3) not in criaturas:
    falhas.append(f"o bicho da mesma coluna nao foi detectado: {criaturas}")

print("\nVEREDITO:", "OK - a barra do personagem calibra a conversao"
      if not falhas else "FALHOU: " + "; ".join(falhas))
