# -*- coding: utf-8 -*-
"""Pegar o loot do bicho que acabou de morrer.

A tecla de saque rapido do cliente resolve o saque em si; o que o bot tem de
fazer e CHEGAR PERTO. Em stand o personagem ja esta colado no corpo; em kite ele
esta a KITE_DIST de distancia. E o corpo nao tem barra de vida: o que se guarda,
no momento da morte, e onde o bicho estava.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import main

acoes = []
relogio = {"t": 100.0}


class Janela:
    isActive = True
    title = "falso"


class Odo:
    """Anda quando o clique manda, como o cliente faria."""

    def __init__(self):
        self.pos = [0, 0]
        self.parado = 9

    def atualiza(self):
        pass


class SemEspera:
    def ready(self):
        return True

    def mark(self):
        pass


odo = Odo()


def clica(_win, passo):
    acoes.append(("clique", passo))
    odo.pos[0] += passo[0]                 # o personagem chega onde clicou
    odo.pos[1] += passo[1]


main.click_minimap = clica
main.focus_window = lambda win: True
main.pyautogui = type("P", (), {
    "press": staticmethod(lambda t: acoes.append(("tecla", t)))})()
main.time = type("T", (), {"time": staticmethod(lambda: relogio["t"]),
                           "sleep": staticmethod(lambda s: None)})()

falhas = []
print(f"tecla de saque: {main.LOOT_HOTKEY!r} | alcance: {main.LOOT_DIST} SQM | "
      f"apertadas por corpo: {main.LOOT_TENTATIVAS}\n")

# ----------------------------------------- 1) em stand: o corpo esta colado
estado = {}
main.marca_o_corpo(estado, (1, 0), odo)
acoes.clear()
for _ in range(6):
    relogio["t"] += 0.5
    if not main.loot(Janela(), Janela(), estado, SemEspera(), odo):
        break
teclas = [a for a in acoes if a[0] == "tecla"]
cliques = [a for a in acoes if a[0] == "clique"]
print(f"corpo colado (1 SQM): {len(teclas)} apertada(s), "
      f"{len(cliques)} clique(s)")
if len(teclas) != main.LOOT_TENTATIVAS:
    falhas.append(f"colado: {len(teclas)} apertadas, esperava "
                  f"{main.LOOT_TENTATIVAS}")
if cliques:
    falhas.append("colado: andou sem precisar")

# --------------------------------- 2) em kite: o corpo esta a 4 SQM, precisa ir
odo.pos = [0, 0]
estado = {}
main.marca_o_corpo(estado, (4, 0), odo)
acoes.clear()
for _ in range(10):
    relogio["t"] += 0.5
    if not main.loot(Janela(), Janela(), estado, SemEspera(), odo):
        break
teclas = [a for a in acoes if a[0] == "tecla"]
cliques = [a for a in acoes if a[0] == "clique"]
print(f"corpo a 4 SQM:       {len(teclas)} apertada(s), "
      f"{len(cliques)} clique(s) {[c[1] for c in cliques]}")
print(f"  posicao final do personagem: {tuple(odo.pos)} "
      f"(em px de minimapa, {main.MINIMAP_PX_SQM} = 1 SQM)")
if not cliques:
    falhas.append("longe: nao andou ate o corpo")
if len(teclas) != main.LOOT_TENTATIVAS:
    falhas.append(f"longe: {len(teclas)} apertadas, esperava "
                  f"{main.LOOT_TENTATIVAS}")

# ------------------------------- 3) o corpo nao anda: o offset acompanha o char
odo.pos = [0, 0]
estado = {}
main.marca_o_corpo(estado, (4, 0), odo)
odo.pos = [4, 0]                           # o personagem andou 2 SQM sozinho
main.loot(Janela(), Janela(), estado, SemEspera(), odo)
print(f"\nandando 2 SQM na direcao do corpo, o offset dele virou "
      f"{estado['loot_onde']}")
if abs(estado["loot_onde"][0] - 2) > 0.1:
    falhas.append(f"o offset do corpo nao acompanhou o personagem: "
                  f"{estado['loot_onde']}")

# --------------------------------------------- 4) prazo: nao trava a cacada
odo.pos = [0, 0]
estado = {}
main.marca_o_corpo(estado, (6, 0), odo)
main.click_minimap = lambda _w, _p: acoes.append(("clique", _p))   # nao anda
acoes.clear()
relogio["t"] += main.LOOT_PRAZO + 1
segue = main.loot(Janela(), Janela(), estado, SemEspera(), odo)
print(f"passado o prazo de {main.LOOT_PRAZO:.0f}s sem chegar: "
      f"{'desistiu' if not segue else 'ainda insistindo'}")
if segue or estado.get("loot_onde") is not None:
    falhas.append("nao desistiu do corpo inalcancavel")

# ------------------------------------------- 5) desligado nao faz nada
main.ENABLE_LOOT = False
estado = {}
main.marca_o_corpo(estado, (1, 0), odo)
acoes.clear()
print(f"com ENABLE_LOOT desligado: guardou corpo? "
      f"{estado.get('loot_onde') is not None}, agiu? {bool(acoes)}")
if estado.get("loot_onde") is not None or acoes:
    falhas.append("desligado e mesmo assim mexeu")
main.ENABLE_LOOT = True

print("\nVEREDITO:", "OK - vai ate o corpo, saqueia e volta para a rota"
      if not falhas else "FALHOU: " + "; ".join(falhas))
