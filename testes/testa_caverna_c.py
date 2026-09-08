# -*- coding: utf-8 -*-
"""A caverna de verdade: um "O" aberto (C), com a entrada no meio da direita.
O personagem NAO corta pedra - ele anda preso ao corredor, como no jogo, e
passa por cima das marcas do meio do caminho. A odometria e lixo de proposito.
"""
import math, random
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

random.seed(11)
RAIO, VEL = 52, 2

# corredor em "C": pontas em cima e embaixo, entrada no meio da direita.
# 9 marcas, ~20 px (10 sqm) de distancia entre vizinhas.
R = 34
ANG = [-100, -75, -50, -25, 0, 25, 50, 75, 100]     # graus; 0 = entrada
NOMES = ["P1", "P2", "P3", "P4", "ENT", "P5", "P6", "P7", "P8"]
CAMINHO = [(round(R * math.cos(math.radians(a))),
            round(R * math.sin(math.radians(a)))) for a in ANG]
MARCAS = dict(zip(NOMES, CAMINHO))


class Mundo:
    """Posicao guardada como distancia percorrida ao longo do corredor."""

    def __init__(self):
        self.t = float(self._dist_ate(4))       # comeca na entrada
        self.destino = None
        self.pedra = 0
        self.acumulado = [0.0]
        for i in range(1, len(CAMINHO)):
            a, b = CAMINHO[i - 1], CAMINHO[i]
            self.acumulado.append(self.acumulado[-1] + math.dist(a, b))
        self.t = self.acumulado[4]

    def _dist_ate(self, i):
        return i

    @property
    def pos(self):
        for i in range(1, len(self.acumulado)):
            if self.t <= self.acumulado[i]:
                a, b = CAMINHO[i - 1], CAMINHO[i]
                trecho = self.acumulado[i] - self.acumulado[i - 1]
                f = (self.t - self.acumulado[i - 1]) / trecho
                return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
        return CAMINHO[-1]

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
        self.pos[0] += random.randint(-6, 6)
        self.pos[1] += random.randint(-6, 6)

    def ancora(self, alvo):
        pass


def visiveis(win, mm=None, cor=None):
    px, py = mundo.pos
    vistas = [(int(round(m[0] - px)), int(round(m[1] - py))) for m in CAMINHO]
    return sorted([v for v in vistas if abs(v[0]) <= RAIO and abs(v[1]) <= RAIO],
                  key=lambda m: abs(m[0]) + abs(m[1]))


def clica(win, passo):
    """Clique so anda se cair em cima de marca; o percurso segue o corredor."""
    px, py = mundo.pos
    destino = (px + passo[0], py + passo[1])
    i = min(range(len(CAMINHO)),
            key=lambda k: math.dist(CAMINHO[k], destino))
    if math.dist(CAMINHO[i], destino) > main.MARK_MERGE:
        mundo.pedra += 1
        return
    mundo.destino = mundo.acumulado[i]


main.detect_marks, main.click_minimap = visiveis, clica

odo, estado, cd = Odo(), {}, main.Cooldown(0)
nome = lambda p: next((n for n, m in MARCAS.items()
                       if math.dist(m, p) <= 3), "?")

visitas, antes = [], 0
for _ in range(6000):
    odo.atualiza()
    mundo.anda()
    main.follow_marks(None, odo, estado, cd)
    if estado.get("ordem", 0) != antes:
        antes = estado["ordem"]
        visitas.append(nome(mundo.pos))
    if len(visitas) >= 22:
        break

seq = " ".join(visitas)
print("\ncorredor em C:", " ".join(NOMES), "(ENT = entrada, no meio)")
print("visitas:", seq)
print("cliques em parede:", mundo.pedra)

texto = "".join(visitas)
ok = ("P1" in visitas and "P8" in visitas and mundo.pedra == 0)
inverte_so_na_ponta = all(
    visitas[i] in ("P1", "P8") for i in range(1, len(visitas) - 1)
    if visitas[i - 1] == visitas[i + 1])
print("chegou nas duas pontas:", ok,
      "| so inverte na ponta:", inverte_so_na_ponta)
print("VEREDITO:", "OK" if ok and inverte_so_na_ponta else "FALHOU")
