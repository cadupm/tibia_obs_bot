# -*- coding: utf-8 -*-
"""Parede no kite: nao insistir na tecla que nao anda.

Nao se reconhece parede na tela - mede-se o resultado. Depois de cada passo, se
o personagem nao saiu do lugar, aquele lado fica bloqueado por um tempo e o kite
escolhe outro. Sem isso o bot martela a mesma tecla contra a pedra para sempre,
porque nada na tela muda para ele decidir diferente.

O mundo daqui tem uma parede a esquerda: a tecla 'left' nunca move.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

main.KITE_DIAGONAIS = False
main.KITE_BLOQUEIO = 1.0
main.KITE_BLOQUEIO_MAX = 30.0

PAREDE = {"left"}                          # o unico lado que nao anda
relogio = {"t": 0.0}
mundo = {"pos": [0, 0]}
teclas = []


class Janela:
    isActive = True
    title = "falso"


class OdoFalso:
    """Odometro de mentira: a posicao so muda se a tecla nao foi para a parede."""

    def __init__(self):
        self.pos = mundo["pos"]
        self.parado = 9

    def atualiza(self):
        pass


def press(tecla):
    """
    Aperta a tecla. O movimento NAO e instantaneo: o personagem leva um tempo
    para andar, e a leitura seguinte pode pegar ele no meio do passo - e por
    isso que uma falha sozinha nao pode contar como parede.
    """
    teclas.append((round(relogio["t"], 1), tecla))
    if tecla in PAREDE:
        return                             # bate na pedra: nao anda
    mundo["andando"] = main.KITE_PASSOS[tecla]


def passa_o_tempo():
    """O passo que estava em andamento se completa aqui."""
    andando = mundo.pop("andando", None)
    if andando:
        mundo["pos"][0] += andando[0] * 2  # 2 px de minimapa por SQM
        mundo["pos"][1] += andando[1] * 2


def viewport_com_bicho(dx, dy):
    """Bicho no offset pedido, com a moldura da barra como o jogo desenha."""
    _vx, _vy, vw, vh = main.GAME_VIEW
    img = np.full((vh, vw, 3), 30, dtype=np.uint8)
    meio_col, meio_lin = (vw // main.TILE_PX) // 2, (vh // main.TILE_PX) // 2
    x = (meio_col + dx) * main.TILE_PX + 18
    y = (meio_lin + dy - main.CREATURE_BAR_ABOVE) * main.TILE_PX + 10
    img[y:y + 4, x:x + 31] = (0, 0, 0)
    img[y + 1:y + 3, x + 1:x + 30] = (0, 95, 0)
    return img


# o bicho fica colado a DIREITA: o passo natural e para a esquerda, que e parede
TELA = viewport_com_bicho(1, 0)

main.grab = lambda regiao: TELA
main.client_rect = lambda win: (0, 0, 1920, 1009)
main.focus_window = lambda win: True
main.pyautogui = type("P", (), {"press": staticmethod(press)})()
main.time = type("T", (), {"time": staticmethod(lambda: relogio["t"]),
                           "sleep": staticmethod(lambda s: None)})()


class SemEspera:
    """Cooldown que esta sempre pronto: o teste controla o relogio."""

    def ready(self):
        return True

    def mark(self):
        pass


odo, estado = OdoFalso(), {}
print("bicho colado a direita; parede a esquerda (a tecla 'left' nao anda)\n")
for passo in range(24):
    relogio["t"] += 0.4
    passa_o_tempo()                        # o passo anterior termina agora
    main.kite(Janela(), Janela(), SemEspera(), {}, odo=odo, estado=estado)
    print(f"  t={relogio['t']:.1f}  teclas ate agora: "
          f"{[t for _q, t in teclas]}  posicao={tuple(mundo['pos'])}")

dadas = [t for _q, t in teclas]
falhas = []
if not dadas:
    falhas.append("nao tentou andar")
# Descobrir a parede custa KITE_FALHAS tentativas, e a espera crescente faz o
# custo parar de crescer: o que se exige e que os passos bons dominem, e que na
# ultima parte da corrida ele nao esteja mais martelando a pedra.
bons = [t for t in dadas if t != "left"]
if len(bons) < 2 * dadas.count("left"):
    falhas.append(f"{dadas.count('left')} tentativas na parede contra "
                  f"{len(bons)} passos bons: insiste demais")
ultimo_terco = dadas[2 * len(dadas) // 3:]
if ultimo_terco.count("left") > 1:
    falhas.append(f"no fim da corrida ainda tentou a parede "
                  f"{ultimo_terco.count('left')}x")
if not any(t != "left" for t in dadas):
    falhas.append("nunca tentou outro lado")
if tuple(mundo["pos"]) == (0, 0):
    falhas.append("nao saiu do lugar em nenhum passo")

print(f"\ntentou 'left' (parede) {dadas.count('left')}x, "
      f"outros lados {sum(1 for t in dadas if t != 'left')}x")
print(f"posicao final: {tuple(mundo['pos'])} (em px de minimapa, 2 = 1 SQM)")
print(f"lados bloqueados no fim: {list(estado.get('bloqueados', {}))}")
print("VEREDITO:", "OK - desiste do lado que nao anda e acha outro"
      if not falhas else "FALHOU: " + "; ".join(falhas))
