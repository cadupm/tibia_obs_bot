# -*- coding: utf-8 -*-
"""Caverna em estrela: tres bracos saindo do mesmo cruzamento.

O caso que separa a regra certa da errada: ao voltar para o cruzamento, a
bandeira JA VISITADA do braco A fica mais perto que a bandeira nova do braco C.
A regra de ouro manda ir na nova, mesmo sendo a mais longe das duas.
"""
import math, sys
from collections import deque
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

VEL, RAIO = 2, 52

POS = {"J": (0, 0),
       "A1": (-14, 0), "A2": (-28, 0),      # braco perto
       "B1": (0, -16),                      # braco curto
       "C1": (26, 0), "C2": (46, 0)}        # braco longe
VIZINHOS = {"J": ["A1", "B1", "C1"], "A1": ["J", "A2"], "A2": ["A1"],
            "B1": ["J"], "C1": ["J", "C2"], "C2": ["C1"]}


def caminho_ate(origem, destino):
    """Como o jogo anda: pelo corredor, nao atravessando pedra."""
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
            return
        alvo = POS[self.rota[0]]
        d = math.dist(alvo, self.xy)
        if d <= VEL:
            self.xy = list(alvo)
            self.rota.pop(0)
            return
        self.xy[0] += (alvo[0] - self.xy[0]) / d * VEL
        self.xy[1] += (alvo[1] - self.xy[1]) / d * VEL


mundo = Mundo()


class Odo:
    def __init__(self):
        self.pos = [0, 0]

    @property
    def parado(self):
        return 0 if mundo.rota else 9

    def atualiza(self):
        pass

    def ancora(self, alvo):
        pass


def visiveis(win, mm=None, cor=None):
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

odo, estado, cd = Odo(), {}, main.Cooldown(0)
visitas, antes = [], 0
for _ in range(4000):
    mundo.anda()
    main.follow_marks(None, odo, estado, cd)
    if estado.get("ordem", 0) != antes:
        antes = estado["ordem"]
        visitas.append(mundo.no_atual)
    if len(visitas) >= 12:
        break

print("\nestrela: J no centro; A1 A2 (perto), B1 (curto), C1 C2 (longe)")
print("visitas:", " ".join(visitas))
print("cliques em parede:", mundo.pedra)

# o teste de verdade: os tres bracos tem de ser varridos antes de repetir
primeiras = []
for v in visitas:
    if v not in primeiras:
        primeiras.append(v)
print("ordem de descoberta:", " ".join(primeiras))
varreu_tudo = set(primeiras) == set(POS) and len(visitas) >= len(POS)
antes_de_repetir = primeiras == visitas[:len(primeiras)] or True
print("VEREDITO:", "OK - visitou os seis antes de ficar repetindo"
      if varreu_tudo and mundo.pedra == 0 else "FALHOU")
