# -*- coding: utf-8 -*-
"""Caverna em estrela com o minimapa CURTO: o bot fica sem ver bandeira nenhuma
em boa parte do caminho, e a odometria do minimapa erra. Se ele perder a
referencia, o mapa mental incha (bandeiras fantasmas) e ele se perde.
"""
import math, os, random, sys
from collections import deque
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

random.seed(int(os.environ.get("SEMENTE", "1")))
VEL = 2
RAIO = int(os.environ.get("RAIO", "52"))       # minimapa de verdade
CEGUEIRA = float(os.environ.get("CEGUEIRA", "0.05"))   # chance de a leitura falhar
ERRO_ODO = float(os.environ.get("ERRO_ODO", "0.25"))   # erro da odometria

POS = {"J": (0, 0), "A1": (-14, 0), "A2": (-28, 0), "B1": (0, -16),
       "C1": (26, 0), "C2": (46, 0)}
VIZINHOS = {"J": ["A1", "B1", "C1"], "A1": ["J", "A2"], "A2": ["A1"],
            "B1": ["J"], "C1": ["J", "C2"], "C2": ["C1"]}


def caminho_ate(origem, destino):
    fila, veio = deque([origem]), {origem: None}
    while fila:
        atual = fila.popleft()
        if atual == destino:
            break
        for viz in VIZINHOS[atual]:
            if viz not in veio:
                veio[viz] = atual
                fila.append(viz)
    rota, no = [], destino
    while no is not None:
        rota.append(no)
        no = veio[no]
    return list(reversed(rota))


class Mundo:
    def __init__(self):
        self.xy = list(POS["J"])
        self.rota = []
        self.pedra = 0

    @property
    def pos(self):
        return tuple(self.xy)

    @property
    def no_atual(self):
        return min(POS, key=lambda n: math.dist(POS[n], self.xy))

    def anda(self):
        if not self.rota:
            return (0.0, 0.0)
        antes = tuple(self.xy)
        alvo = POS[self.rota[0]]
        d = math.dist(alvo, self.xy)
        if d <= VEL:
            self.xy = list(alvo)
            self.rota.pop(0)
        else:
            self.xy[0] += (alvo[0] - self.xy[0]) / d * VEL
            self.xy[1] += (alvo[1] - self.xy[1]) / d * VEL
        return (self.xy[0] - antes[0], self.xy[1] - antes[1])


mundo = Mundo()


class Odo:
    """A odometria do minimapa: segue o movimento de verdade, mas com erro."""

    def __init__(self):
        self.pos = [0.0, 0.0]

    @property
    def parado(self):
        return 0 if mundo.rota else 9

    def anda(self, d):
        self.pos[0] += d[0] * (1 + random.uniform(-ERRO_ODO, ERRO_ODO))
        self.pos[1] += d[1] * (1 + random.uniform(-ERRO_ODO, ERRO_ODO))

    def atualiza(self):
        pass

    def ancora(self, alvo):
        pass


odo = Odo()


apagao = {"restam": 0}


def visiveis(win, mm=None, cor=None):
    """As bandeiras somem por algumas leituras de vez em quando: bicho por cima
    delas, minimapa redesenhando, janela ocupada. E ai que o bot se perdia."""
    if apagao["restam"] > 0:
        apagao["restam"] -= 1
        return []
    if random.random() < CEGUEIRA:
        apagao["restam"] = random.randint(10, 45)
        return []
    px, py = mundo.pos
    vistas = [(int(round(p[0] - px)), int(round(p[1] - py))) for p in POS.values()]
    return sorted([v for v in vistas if abs(v[0]) <= RAIO and abs(v[1]) <= RAIO],
                  key=lambda m: abs(m[0]) + abs(m[1]))


def clica(win, passo):
    px, py = mundo.pos
    destino = (px + passo[0], py + passo[1])
    alvo = min(POS, key=lambda n: math.dist(POS[n], destino))
    if math.dist(POS[alvo], destino) > main.MARK_MERGE:
        mundo.pedra += 1
        return
    origem = mundo.no_atual if not mundo.rota else mundo.rota[0]
    mundo.rota = caminho_ate(origem, alvo)[1:]


main.detect_marks, main.click_minimap = visiveis, clica

estado, cd = {}, main.Cooldown(0)
visitas, antes, cegos = [], 0, 0
quadros = 0
for quadros in range(1, 6001):
    odo.anda(mundo.anda())
    if not visiveis(None):
        cegos += 1
    main.follow_marks(None, odo, estado, cd)
    if estado.get("ordem", 0) != antes:
        antes = estado["ordem"]
        visitas.append(mundo.no_atual)
    if len(visitas) >= 14:
        break

conhecidas = len(estado.get("visitadas", {}))
print(f"\nminimapa de raio {RAIO} px | leituras sem ver bandeira: {cegos}")
print(f"leituras ate {len(visitas)} visitas: {quadros}")
print("visitas:", " ".join(visitas))
print(f"bandeiras no mapa mental: {conhecidas} (existem {len(POS)})")
print("cliques em parede:", mundo.pedra)
descobertas = []
for v in visitas:
    if v not in descobertas:
        descobertas.append(v)
print("ordem de descoberta:", " ".join(descobertas))
ok = (conhecidas == len(POS) and set(descobertas) == set(POS)
      and mundo.pedra == 0)
print("VEREDITO:", "OK - nao se perdeu" if ok else
      f"FALHOU ({'inventou bandeiras' if conhecidas > len(POS) else 'nao varreu'})")
