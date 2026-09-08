# -*- coding: utf-8 -*-
"""Paralisia: reconhecer e curar.

No Tibia a paralisia derruba a velocidade a quase zero, e sai de duas formas:
qualquer magia de cura remove, e haste (utani hur) sobrepoe a velocidade. Os
bichos desta cave - bonelord, gazer - paralisam.

Do ponto de vista do bot, paralisado e identico a bater na pedra: manda o passo
e nao sai do lugar. O que separa os dois e QUANTOS lados falham - pedra e de um
lado, paralisia e de todos. Este teste mede exatamente essa distincao.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

main.KITE_DIAGONAIS = False
main.KITE_BLOQUEIO = 5.0
main.PARALISIA_LADOS = 3
apertadas = []
relogio = {"t": 0.0}


class Janela:
    isActive = True
    title = "falso"


class OdoTravado:
    """Nunca sai do lugar: e o que a paralisia faz, e o que a pedra faz."""

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
    "press": staticmethod(lambda t: apertadas.append(t))})()
main.click_minimap = lambda w, p: None
main.time = type("T", (), {"time": staticmethod(lambda: relogio["t"]),
                           "sleep": staticmethod(lambda s: None)})()
main.grab = lambda regiao, _t=viewport_com_bicho(1, 0): _t

falhas = []
print(f"magia que cura: {main.PARALISIA_HOTKEY!r} | "
      f"lados travados para suspeitar: {main.PARALISIA_LADOS}\n")


class SemEsperaCura:
    """Cooldown da cura, controlado pelo teste."""

    def __init__(self):
        self.pronto = True

    def ready(self):
        return self.pronto

    def mark(self):
        self.pronto = False


# ------------------------------- 1) UM lado travado: e pedra, nao paralisia
estado = {"bloqueados": {"left": 100.0}}
relogio["t"] = 1.0
apertadas.clear()
curou = main.cura_paralisia(Janela(), estado, SemEsperaCura())
print(f"1 lado travado (pedra):        conjurou? {curou}")
if curou:
    falhas.append("conjurou com um lado so travado - isso e pedra")

# ------------------------------- 2) TODOS travados: paralisia
estado = {"bloqueados": {"left": 100.0, "right": 100.0, "up": 100.0,
                         "down": 100.0}}
apertadas.clear()
curou = main.cura_paralisia(Janela(), estado, SemEsperaCura())
print(f"4 lados travados (paralisia):  conjurou? {curou} "
      f"{apertadas}")
if not curou:
    falhas.append("nao conjurou com todos os lados travados")
if apertadas != [main.PARALISIA_HOTKEY]:
    falhas.append(f"apertou {apertadas}, esperava [{main.PARALISIA_HOTKEY!r}]")
if estado["bloqueados"]:
    falhas.append("deixou os bloqueios de pe: o bot passaria os proximos "
                  "segundos achando que esta cercado de parede")
print(f"  bloqueios depois da cura: {estado['bloqueados']} (tem de ficar vazio)")

# --------------------- 3) o caminho inteiro pelo kite: travado em todos os lados
print("\npelo laco do kite, com o personagem sem sair do lugar:")
odo, estado = OdoTravado(), {}
apertadas.clear()
cura_cd = SemEsperaCura()
for volta in range(14):
    relogio["t"] += 0.5
    main.kite(Janela(), Janela(), SemEspera(), {}, odo=odo, estado=estado)
    if main.cura_paralisia(Janela(), estado, cura_cd):
        print(f"  na volta {volta}: {len(estado.get('bloqueados', {}))} "
              f"bloqueios -> conjurou {main.PARALISIA_HOTKEY}")
        break
else:
    falhas.append("o kite travou em todos os lados e a cura nunca saiu")
print(f"  teclas apertadas ate ai: {apertadas}")
if main.PARALISIA_HOTKEY not in apertadas:
    falhas.append("a magia de cura nao foi conjurada")

# ------------------------------- 4) desligado nao conjura
main.ENABLE_PARALISIA = False
estado = {"bloqueados": {"left": 100.0, "right": 100.0, "up": 100.0}}
apertadas.clear()
curou = main.cura_paralisia(Janela(), estado, SemEsperaCura())
print(f"\ncom ENABLE_PARALISIA desligado: conjurou? {curou}")
if curou:
    falhas.append("desligado e mesmo assim conjurou")
main.ENABLE_PARALISIA = True

print("\nVEREDITO:", "OK - separa pedra de paralisia e conjura a cura"
      if not falhas else "FALHOU: " + "; ".join(falhas))
