# -*- coding: utf-8 -*-
"""Kite com distancia de DOIS lados, e sem pisar em escada ou buraco.

Perto demais e perigo; longe demais e perder o bicho - se ele corre, tem de
correr atras. E ha quadrados em que nao se pisa de jeito nenhum: escada, buraco,
portal. Cair de andar fugindo de bicho e queda sem volta automatica.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import numpy as np
import main

main.KITE_DIAGONAIS = False               # como o projeto vem: so setas
D = main.KITE_DIST
falhas = []

print(f"mantendo {D} SQM (KITE_DIST), diagonais desligadas\n")

# ------------------------------------------------------- 1) os dois lados
CASOS = [
    ("colado, tem de recuar",        [(1, 0)],   "left"),
    ("a 2, ainda recua",             [(2, 0)],   "left"),
    (f"exatamente a {D}, fica",      [(D, 0)],   None),
    ("longe, tem de perseguir",      [(D + 1, 0)], "right"),
    ("muito longe, persegue",        [(8, 0)],   "right"),
    ("longe para tras, persegue",    [(0, -7)],  "up"),
    ("um longe e um na distancia",    [(8, 0), (D, 0)], None),
]
for nome, criaturas, esperado in CASOS:
    passo = main.passo_de_kite(criaturas)
    perto = main.longe_o_bastante(criaturas)
    print(f"  {nome:30} bichos={str(criaturas):20} perto={perto} -> {passo}")
    if passo != esperado:
        falhas.append(f"{nome}: esperava {esperado}, saiu {passo}")

# perseguir de longe nao pode aproximar demais de OUTRO bicho
perto_e_longe = [(8, 0), (-D, 0)]        # um a 8 na direita, um na distancia
passo = main.passo_de_kite(perto_e_longe)
print(f"\n  perseguindo o de 8 com outro a {D} atras: {passo}")
if passo == "left":
    falhas.append("recuou para cima do bicho que estava na distancia")

# ---------------------------------------------- 2) escada, buraco, portal
print("\nquadrados de nao pisar:")
LADOS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
# bicho colado a direita: o passo natural e para a esquerda
bicho = [(1, 0)]
print(f"  sem proibicao, bicho a direita -> {main.passo_de_kite(bicho)}")
com_escada = main.passo_de_kite(bicho, proibidos={LADOS["left"]})
print(f"  com escada a esquerda          -> {com_escada}")
if com_escada == "left":
    falhas.append("pisou na escada")
if com_escada is None:
    falhas.append("desistiu de fugir tendo outro lado livre")

# so sobra a escada: melhor ficar do que cair de andar
so_escada = main.passo_de_kite(bicho, proibidos=set(LADOS.values()))
print(f"  todos os lados proibidos       -> {so_escada}")
if so_escada is not None:
    falhas.append(f"andou para {so_escada} com todos os lados proibidos")

# --------------------------------------- 3) reconhecer o quadrado ensinado
print("\nreconhecimento do quadrado ensinado:")
np.random.seed(5)
escada = (np.random.rand(main.TILE_PX, main.TILE_PX, 3) * 255).astype(np.uint8)
chao = (np.random.rand(main.TILE_PX, main.TILE_PX, 3) * 255).astype(np.uint8)
lugares = {"escada": main.assinatura_tile(escada)}
print("  a propria escada:", main.tile_proibido(escada, lugares))
print("  outro chao:      ", main.tile_proibido(chao, lugares))
print("  escada mais escura:",
      main.tile_proibido((escada * 0.9).astype(np.uint8), lugares))
if main.tile_proibido(escada, lugares) != "escada":
    falhas.append("nao reconheceu o proprio quadrado ensinado")
if main.tile_proibido(chao, lugares) is not None:
    falhas.append("confundiu chao comum com escada")

# a grade do viewport: um quadrado proibido no lado de baixo
tela = np.zeros((main.GAME_VIEW[3], main.GAME_VIEW[2], 3), dtype=np.uint8)
meio_col = (main.GAME_VIEW[2] // main.TILE_PX) // 2
meio_lin = (main.GAME_VIEW[3] // main.TILE_PX) // 2
y0 = (meio_lin + 1) * main.TILE_PX
x0 = meio_col * main.TILE_PX
tela[y0:y0 + main.TILE_PX, x0:x0 + main.TILE_PX] = escada
proibidos = main.passos_proibidos(tela, lugares)
print(f"  escada desenhada embaixo -> passos proibidos: {sorted(proibidos)}")
if (0, 1) not in proibidos:
    falhas.append("nao proibiu o passo para baixo, onde esta a escada")

# ------------------------- 4) preferir o chao por onde ele JA ANDOU
# Aquele chao esta provado: nao tem parede, porque o personagem passou por ele,
# e nao tem escada, porque ele nao mudou de andar ali. Vale como desempate,
# nunca acima da distancia do bicho.
print("\nchao ja pisado como desempate:")
AQUI = (0, 0)
px_sqm = main.MINIMAP_PX_SQM
esquerda, direita = (-px_sqm, 0), (px_sqm, 0)

# Precisa ser um EMPATE de verdade para o rastro entrar: com bicho em cima e
# escada embaixo, esquerda e direita resolvem exatamente igual (o bicho fica a 1
# de qualquer jeito, e em linha reta a mesma coisa). So ai o rastro decide.
bicho, escada_embaixo = [(0, -1)], {(0, 1)}
print("  bicho em cima, escada embaixo:")
print(f"    sem rastro                       -> "
      f"{main.passo_de_kite(bicho, proibidos=escada_embaixo)}")
com_esq = main.passo_de_kite(bicho, proibidos=escada_embaixo,
                             pisado={esquerda}, aqui=AQUI)
com_dir = main.passo_de_kite(bicho, proibidos=escada_embaixo,
                             pisado={direita}, aqui=AQUI)
print(f"    com rastro a esquerda            -> {com_esq}")
print(f"    com rastro a direita             -> {com_dir}")
if com_esq != "left":
    falhas.append(f"ignorou o rastro a esquerda (saiu {com_esq})")
if com_dir != "right":
    falhas.append(f"ignorou o rastro a direita (saiu {com_dir})")

# o rastro NAO pode ganhar da distancia: com bicho colado a esquerda, seguir o
# rastro de la seria andar para cima dele
perigo = main.passo_de_kite([(-1, 0)], pisado={esquerda}, aqui=AQUI)
print(f"  bicho colado a esquerda, rastro la -> {perigo}")
if perigo is not None and main.KITE_PASSOS[perigo] == (-1, 0):
    falhas.append("seguiu o rastro para cima do bicho")

print("\nVEREDITO:", "OK - dois lados e sem pisar onde nao deve" if not falhas
      else "FALHOU: " + "; ".join(falhas))
