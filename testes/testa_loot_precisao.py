# -*- coding: utf-8 -*-
"""Chegar no corpo sem passar dele.

Relatado em cacada: "vai na direcao certa mas passa a mais muitas vezes". A
causa e o caminho usado para chegar. Havia dois candidatos:

  MINIMAPA: o passo em SQM e convertido em pixel por MINIMAP_PX_SQM - um numero
  que se mede a mao com --zoom e que muda com o zoom do jogo. Cada clique pede
  um deslocamento em pixel de minimapa, e o quanto isso vale em SQM depende
  dessa calibracao estar certa.

  TELA DO JOGO: o quadrado tem TILE_PX de lado e o pixel do centro dele sai de
  uma conta fechada - meio da grade mais o offset, vezes TILE_PX. Nao ha escala
  para errar, e o cliente acha o caminho. Errar exige que GAME_VIEW ou TILE_PX
  estejam errados, e para esses ha --kite, que desenha a grade num PNG.

Este teste mede o que da para medir sem o jogo:
  - o clique de aproximacao cai no PIXEL do quadrado do corpo, para qualquer
    offset dentro da tela;
  - fora da area do jogo nao ha quadrado para clicar, e o minimapa assume;
  - o caminho pela tela NAO LE MINIMAP_PX_SQM: mudando a escala, o clique cai
    no mesmo pixel. Caminho que nao depende de calibracao nao erra por causa
    dela.

O que NAO da para medir aqui e o "passou do corpo" em si: quanto o personagem
anda por clique e coisa do cliente. A primeira versao deste arquivo tentou, com
um minimapa de mentira, e nao mediu nada - o falso andava pela escala
CONFIGURADA, entao a conta fechava sempre.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import main

acoes = []
relogio = {"t": 100.0}


class Janela:
    isActive = True
    title = "falso"


class Odo:
    def __init__(self):
        self.pos = [0, 0]
        self.parado = 9

    def atualiza(self):
        pass


class Livre:
    def ready(self):
        return True

    def mark(self):
        pass


odo = Odo()


def clica_minimapa(_win, passo):
    """Registra o clique de minimapa e leva o personagem ao ponto pedido."""
    acoes.append(("mapa", passo))
    odo.pos[0] += passo[0]
    odo.pos[1] += passo[1]


def clica_jogo(x, y, pausa=0.09, botao="esquerdo", mod=""):
    """Clique na tela do jogo: o cliente leva o personagem AO QUADRADO."""
    acoes.append(("jogo", botao, (x, y)))
    if botao == "esquerdo":
        off = ponto_para_off((x, y))
        odo.pos[0] += off[0] * main.MINIMAP_PX_SQM
        odo.pos[1] += off[1] * main.MINIMAP_PX_SQM


def ponto_para_off(p):
    vx, vy, vw, vh = main.GAME_VIEW
    mc, ml = (vw // main.TILE_PX) // 2, (vh // main.TILE_PX) // 2
    return (round((p[0] - vx) / main.TILE_PX - 0.5 - mc),
            round((p[1] - vy) / main.TILE_PX - 0.5 - ml))


main.click_minimap = clica_minimapa
main.click_game = clica_jogo
main.client_rect = lambda win: (0, 0, 1920, 1009)
main.focus_window = lambda win: True
main.pyautogui = type("P", (), {
    "press": staticmethod(lambda t: acoes.append(("tecla", t))),
    "keyDown": staticmethod(lambda t: None),
    "keyUp": staticmethod(lambda t: None)})()
main.time = type("T", (), {"time": staticmethod(lambda: relogio["t"]),
                           "sleep": staticmethod(lambda s: None)})()

falhas = []
print(f"grade da tela: {main.GAME_VIEW[2] // main.TILE_PX}x"
      f"{main.GAME_VIEW[3] // main.TILE_PX} quadrados de {main.TILE_PX}px | "
      f"MINIMAP_PX_SQM configurado = {main.MINIMAP_PX_SQM}\n")

# ---------- 1) o clique de aproximacao cai no PIXEL do quadrado do corpo
print("corpo longe -> onde o clique de aproximacao cai:")
for off in ((3, 0), (-4, 2), (0, -3), (5, -4), (-2, -2)):
    odo.pos = [0, 0]
    acoes.clear()
    estado = {}
    main.marca_o_corpo(estado, off, odo, na_tela=True)
    main.loot(Janela(), Janela(), estado, Livre(), odo)
    jogo = [a for a in acoes if a[0] == "jogo"]
    esperado = main.ponto_do_quadrado(Janela(), off)
    ok = bool(jogo) and jogo[0][2] == esperado
    print(f"  corpo em {str(off):>9}: clicou em "
          f"{jogo[0][2] if jogo else None} | quadrado dele em {esperado} "
          f"-> {'exato' if ok else 'ERRADO'}")
    if not jogo:
        falhas.append(f"corpo em {off}: nao clicou na tela do jogo para chegar")
    elif jogo[0][2] != esperado:
        falhas.append(f"corpo em {off}: clicou em {jogo[0][2]}, o quadrado "
                      f"esta em {esperado}")
    if any(a[0] == "mapa" for a in acoes):
        falhas.append(f"corpo em {off}: usou o minimapa, cuja escala pode "
                      f"estar errada, tendo o quadrado dentro da tela")

# ---------- 2) fora da tela do jogo nao se clica em lugar nenhum
vw = main.GAME_VIEW[2] // main.TILE_PX
fora = (vw // 2 + 3, 0)
odo.pos = [0, 0]
acoes.clear()
estado = {}
main.marca_o_corpo(estado, fora, odo, na_tela=True)
main.loot(Janela(), Janela(), estado, Livre(), odo)
print(chr(10) + f"corpo em {fora}, FORA da tela do jogo: "
      f"{[a[0] for a in acoes] or 'nenhuma acao'}; sobrou "
      f"{len(estado.get('corpos') or [])} na fila")
if any(a[0] == "mapa" for a in acoes):
    falhas.append(f"corpo fora da tela em {fora}: clicou no minimapa. Era o "
                  f"que 'assumia' ali, e depende da mesma escala que fazia o "
                  f"personagem passar do corpo")
if any(a[0] == "jogo" for a in acoes):
    falhas.append(f"corpo fora da tela em {fora}: clicou na tela do jogo, onde "
                  f"nao ha quadrado dele - o clique cai no painel")
if estado.get("corpos"):
    falhas.append(f"corpo fora da tela em {fora} continua na fila, e loot() "
                  f"devolvendo True segura a rota para sempre")

# ---------- 3) o caminho pela tela NAO DEPENDE de MINIMAP_PX_SQM
# Esta e a propriedade que importa e que da para medir: mudando a escala do
# minimapa - o numero que se mede a mao com --zoom e que muda com o zoom do
# jogo - o clique na tela do jogo cai no MESMO pixel. Caminho que nao le esse
# numero nao pode errar por causa dele.
#
# (A primeira versao deste teste tentava medir o "passou do corpo" com um
# minimapa de mentira, e nao media nada: o falso andava pela escala
# CONFIGURADA, entao a conta fechava sempre. Escala errada nao desloca o passo
# do minimapa - ela distorce a DISTANCIA relatada, porque o mesmo numero
# divide e multiplica. O que sobra de verdade e isto: um caminho a menos
# dependendo de calibracao.)
print("\no clique de aproximacao com escalas de minimapa diferentes:")
guardado = main.MINIMAP_PX_SQM
pontos = {}
for escala in (1.0, 2.0, 4.0):
    main.MINIMAP_PX_SQM = escala
    odo.pos = [0, 0]
    acoes.clear()
    estado = {}
    main.marca_o_corpo(estado, (3, -2), odo, na_tela=True)
    main.loot(Janela(), Janela(), estado, Livre(), odo)
    jogo = [a for a in acoes if a[0] == "jogo"]
    pontos[escala] = jogo[0][2] if jogo else None
    print(f"  MINIMAP_PX_SQM={escala}: clicou em {pontos[escala]}")
main.MINIMAP_PX_SQM = guardado

if len(set(pontos.values())) != 1:
    falhas.append(f"o clique na tela mudou com a escala do minimapa: {pontos}. "
                  f"Esse caminho existe justamente para nao depender dela")
esperado_3 = main.ponto_do_quadrado(Janela(), (3, -2))
if pontos.get(2.0) != esperado_3:
    falhas.append(f"clicou em {pontos.get(2.0)}, o quadrado esta em "
                  f"{esperado_3}")

print("\nVEREDITO:", "OK - chega pelo quadrado da tela, sem escala para errar"
      if not falhas else "FALHOU: " + "; ".join(falhas))
