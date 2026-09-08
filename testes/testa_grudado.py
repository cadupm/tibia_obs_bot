# -*- coding: utf-8 -*-
"""O alvo so pode mudar quando a cruz chega numa bandeira. Roda a caverna em C
com brigas e conta toda troca de alvo feita LONGE de qualquer marca.

O cenario vem do testa_briga_leve, executado aqui dentro - por isso ele imprime
o veredito DELE primeiro, que e severo com o teleporte artificial que injeta. O
veredito que importa aqui e o ultimo, "VEREDITO ALVO GRUDADO"."""
import math
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

CAM = AQUI + "testa_briga_leve.py"

ambiente = {"__name__": "__main__"}
orig = main.follow_marks
trocas_no_meio = []


def espiao(leitura, odo, estado, cd):
    antes = estado.get("alvo_off")
    r = orig(leitura, odo, estado, cd)
    depois = estado.get("alvo_off")
    if antes is not None and depois is not None and depois != antes \
            and estado.get("cliques", 0) == 0:
        mundo, marcas = ambiente["mundo"], ambiente["MARCAS"]
        px, py = mundo.pos
        longe = min(math.dist(m, (px, py)) for m in marcas.values())
        if longe > main.MARK_ARRIVE + 2:   # folga: manhattan x euclidiana
            trocas_no_meio.append(round(longe, 1))
    return r


main.follow_marks = espiao
# o cenario vem do outro teste, executado aqui dentro: ele precisa do
# proprio __file__ para achar o main.py
ambiente["__file__"] = CAM
exec(compile(open(CAM, encoding="utf-8").read(), CAM, "exec"), ambiente)
print(f"trocas de alvo longe de qualquer bandeira: {len(trocas_no_meio)} "
      f"{trocas_no_meio[:6]}")
print("VEREDITO ALVO GRUDADO:", "OK" if not trocas_no_meio else "FALHOU")
