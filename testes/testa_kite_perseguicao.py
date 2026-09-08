# -*- coding: utf-8 -*-
"""Bicho que corre com pouca vida: o bot tem de ir atras, e rapido.

Fechar 6 quadrados de seta sao 6 teclas a KITE_COOLDOWN cada, e cada seta
esbarra sozinha em cada pedra do caminho. Para trecho longo o bot clica no mapa:
anda o trecho inteiro com o desvio de parede do proprio cliente. De perto ele
volta para a seta, que e o que da controle fino.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

main.KITE_DIAGONAIS = False
D, PERTO_DEMAIS = main.KITE_DIST, main.KITE_DIST + main.KITE_CLIQUE
acoes = []


class Janela:
    isActive = True
    title = "falso"


class OdoFalso:
    """`parado` alto = personagem parado, que e quando o clique pode sair."""

    def __init__(self, parado=9):
        self.pos = [0, 0]
        self.parado = parado

    def atualiza(self):
        pass


class SemEspera:
    def ready(self):
        return True

    def mark(self):
        pass


def viewport_com_bicho(dx, dy):
    _vx, _vy, vw, vh = main.GAME_VIEW
    img = np.full((vh, vw, 3), 30, dtype=np.uint8)
    meio_col, meio_lin = (vw // main.TILE_PX) // 2, (vh // main.TILE_PX) // 2
    x = (meio_col + dx) * main.TILE_PX + 18
    y = (meio_lin + dy - main.CREATURE_BAR_ABOVE) * main.TILE_PX + 10
    img[y:y + 4, x:x + 31] = (0, 0, 0)
    img[y + 1:y + 3, x + 1:x + 30] = (0, 95, 0)
    return img


main.client_rect = lambda win: (0, 0, 1920, 1009)
main.focus_window = lambda win: True
main.pyautogui = type("P", (), {
    "press": staticmethod(lambda t: acoes.append(("tecla", t)))})()
main.click_minimap = lambda win, passo: acoes.append(("clique", passo))
main.time = type("T", (), {"time": staticmethod(lambda: 0.0),
                           "sleep": staticmethod(lambda s: None)})()

print(f"distancia pedida: {D} SQM | clique a partir de {PERTO_DEMAIS} SQM")
print(f"escala do minimapa: {main.MINIMAP_PX_SQM} px por SQM\n")

# O viewport tem 15x11 quadrados, entao a tela so alcanca 7 SQM na horizontal e
# 5 na vertical (e a barra e desenhada um quadrado acima, o que tira uma linha).
# Bicho mais longe que isso nao aparece: nao ha o que perseguir.
CASOS = [
    ("colado", (1, 0), "tecla"),
    (f"na distancia ({D})", (D, 0), None),
    (f"um pouco longe ({D + 1})", (D + 1, 0), "tecla"),
    (f"correu ({PERTO_DEMAIS})", (PERTO_DEMAIS, 0), "clique"),
    ("correu para a beirada (7)", (7, 0), "clique"),
    ("correu na diagonal", (5, -3), "clique"),
]
falhas = []
for nome, onde, esperado in CASOS:
    acoes.clear()
    main.grab = lambda regiao, _t=viewport_com_bicho(*onde): _t
    main.kite(Janela(), Janela(), SemEspera(), {}, odo=OdoFalso(), estado={})
    feito = acoes[0] if acoes else None
    print(f"  {nome:24} bicho em {str(onde):9} -> "
          f"{feito if feito else 'nao se moveu'}")
    tipo = feito[0] if feito else None
    if tipo != esperado:
        falhas.append(f"{nome}: esperava {esperado}, saiu {tipo}")

# o clique tem de parar A DISTANCIA PEDIDA do bicho, nao em cima dele
acoes.clear()
LONGE = 7                            # o mais longe que a tela alcanca de lado
main.grab = lambda regiao, _t=viewport_com_bicho(LONGE, 0): _t
main.kite(Janela(), Janela(), SemEspera(), {}, odo=OdoFalso(), estado={})
_tipo, passo = acoes[0]
andaria = passo[0] / main.MINIMAP_PX_SQM
print(f"\n  bicho a {LONGE} SQM: clique andaria {andaria:.0f} SQM, "
      f"parando a {LONGE - andaria:.0f} do bicho")
if abs((LONGE - andaria) - D) > 1:
    falhas.append(f"o clique pararia a {LONGE - andaria:.0f} SQM do bicho, "
                  f"nao a {D}")

# ------------------------------- o clique tem de deixar o trajeto TERMINAR
# Clique no mapa e um trajeto inteiro; clicar de novo no meio dele cancela o
# anterior e o personagem anda aos centimetros. Andando, so se clica de novo
# depois de KITE_CLIQUE_ESPERA.
print("\ncom o personagem ANDANDO (trajeto em curso):")
relogio = {"t": 100.0}
main.time = type("T", (), {"time": staticmethod(lambda: relogio["t"]),
                           "sleep": staticmethod(lambda s: None)})()
main.grab = lambda regiao, _t=viewport_com_bicho(7, 0): _t
estado = {}
andando = OdoFalso(parado=0)

acoes.clear()
main.kite(Janela(), Janela(), SemEspera(), {}, odo=andando, estado=estado)
print(f"  primeiro clique: {acoes}")
if not acoes:
    falhas.append("nao clicou nem na primeira vez")

acoes.clear()
relogio["t"] += 0.4                        # ainda no meio do trajeto
main.kite(Janela(), Janela(), SemEspera(), {}, odo=andando, estado=estado)
print(f"  0,4s depois, ainda andando: {acoes or 'nao clicou (certo)'}")
if acoes:
    falhas.append("clicou de novo no meio do trajeto, cancelando o anterior")

acoes.clear()
relogio["t"] += main.KITE_CLIQUE_ESPERA     # travou no caminho
main.kite(Janela(), Janela(), SemEspera(), {}, odo=andando, estado=estado)
print(f"  {main.KITE_CLIQUE_ESPERA}s depois, sem ter parado: "
      f"{acoes or 'nao clicou'}")
if not acoes:
    falhas.append("travado no caminho e nao clicou de novo")

acoes.clear()
relogio["t"] += 0.1
main.kite(Janela(), Janela(), SemEspera(), {}, odo=OdoFalso(parado=9),
          estado=estado)
print(f"  personagem PARADO: {acoes or 'nao clicou'}")
if not acoes:
    falhas.append("personagem parado e nao clicou")

print("\nVEREDITO:", "OK - persegue de clique longe e de seta perto"
      if not falhas else "FALHOU: " + "; ".join(falhas))
