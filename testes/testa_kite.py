# -*- coding: utf-8 -*-
"""Kite: manter distancia de todo bicho na tela, inclusive do alvo.

Duas partes:
  1. a DETECCAO, contra a captura de verdade de dentro da cave - as barrinhas de
     vida sobre as criaturas viram offsets em SQM, e a barra do proprio
     personagem tem de ser descartada;
  2. a DECISAO, contra tabuleiros montados a mao - para que lado fugir, e quando
     nao ha para onde.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import numpy as np
import main

falhas = []

# A decisao e testada com as diagonais LIGADAS, que e o comportamento completo.
# O padrao do projeto e desligado porque no cliente testado o teclado numerico
# nao move o personagem (ver KITE_DIAGONAIS no main.py).
print(f"KITE_DIAGONAIS no projeto: {main.KITE_DIAGONAIS} "
      f"(este teste liga para medir tambem as diagonais)")
main.KITE_DIAGONAIS = True

# ------------------------------------------------------- 1) deteccao na captura
AMOSTRA = AQUI + "tela_cave.png"     # PNG e nao npy: um terco do tamanho, e
if os.path.exists(AMOSTRA):          # ja exercita o leitor do png.py
    import png
    tela = png.le(AMOSTRA)
    # A AMOSTRA TEM A GEOMETRIA DA EPOCA EM QUE FOI TIRADA, e nao a do cliente
    # de hoje: 15x11 quadrados de 68px comecando em (221,61). Ler pixel antigo
    # com grade nova poe as criaturas em quadrados que nao sao os delas, e o
    # teste passaria a medir a diferenca entre dois layouts em vez da deteccao.
    # As constantes do projeto sao MEDIDAS no cliente atual (python main.py
    # --grade); aqui vale a da foto.
    guardado = (main.GAME_VIEW, main.TILE_PX)
    main.GAME_VIEW, main.TILE_PX = (221, 61, 15 * 68, 11 * 68), 68
    vx, vy, vw, vh = main.GAME_VIEW
    cheio = np.zeros((vh, vw, 3), dtype=tela.dtype)   # a amostra e um recorte
    pedaco = tela[vy:vy + vh, vx:vx + vw]
    cheio[:pedaco.shape[0], :pedaco.shape[1]] = pedaco
    achadas = main.detect_creatures(None, img=cheio)
    # as duas criaturas da cena, conferidas uma a uma no pixel:
    #   (-1, 0) Skeleton colado a esquerda, barra cheia (moldura em 630,378)
    #   (-4, 3) Bonelord no canto de baixo, 14px de barra ~48% (443,598)
    # a barra de vida E a de mana do proprio personagem caem no quadrado do meio
    # (698,374 verde e 698,378 azul) e sao descartadas.
    ESPERADAS = [(-1, 0), (-4, 3)]
    print("captura da cave (Skeleton colado a esquerda, Bonelord no canto):")
    print("  criaturas:", achadas)
    print("  mais perto:", main.longe_o_bastante(achadas), "SQM")
    print("  passo de fuga:", main.passo_de_kite(achadas))
    if sorted(achadas) != sorted(ESPERADAS):
        falhas.append(f"deteccao na captura: esperava {ESPERADAS}, "
                      f"saiu {achadas}")
    passo = main.passo_de_kite(achadas)
    px, py = main.KITE_PASSOS[passo] if passo else (0, 0)
    depois = main.longe_o_bastante([(dx - px, dy - py) for dx, dy in achadas])
    if depois <= main.longe_o_bastante(achadas):
        falhas.append(f"fuga na captura: {passo} nao afasta "
                      f"({main.longe_o_bastante(achadas)} -> {depois})")
    main.GAME_VIEW, main.TILE_PX = guardado
else:
    print(f"(sem {os.path.basename(AMOSTRA)}: a parte de deteccao nao roda)")

# --------------------------------------------------------------- 2) decisao
print("\ndecisao de fuga, tabuleiros montados a mao "
      f"(mantendo {main.KITE_DIST} SQM):")
# Aqui se confere o EFEITO, nao a tecla: com as diagonais ligadas ha mais de uma
# resposta certa, e qual delas nao vem ao caso. A decisao detalhada, com o
# projeto no padrao (so setas), esta no testa_kite_distancia.py.
CASOS = [
    ("bicho colado a esquerda", [(-1, 0)], "afasta"),
    ("bicho colado a direita", [(1, 0)], "afasta"),
    ("bicho em cima", [(0, -1)], "afasta"),
    ("bicho embaixo", [(0, 1)], "afasta"),
    ("dois, esquerda e cima", [(-1, 0), (0, -1)], "afasta"),
    (f"ja esta a {main.KITE_DIST} SQM", [(main.KITE_DIST, 0)], "fica"),
    ("longe demais", [(8, 0)], "aproxima"),
    ("nada na tela", [], "fica"),
]
for nome, criaturas, querido in CASOS:
    passo = main.passo_de_kite(criaturas)
    perto = main.longe_o_bastante(criaturas)
    if passo is None:
        saiu = "fica"
    else:
        px, py = main.KITE_PASSOS[passo]
        depois = main.longe_o_bastante([(dx - px, dy - py)
                                        for dx, dy in criaturas])
        saiu = ("afasta" if depois > perto else
                "aproxima" if depois < perto else "de lado")
    print(f"  {nome:28} bichos={str(criaturas):26} "
          f"perto={perto} -> {passo} ({saiu})")
    if querido == "afasta" and saiu not in ("afasta", "de lado"):
        falhas.append(f"{nome}: em vez de afastar, {saiu}")
    if querido in ("fica", "aproxima") and saiu != querido:
        falhas.append(f"{nome}: esperava {querido}, saiu {saiu}")

# Os casos sem resposta unica sao conferidos pelo EFEITO, nao pela tecla: o que
# importa e a posicao ficar melhor, e qual diagonal serve nao vem ao caso.
def depois_de(criaturas, tecla):
    px, py = main.KITE_PASSOS[tecla]
    return [(dx - px, dy - py) for dx, dy in criaturas]


dois = [(-1, 0), (0, -1)]                        # esquerda e em cima
passo = main.passo_de_kite(dois)
if passo is None or main.longe_o_bastante(depois_de(dois, passo)) <= 1:
    falhas.append(f"dois bichos: {passo} nao aumenta a distancia do mais perto")
else:
    print(f"\n  dois bichos: {passo} leva o mais perto de 1 para "
          f"{main.longe_o_bastante(depois_de(dois, passo))} SQM")

if main.passo_de_kite([(3, 0)]) is not None:
    falhas.append("andou estando ja na distancia pedida")

# cercado nos quatro lados retos: nao da para aumentar a distancia, mas a
# diagonal deixa dois vizinhos em vez de quatro - isso e melhor que ficar
cercado = [(-1, 0), (1, 0), (0, -1), (0, 1)]
passo = main.passo_de_kite(cercado)
if passo is not None:
    antes = sum(1 for c in cercado if max(abs(c[0]), abs(c[1])) <= 1)
    agora = sum(1 for c in depois_de(cercado, passo)
                if max(abs(c[0]), abs(c[1])) <= 1)
    print(f"  cercado: {passo} deixa {agora} bicho(s) colado(s) "
          f"em vez de {antes}")
    if agora >= antes:
        falhas.append(f"cercado: {passo} nao melhora nada")
    if main.KITE_PASSOS[passo] in cercado:
        falhas.append(f"cercado: {passo} anda para cima de um bicho")

# ------------------------------------------------- 3) foge de quem esta longe?
print("\nafastando-se em serie (bicho parado, personagem fugindo):")
criaturas, andou = [(-1, 0)], []
for _ in range(5):
    passo = main.passo_de_kite(criaturas)
    if passo is None:
        break
    andou.append(passo)
    px, py = main.KITE_PASSOS[passo]        # inclui as diagonais
    criaturas = [(dx - px, dy - py) for dx, dy in criaturas]
print("  passos:", andou, "-> bicho agora em", criaturas,
      f"({main.longe_o_bastante(criaturas)} SQM)")
if main.longe_o_bastante(criaturas) < main.KITE_DIST:
    falhas.append("nao chegou na distancia pedida fugindo em linha")
if len(andou) > main.KITE_DIST:
    falhas.append(f"gastou {len(andou)} passos para abrir "
                  f"{main.KITE_DIST} SQM, mais que o necessario")

print("\nVEREDITO:", "OK - mantem a distancia e sabe quando nao ha para onde ir"
      if not falhas else "FALHOU: " + "; ".join(falhas))
