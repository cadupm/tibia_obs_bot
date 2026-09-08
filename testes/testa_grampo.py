# -*- coding: utf-8 -*-
"""Caverna em grampo (a volta do "O"): dois bracos coladinhos, com pedra no meio.

Em linha reta B2 fica a 40px de A2 - mais perto que a proxima bandeira do
proprio corredor. Mas nao ha caminho direto: so dando a volta pela ponta. Clicar
de um braco no outro nao anda, e o bot fica patinando: a travadinha.
"""
import math, os, sys
from collections import deque
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

VEL, RAIO = 2, 52
POS = {"A1": (0, 0), "A2": (0, -40), "A3": (0, -80),
       "T": (20, -104),
       "B3": (40, -80), "B2": (40, -40), "B1": (40, 0)}
VIZINHOS = {"A1": ["A2"], "A2": ["A1", "A3"], "A3": ["A2", "T"],
            "T": ["A3", "B3"], "B3": ["T", "B2"], "B2": ["B3", "B1"],
            "B1": ["B2"]}
ORDEM = ["A1", "A2", "A3", "T", "B3", "B2", "B1"]


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
        self.xy = list(POS["A1"])
        self.rota = []
        self.pedra = 0

    @property
    def pos(self):
        return tuple(self.xy)

    @property
    def no(self):
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
    """
    O clique do mapa so leva ate onde da para andar em linha pelo corredor.
    Clicar no outro braco (pedra no meio) nao move o personagem.
    """
    px, py = mundo.pos
    destino = (px + passo[0], py + passo[1])
    alvo = min(POS, key=lambda n: math.dist(POS[n], destino))
    if math.dist(POS[alvo], destino) > main.MARK_MERGE:
        mundo.pedra += 1
        return
    origem = mundo.no if not mundo.rota else mundo.rota[0]
    rota = caminho_ate(origem, alvo)
    # atravessar o vao entre os bracos exige dar a volta: se a rota pelo
    # corredor for muito mais longa que a linha reta, o Tibia nao acha caminho
    andado = sum(math.dist(POS[rota[i]], POS[rota[i + 1]])
                 for i in range(len(rota) - 1))
    if andado > math.dist(POS[origem], POS[alvo]) * 2.2:
        mundo.pedra += 1          # clique na pedra: nao anda
        return
    mundo.rota = rota[1:]


main.detect_marks, main.click_minimap = visiveis, clica

odo, estado, cd = Odo(), {}, main.Cooldown(0)
visitas, antes = [], 0
pedra_na_metade = None
for _ in range(30000):
    mundo.anda()
    main.follow_marks(None, odo, estado, cd)
    if estado.get("ordem", 0) != antes:
        antes = estado["ordem"]
        visitas.append(mundo.no)
    if len(visitas) == 26 and pedra_na_metade is None:
        pedra_na_metade = mundo.pedra      # ja deu uma volta inteira
    if len(visitas) >= 40:
        break

print("\ngrampo:", " ".join(ORDEM), " (A2 e B2 ficam a 40px em linha reta)")
print("visitas:", " ".join(visitas))
print(f"cliques em pedra: {mundo.pedra} "
      f"({pedra_na_metade} nas duas primeiras voltas, "
      f"{mundo.pedra - pedra_na_metade} depois de aprender)")
ligacoes = estado.get("ligacoes", {})
print(f"ligacoes aprendidas: {sum(len(v) for v in ligacoes.values()) // 2} "
      f"(o corredor tem {len(ORDEM) - 1})")
saltos = [(visitas[i - 1], visitas[i]) for i in range(1, len(visitas))
          if visitas[i] not in VIZINHOS[visitas[i - 1]]]
print("saltos por cima da pedra:", saltos[:6], f"({len(saltos)} no total)")
# descobrir uma parede custa alguns cliques; o que nao pode e continuar
# batendo nela depois de aprendida
print("VEREDITO:", "OK - andou pelo corredor e nao repete a parede"
      if not saltos and mundo.pedra - pedra_na_metade == 0
      else "FALHOU - continua tentando cortar")
