# -*- coding: utf-8 -*-
"""Corredor com bandeiras ESPACADAS, como na caverna do usuario.

Com ~40px entre bandeiras e o minimapa de +-52px, chegando perto da ponta do
ramo muitas vezes so a bandeira de onde se veio esta na tela. Se a decisao olhar
so para o que aparece, a regra manda voltar por ela e o bot fica indo e vindo
entre as ultimas bandeiras: a "travadinha".
"""
import math
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

VEL = 2
RAIO = int(os.environ.get("RAIO", "52"))
ESPACO = int(os.environ.get("ESPACO", "40"))
NOMES = ["F1", "F2", "F3", "F4", "F5", "F6"]        # F1 e a ponta do ramo
CAMINHO = [(0, -ESPACO * i) for i in range(len(NOMES))][::-1]
CAMINHO = [(0, y) for y in sorted(p[1] for p in CAMINHO)]
MARCAS = dict(zip(NOMES, CAMINHO))


class Mundo:
    def __init__(self):
        self.t = float(len(CAMINHO) - 1) * ESPACO      # comeca na outra ponta
        self.destino = None
        self.pedra = 0

    @property
    def pos(self):
        return (0.0, CAMINHO[0][1] + self.t)

    def anda(self):
        if self.destino is None:
            return
        d = self.destino - self.t
        self.t += max(-VEL, min(VEL, d))
        if abs(self.destino - self.t) < 0.01:
            self.t, self.destino = self.destino, None


mundo = Mundo()


class Odo:
    def __init__(self):
        self.pos = [0, 0]

    @property
    def parado(self):
        return 0 if mundo.destino is not None else 9

    def atualiza(self):
        pass

    def ancora(self, alvo):
        pass


def visiveis(win, mm=None, cor=None):
    px, py = mundo.pos
    vistas = [(int(round(m[0] - px)), int(round(m[1] - py))) for m in CAMINHO]
    return sorted([v for v in vistas if abs(v[0]) <= RAIO and abs(v[1]) <= RAIO],
                  key=lambda m: abs(m[0]) + abs(m[1]))


def clica(win, passo):
    px, py = mundo.pos
    destino = (px + passo[0], py + passo[1])
    i = min(range(len(CAMINHO)), key=lambda k: math.dist(CAMINHO[k], destino))
    if math.dist(CAMINHO[i], destino) > main.MARK_MERGE:
        mundo.pedra += 1
        return
    mundo.destino = (CAMINHO[i][1] - CAMINHO[0][1])


main.detect_marks, main.click_minimap = visiveis, clica

odo, estado, cd = Odo(), {}, main.Cooldown(0)
nome = lambda p: next((n for n, m in MARCAS.items() if math.dist(m, p) <= 4), "?")

visitas, antes = [], 0
for _ in range(30000):
    mundo.anda()
    main.follow_marks(None, odo, estado, cd)
    if estado.get("ordem", 0) != antes:
        antes = estado["ordem"]
        visitas.append(nome(mundo.pos))
    if len(visitas) >= 30:
        break

print(f"\ncorredor: {' '.join(NOMES)} espacados {ESPACO}px, minimapa +-{RAIO}px")
print("visitas:", " ".join(visitas))
# quantas bandeiras aparecem na tela, tipicamente
mundo.t = ESPACO * 0.0
print(f"na ponta F1 o bot enxerga {len(visiveis(None))} bandeira(s)")
pontas = [v for v in visitas if v in ("F1", "F6")]
inversoes = [visitas[i] for i in range(1, len(visitas) - 1)
             if visitas[i - 1] == visitas[i + 1] and visitas[i] not in ("F1", "F6")]
print("pontas alcancadas:", sorted(set(pontas)), "| inversoes fora das pontas:",
      inversoes)
print("cliques em parede:", mundo.pedra)
print("VEREDITO:", "OK" if len(set(pontas)) == 2 and not inversoes
      and mundo.pedra == 0 else "FALHOU - travadinha nas ultimas bandeiras")
