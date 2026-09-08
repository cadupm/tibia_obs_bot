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
main.client_rect = lambda win: (0, 0, 1920, 1009)
# a tecla de saque age sobre o que esta DEBAIXO DO CURSOR: o teste registra
# para onde o bot mirou e confere que foi no quadrado do corpo
mirado = []
main.mira_mouse = lambda x, y: mirado.append((x, y))
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

# ---------------------------- 6) mirar o cursor no corpo antes de apertar
# A tecla de saque rapido age sobre o que esta DEBAIXO DO CURSOR: sem mirar, ela
# sai com o mouse onde quer que ele tenha ficado - em geral sobre o minimapa, do
# ultimo clique de rota - e nao pega nada.
odo.pos = [0, 0]
estado = {}
main.marca_o_corpo(estado, (1, 0), odo)
mirado.clear()
main.loot(Janela(), Janela(), estado, SemEspera(), odo)
esperado = main.ponto_do_quadrado(Janela(), (1, 0))
print(f"\nmirou em {mirado[:1]}, quadrado do corpo em {esperado}")
if not mirado:
    falhas.append("apertou a tecla sem mirar o cursor no corpo")
elif mirado[0] != esperado:
    falhas.append(f"mirou em {mirado[0]}, o corpo esta em {esperado}")

# ------------- 7) o corpo nao envelhece: desconta o caminho andado ate a morte
estado = {}
odo.pos = [6, 0]                       # andou 3 SQM desde que viu o bicho
main.marca_o_corpo(estado, (4, 0), odo, visto_em=(0, 0))
print(f"viu o bicho a 4 SQM e andou 3 na direcao dele -> corpo em "
      f"{estado['loot_onde']}")
if abs(estado["loot_onde"][0] - 1) > 0.1:
    falhas.append(f"nao descontou o caminho andado: {estado['loot_onde']} "
                  f"(esperava perto de (1, 0))")

print("\nVEREDITO:", "OK - vai ate o corpo, saqueia e volta para a rota"
      if not falhas else "FALHOU: " + "; ".join(falhas))
