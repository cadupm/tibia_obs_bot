# -*- coding: utf-8 -*-
"""Regra de ouro com rastreio visual: o personagem anda de verdade (2 px por
leitura, como no jogo) e a odometria e proposital lixo, para provar que ela nao
participa mais da decisao."""
import random
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

random.seed(7)
RAIO = 52                      # metade do minimapa, em px
VEL = 2                        # px por leitura (1 sqm)


class Odo:
    """Odometria de proposito ruim: erra ate 6 px por leitura. `parado` e o
    unico dado dela que ainda importa - so se clica com o personagem parado."""
    def __init__(self, mundo):
        self.pos, self.mundo = [0, 0], mundo

    @property
    def parado(self):
        return 0 if self.mundo["indo"] else 9

    def atualiza(self):
        self.pos[0] += random.randint(-6, 6)
        self.pos[1] += random.randint(-6, 6)

    def ancora(self, alvo):
        pass


def roda(nome_do_teste, marcas, passos=4000, alvo_visitas=14):
    mundo = {"pos": [0.0, 0.0], "indo": None, "pedra": 0}

    def visiveis(win, mm=None, cor=None):
        px, py = mundo["pos"]
        vistas = [(int(round(m[0] - px)), int(round(m[1] - py)))
                  for m in marcas.values()]
        return sorted([v for v in vistas
                       if abs(v[0]) <= RAIO and abs(v[1]) <= RAIO],
                      key=lambda m: abs(m[0]) + abs(m[1]))

    def clica(win, passo):
        destino = (mundo["pos"][0] + passo[0], mundo["pos"][1] + passo[1])
        perto = min(marcas.values(),
                    key=lambda m: abs(m[0] - destino[0]) + abs(m[1] - destino[1]))
        if abs(perto[0] - destino[0]) + abs(perto[1] - destino[1]) > main.MARK_MERGE:
            mundo["pedra"] += 1     # clicou em parede: nao anda
            return
        mundo["indo"] = perto

    def anda():
        """Vai em linha ate o destino, 2 px por leitura, um eixo de cada vez."""
        alvo = mundo["indo"]
        if not alvo:
            return
        for i in (0, 1):
            d = alvo[i] - mundo["pos"][i]
            if abs(d) >= 0.01:
                mundo["pos"][i] += max(-VEL, min(VEL, d))
                break
        if abs(alvo[0] - mundo["pos"][0]) + abs(alvo[1] - mundo["pos"][1]) < 0.01:
            mundo["indo"] = None

    main.detect_marks, main.click_minimap = visiveis, clica
    odo, estado, cd = Odo(mundo), {}, main.Cooldown(0)

    def nome(p):
        return next((n for n, m in marcas.items()
                     if abs(m[0] - p[0]) + abs(m[1] - p[1]) <= 3), "?")

    visitas, antes = [], 0
    for _ in range(passos):
        odo.atualiza()
        anda()
        main.follow_marks(None, odo, estado, cd)
        if estado.get("ordem", 0) != antes:
            antes = estado["ordem"]
            visitas.append(nome(mundo["pos"]))
        if len(visitas) >= alvo_visitas:
            break

    inversoes = sum(1 for i in range(1, len(visitas) - 1)
                    if visitas[i - 1] == visitas[i + 1])
    print(f"\n=== {nome_do_teste}")
    print("  marcas: ", {n: m for n, m in marcas.items()})
    print("  visitas:", " ".join(visitas))
    print(f"  cliques em parede: {mundo['pedra']} | inversoes: {inversoes}")
    return visitas, mundo["pedra"]


# 1) corredor com a entrada no meio: vai ate uma ponta, volta e vai ate a outra
vis, pedra = roda("corredor com entrada no meio",
                  {"C": (0, -40), "B": (0, -20), "A": (0, 0),
                   "D": (0, 20), "E": (0, 40)})
seq = "".join(vis)
ok1 = ("BC" in seq and "DE" in seq and pedra == 0
       and "CB" in seq and "ED" in seq)
print("  VEREDITO:", "OK - varreu as duas pontas" if ok1 else "FALHOU")

# A caverna em "O" fica no testa_caverna_c.py: aqui o boneco atravessaria a
# pedra entre os dois bracos, o que o jogo nao deixa, e o teste mediria fantasia.
