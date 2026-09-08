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

# ------------------------------------------------------- 1) deteccao na captura
AMOSTRA = AQUI + "tela_cave.npy"
if os.path.exists(AMOSTRA):
    tela = np.load(AMOSTRA)
    vx, vy, vw, vh = main.GAME_VIEW
    cheio = np.zeros((vh, vw, 3), dtype=tela.dtype)   # a amostra e um recorte
    pedaco = tela[vy:vy + vh, vx:vx + vw]
    cheio[:pedaco.shape[0], :pedaco.shape[1]] = pedaco
    achadas = main.detect_creatures(None, img=cheio)
    print("captura da cave (Skeleton 1 SQM a esquerda do personagem):")
    print("  criaturas:", achadas)
    print("  mais perto:", main.longe_o_bastante(achadas), "SQM")
    print("  passo de fuga:", main.passo_de_fuga(achadas))
    if achadas != [(-1, 0)]:
        falhas.append(f"deteccao na captura: esperava [(-1, 0)], saiu {achadas}")
    if main.passo_de_fuga(achadas) != "right":
        falhas.append("fuga na captura: devia ser para a direita")
else:
    print(f"(sem {os.path.basename(AMOSTRA)}: a parte de deteccao nao roda)")

# --------------------------------------------------------------- 2) decisao
print("\ndecisao de fuga, tabuleiros montados a mao "
      f"(mantendo {main.KITE_DIST} SQM):")
CASOS = [
    ("bicho colado a esquerda", [(-1, 0)], "right"),
    ("bicho colado a direita", [(1, 0)], "left"),
    ("bicho em cima", [(0, -1)], "down"),
    ("bicho embaixo", [(0, 1)], "up"),
    ("dois, esquerda e cima", [(-1, 0), (0, -1)], None),   # direita ou baixo
    ("ja esta a 3 SQM", [(3, 0)], None),                   # nao anda
    ("ja esta longe", [(5, -4)], None),
    ("cercado dos quatro lados", [(-1, 0), (1, 0), (0, -1), (0, 1)], None),
    ("nada na tela", [], None),
]
for nome, criaturas, esperado in CASOS:
    passo = main.passo_de_fuga(criaturas)
    perto = main.longe_o_bastante(criaturas)
    print(f"  {nome:28} bichos={str(criaturas):32} "
          f"perto={perto} -> {passo}")
    if esperado is not None and passo != esperado:
        falhas.append(f"{nome}: esperava {esperado}, saiu {passo}")

# Os casos sem resposta unica sao conferidos pelo EFEITO, nao pela tecla: o que
# importa e a posicao ficar melhor, e qual diagonal serve nao vem ao caso.
def depois_de(criaturas, tecla):
    px, py = main.KITE_PASSOS[tecla]
    return [(dx - px, dy - py) for dx, dy in criaturas]


dois = [(-1, 0), (0, -1)]                        # esquerda e em cima
passo = main.passo_de_fuga(dois)
if passo is None or main.longe_o_bastante(depois_de(dois, passo)) <= 1:
    falhas.append(f"dois bichos: {passo} nao aumenta a distancia do mais perto")
else:
    print(f"\n  dois bichos: {passo} leva o mais perto de 1 para "
          f"{main.longe_o_bastante(depois_de(dois, passo))} SQM")

if main.passo_de_fuga([(3, 0)]) is not None:
    falhas.append("andou estando ja na distancia pedida")

# cercado nos quatro lados retos: nao da para aumentar a distancia, mas a
# diagonal deixa dois vizinhos em vez de quatro - isso e melhor que ficar
cercado = [(-1, 0), (1, 0), (0, -1), (0, 1)]
passo = main.passo_de_fuga(cercado)
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
    passo = main.passo_de_fuga(criaturas)
    if passo is None:
        break
    andou.append(passo)
    px, py = {"up": (0, -1), "down": (0, 1),
              "left": (-1, 0), "right": (1, 0)}[passo]
    criaturas = [(dx - px, dy - py) for dx, dy in criaturas]
print("  passos:", andou, "-> bicho agora em", criaturas,
      f"({main.longe_o_bastante(criaturas)} SQM)")
if main.longe_o_bastante(criaturas) < main.KITE_DIST:
    falhas.append("nao chegou na distancia pedida fugindo em linha")
if len(andou) != main.KITE_DIST - 1:
    falhas.append(f"gastou {len(andou)} passos para abrir "
                  f"{main.KITE_DIST} SQM (esperava {main.KITE_DIST - 1})")

print("\nVEREDITO:", "OK - mantem a distancia e sabe quando nao ha para onde ir"
      if not falhas else "FALHOU: " + "; ".join(falhas))
