# -*- coding: utf-8 -*-
"""Rota gravada: o bot tem de seguir a ORDEM, nao decidir nada.

Percurso do usuario: entra pelo meio, desce ate a ponta, volta passando pela
entrada e vai ate a outra ponta. Aqui a rota ja esta gravada e o bot so obedece.
O teste comeca o bot NO MEIO da rota, com uma briga no caminho, e confere se a
sequencia sai exatamente na ordem gravada.
"""
import io, math, os, random, sys
from contextlib import redirect_stdout
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

random.seed(int(os.environ.get("SEMENTE", "2")))
VEL, RAIO = 2, 52
R = 34
ANG = [-100, -75, -50, -25, 0, 25, 50, 75, 100]
NOMES = ["P1", "P2", "P3", "P4", "ENT", "P5", "P6", "P7", "P8"]
LUGAR = [(round(R * math.cos(math.radians(a))),
          round(R * math.sin(math.radians(a)))) for a in ANG]
MARCAS = dict(zip(NOMES, LUGAR))

# a ordem que a pessoa gravou clicando nas marcas
ORDEM = ["ENT", "P4", "P3", "P2", "P1", "P2", "P3", "P4",
         "ENT", "P5", "P6", "P7", "P8", "P7", "P6", "P5"]
ROTA = [MARCAS[n] for n in ORDEM]


class Mundo:
    def __init__(self, comeco):
        self.acum = [0.0]
        for i in range(1, len(LUGAR)):
            self.acum.append(self.acum[-1] + math.dist(LUGAR[i - 1], LUGAR[i]))
        self.t = self.acum[comeco]
        self.destino = None
        self.pedra = 0

    @property
    def pos(self):
        for i in range(1, len(self.acum)):
            if self.t <= self.acum[i]:
                a, b = LUGAR[i - 1], LUGAR[i]
                f = (self.t - self.acum[i - 1]) / (self.acum[i] - self.acum[i - 1])
                return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
        return LUGAR[-1]

    def anda(self):
        if self.destino is None:
            return (0.0, 0.0)
        antes = self.pos
        d = self.destino - self.t
        self.t += max(-VEL, min(VEL, d))
        if abs(self.destino - self.t) < 0.01:
            self.t, self.destino = self.destino, None
        agora = self.pos
        return (agora[0] - antes[0], agora[1] - antes[1])


mundo = Mundo(comeco=6)          # comeca em P7, no meio da rota


class Odo:
    def __init__(self):
        self.pos = [0.0, 0.0]

    @property
    def parado(self):
        return 0 if mundo.destino is not None else 9

    def anda(self, d):
        self.pos[0] += d[0] * (1 + random.uniform(-0.1, 0.1))
        self.pos[1] += d[1] * (1 + random.uniform(-0.1, 0.1))

    def atualiza(self):
        pass

    def ancora(self, alvo):
        pass


odo = Odo()


def visiveis(win, mm=None, cor=None):
    px, py = mundo.pos
    vistas = [(int(round(m[0] - px)), int(round(m[1] - py))) for m in LUGAR]
    return sorted([v for v in vistas if abs(v[0]) <= RAIO and abs(v[1]) <= RAIO],
                  key=lambda m: abs(m[0]) + abs(m[1]))


def clica(win, passo):
    px, py = mundo.pos
    destino = (px + passo[0], py + passo[1])
    i = min(range(len(LUGAR)), key=lambda k: math.dist(LUGAR[k], destino))
    if math.dist(LUGAR[i], destino) > main.MARK_MERGE:
        mundo.pedra += 1
        return
    mundo.destino = mundo.acum[i]


main.detect_marks, main.click_minimap = visiveis, clica

estado = {"rota": list(ROTA)}
cd = main.Cooldown(0)
nome = lambda p: next((n for n, m in MARCAS.items() if math.dist(m, p) <= 4), "?")

chegadas, indice_antes, lutando, brigas = [], None, 0, 0
saida = io.StringIO()
with redirect_stdout(saida):
    for _ in range(30000):
        odo.anda(mundo.anda())
        if not lutando and random.random() < 1 / 40:
            lutando, brigas = random.randint(10, 60), brigas + 1
            mundo.destino = None
            estado["cliques"] = 0
        if lutando:
            lutando -= 1
            main.track_marks(None, estado, andando=False, odo=odo)
        else:
            main.follow_route(None, odo, estado, cd)
        i = estado.get("indice")
        if i != indice_antes and indice_antes is not None:
            chegadas.append(nome(mundo.pos))
        indice_antes = i
        if len(chegadas) >= 20:
            break

log = saida.getvalue()
inicio = log[log.index("[rota] me localizei"):].splitlines()[0] if \
    "me localizei" in log else "(nao se localizou)"
print("\nordem gravada:", " ".join(ORDEM))
print("comecou em P7 (meio da rota)")
print(inicio)
print("chegadas:", " ".join(chegadas))
print(f"brigas no caminho: {brigas} | cliques em parede: {mundo.pedra} | "
      f"pontos pulados: {log.count('pulo para o')}")

# a sequencia tem de casar com a ordem gravada, a partir de onde ele entrou
esperado = None
for comeco in range(len(ORDEM)):
    tentativa = [ORDEM[(comeco + k) % len(ORDEM)] for k in range(len(chegadas))]
    if tentativa == chegadas:
        esperado = comeco
        break
print("VEREDITO:", f"OK - seguiu a ordem gravada (entrou no ponto {esperado + 1})"
      if esperado is not None else "FALHOU - saiu da ordem")
