# -*- coding: utf-8 -*-
"""Poucas bandeiras na tela - o caso do log do usuario ("2 candidata(s)").

Com uma ou duas bandeiras visiveis nao ha conjunto para casar entre leituras, e
a estimativa de deslocamento fica ambigua. Era assim que o bot perdia a bandeira
alvo ("sumiu do lugar em N leituras") e trocava de rumo sem ter chegado: clicava
em cima e depois embaixo.
"""
import io, math, os, random, sys
from contextlib import redirect_stdout
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

random.seed(int(os.environ.get("SEMENTE", "1")))
VEL = 2
RAIO = int(os.environ.get("RAIO", "30"))        # minimapa curto: 1-2 bandeiras
ESPACO = 25
TREME = float(os.environ.get("TREME", "1"))     # tremida do centro detectado
ERRO_ODO = float(os.environ.get("ERRO_ODO", "0.12"))

NOMES = ["F1", "F2", "F3", "F4", "F5", "F6"]
CAMINHO = [(0, -ESPACO * i) for i in range(len(NOMES))]
MARCAS = dict(zip(NOMES, CAMINHO))


class Mundo:
    def __init__(self):
        self.xy = [0.0, 0.0]
        self.destino = None
        self.pedra = 0

    @property
    def pos(self):
        return tuple(self.xy)

    def anda(self):
        if self.destino is None:
            return (0.0, 0.0)
        antes = tuple(self.xy)
        d = math.dist(self.destino, self.xy)
        if d <= VEL:
            self.xy = list(self.destino)
            self.destino = None
        else:
            self.xy[0] += (self.destino[0] - self.xy[0]) / d * VEL
            self.xy[1] += (self.destino[1] - self.xy[1]) / d * VEL
        return (self.xy[0] - antes[0], self.xy[1] - antes[1])


mundo = Mundo()


class Odo:
    """A odometria do minimapa: acompanha o movimento, com erro."""

    def __init__(self):
        self.pos = [0.0, 0.0]

    @property
    def parado(self):
        return 0 if mundo.destino is not None else 9

    def anda(self, d):
        self.pos[0] += d[0] * (1 + random.uniform(-ERRO_ODO, ERRO_ODO))
        self.pos[1] += d[1] * (1 + random.uniform(-ERRO_ODO, ERRO_ODO))

    def atualiza(self):
        pass

    def ancora(self, alvo):
        pass


odo = Odo()


def visiveis(win, mm=None, cor=None):
    px, py = mundo.pos
    vistas = []
    for p in CAMINHO:
        off = (p[0] - px + random.uniform(-TREME, TREME),
               p[1] - py + random.uniform(-TREME, TREME))
        if abs(off[0]) <= RAIO and abs(off[1]) <= RAIO:
            vistas.append((int(round(off[0])), int(round(off[1]))))
    return sorted(vistas, key=lambda m: abs(m[0]) + abs(m[1]))


def clica(win, passo):
    px, py = mundo.pos
    destino = (px + passo[0], py + passo[1])
    alvo = min(CAMINHO, key=lambda p: math.dist(p, destino))
    if math.dist(alvo, destino) > main.MARK_MERGE:
        mundo.pedra += 1
        return
    mundo.destino = alvo


main.detect_marks, main.click_minimap = visiveis, clica

estado, cd = {}, main.Cooldown(0)
nome = lambda p: next((n for n, m in MARCAS.items() if math.dist(m, p) <= 4), "?")

visitas, antes, trocas_no_meio = [], 0, 0
saida = io.StringIO()
with redirect_stdout(saida):
    for _ in range(40000):
        odo.anda(mundo.anda())
        alvo_antes = estado.get("alvo_off")
        main.follow_marks(None, odo, estado, cd)
        alvo = estado.get("alvo_off")
        if (alvo_antes is not None and alvo is not None and alvo != alvo_antes
                and estado.get("cliques", 0) == 0):
            longe = min(math.dist(m, mundo.pos) for m in CAMINHO)
            if longe > main.MARK_ARRIVE + 2:
                trocas_no_meio += 1
        if estado.get("ordem", 0) != antes:
            antes = estado["ordem"]
            visitas.append(nome(mundo.pos))
        if len(visitas) >= 24:
            break

log = saida.getvalue()
print(f"\ncorredor {' '.join(NOMES)} a {ESPACO}px, minimapa +-{RAIO}px, "
      f"tremida +-{TREME}px")
print("visitas:", " ".join(visitas))
print(f"bandeiras dadas por perdidas: {log.count('sumiu do lugar')}")
print(f"trocas de alvo sem ter chegado: {trocas_no_meio}")
print(f"cliques em parede: {mundo.pedra} | mapa mental: "
      f"{len(estado.get('visitadas', {}))} (existem {len(CAMINHO)})")
ok = (log.count("sumiu do lugar") == 0 and trocas_no_meio == 0
      and len(estado.get("visitadas", {})) == len(CAMINHO))
print("VEREDITO:", "OK" if ok else "FALHOU")
