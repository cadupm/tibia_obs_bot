# -*- coding: utf-8 -*-
"""Depois que TODAS as bandeiras ja foram visitadas.

E o estado em que o bot vive na pratica (o log do usuario so mostra "0 nova(s)").
Aqui se mede o que quebrava: alvo escolhido na beirada do minimapa, que sai de
vista no meio do caminho e faz o bot trocar de rumo a cada dois passos.
"""
import io, math, os, random, sys
from contextlib import redirect_stdout
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

random.seed(int(os.environ.get("SEMENTE", "1")))
VEL, RAIO = 2, 52
R = 34
ANG = [-100, -75, -50, -25, 0, 25, 50, 75, 100]
NOMES = ["P1", "P2", "P3", "P4", "ENT", "P5", "P6", "P7", "P8"]
CAMINHO = [(round(R * math.cos(math.radians(a))),
            round(R * math.sin(math.radians(a)))) for a in ANG]
MARCAS = dict(zip(NOMES, CAMINHO))


class Mundo:
    def __init__(self):
        self.acumulado = [0.0]
        for i in range(1, len(CAMINHO)):
            self.acumulado.append(self.acumulado[-1]
                                  + math.dist(CAMINHO[i - 1], CAMINHO[i]))
        self.t = self.acumulado[4]
        self.destino = None
        self.pedra = 0

    @property
    def pos(self):
        for i in range(1, len(self.acumulado)):
            if self.t <= self.acumulado[i]:
                a, b = CAMINHO[i - 1], CAMINHO[i]
                f = ((self.t - self.acumulado[i - 1])
                     / (self.acumulado[i] - self.acumulado[i - 1]))
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
    mundo.destino = mundo.acumulado[i]


main.detect_marks, main.click_minimap = visiveis, clica

odo, estado, cd = Odo(), {}, main.Cooldown(0)
nome = lambda p: next((n for n, m in MARCAS.items() if math.dist(m, p) <= 4), "?")

visitas, antes, alvos = [], 0, []
saida = io.StringIO()
with redirect_stdout(saida):
    for _ in range(20000):
        mundo.anda()
        alvo_antes = estado.get("alvo_off")
        main.follow_marks(None, odo, estado, cd)
        alvo = estado.get("alvo_off")
        if alvo is not None and alvo != alvo_antes and estado.get("cliques", 0) == 0:
            alvos.append(abs(alvo[0]) + abs(alvo[1]))
        if estado.get("ordem", 0) != antes:
            antes = estado["ordem"]
            visitas.append(nome(mundo.pos))
        if len(visitas) >= 60:
            break

import re
log = saida.getvalue()
por_motivo = {}
for achado in re.finditer(r"alvo: bandeira em \((-?\d+), (-?\d+)\) \(([^)]+)\)", log):
    d = abs(int(achado.group(1))) + abs(int(achado.group(2)))
    por_motivo.setdefault(achado.group(3), []).append(d)
for motivo, ds in sorted(por_motivo.items()):
    print(f"  {motivo}: {len(ds)} escolha(s), media {sum(ds)/len(ds):.0f} px, "
          f"maior {max(ds)} px")
perdidas = log.count("sumiu da tela")
espacamento = min(math.dist(CAMINHO[i], CAMINHO[i + 1])
                  for i in range(len(CAMINHO) - 1))
print("visitas:", " ".join(visitas[:40]), "...")
print(f"bandeiras conhecidas: {len(estado.get('visitadas', {}))} (existem 9)")
print(f"distancia dos alvos escolhidos: media {sum(alvos)/len(alvos):.0f} px, "
      f"maior {max(alvos)} px (vizinha fica a ~{espacamento:.0f} px)")
print(f"alvos perdidos de vista: {perdidas} | cliques em parede: {mundo.pedra}")
inversoes = [visitas[i] for i in range(1, len(visitas) - 1)
             if visitas[i - 1] == visitas[i + 1] and visitas[i] not in ("P1", "P8")]
print("inversoes fora das pontas:", inversoes)
# o limite de vizinhanca vale para o regime permanente (tudo ja visitado);
# na descoberta, ir buscar uma bandeira nova longe E a regra
rotina = [d for motivo, ds in por_motivo.items()
          if "ainda nao visitada" not in motivo for d in ds] or [0]
ok = (max(rotina) <= espacamento * main.MARK_ADJ * 2 and perdidas == 0
      and not inversoes and mundo.pedra == 0)
print(f"maior alvo no regime permanente: {max(rotina)} px "
      f"(limite {espacamento * main.MARK_ADJ * 2:.0f})")
print("VEREDITO:", "OK" if ok else "FALHOU")
