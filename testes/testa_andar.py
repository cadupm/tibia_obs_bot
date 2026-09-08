# -*- coding: utf-8 -*-
"""Mudanca de andar: perceber, aprender o quadrado e nunca mais pisar nele.

O minimapa NAO marca piso que muda de andar. Medido na captura do minimapa da
cidade: os 574 pixels do vermelho da paleta formam 111 blocos espalhados que
acompanham os predios - e telhado, nao escada. Sem sinal de antemao, o caminho e
cair UMA vez, guardar o retrato do quadrado e nunca mais pisar nele.

Aqui se testa: o alarme dispara quando o minimapa troca por inteiro (e nao
dispara com o mapa apenas rolando), o quadrado pisado e guardado, e a partir
dai aquele lado fica proibido.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

falhas = []
np.random.seed(9)

# ------------------------------------------------- 1) o alarme de mudar andar
ANDAR_A = (np.random.rand(110, 108, 3) * 255).astype(np.int16)
ANDAR_B = (np.random.rand(110, 108, 3) * 255).astype(np.int16)


class Janela:
    title = "falso"


quadro = {"mm": ANDAR_A}
main.minimap_grab = lambda win: quadro["mm"]
odo = main.Odometro(Janela())

print("andando pelo mesmo andar (o mapa so rola):")
for passo in range(main.ODO_HISTORICO + 2):
    # rolar o mapa 2 px = andar 1 SQM, mantendo a textura
    quadro["mm"] = np.roll(quadro["mm"], -2, axis=1)
    odo.atualiza()
    if odo.mudou_de_andar():
        falhas.append(f"alarme falso no passo {passo} andando no mesmo andar")
print(f"  restos recentes: {[round(r, 1) for r in odo.restos[-5:]]}")
print(f"  alarme: {odo.mudou_de_andar()}")

print("\ntrocando o andar inteiro:")
quadro["mm"] = ANDAR_B
odo.atualiza()
print(f"  resto agora: {odo.restos[-1]:.1f} "
      f"(antes ficava em torno de {sorted(odo.restos[:-1])[len(odo.restos)//2]:.1f})")
print(f"  alarme: {odo.mudou_de_andar()}")
if not odo.mudou_de_andar():
    falhas.append("nao percebeu a troca de andar")

# --------------------------------------- 2) aprender o quadrado que derrubou
print("\naprendendo o quadrado que derrubou:")
_vx, _vy, vw, vh = main.GAME_VIEW
tela = np.zeros((vh, vw, 3), dtype=np.uint8)
meio_col, meio_lin = (vw // main.TILE_PX) // 2, (vh // main.TILE_PX) // 2
buraco = (np.random.rand(main.TILE_PX, main.TILE_PX, 3) * 255).astype(np.uint8)
x0, y0 = meio_col * main.TILE_PX, (meio_lin + 1) * main.TILE_PX   # embaixo
tela[y0:y0 + main.TILE_PX, x0:x0 + main.TILE_PX] = buraco

lugares = {}
main.save_evitar = lambda l, caminho=None: None      # nao escrever arquivo
main.mss = type("M", (), {"tools": type("T", (), {
    "to_png": staticmethod(lambda *a, **k: None)})})()
estado = {"tela_antes": tela, "passo_dado": (0, 1)}
nome = main.aprende_o_que_derrubou(estado, lugares)
print(f"  guardou como: {nome} ({len(lugares)} lugar(es) na lista)")
if not nome or not lugares:
    falhas.append("nao guardou o quadrado que derrubou")

# ------------------------------------------- 3) e agora aquele lado e proibido
proibidos = main.passos_proibidos(tela, lugares)
print(f"  passos proibidos a partir daqui: {sorted(proibidos)}")
if (0, 1) not in proibidos:
    falhas.append("depois de aprender, ainda deixaria pisar no buraco")

# com o buraco embaixo e bicho colado embaixo, ele nao pode fugir para la
main.KITE_DIAGONAIS = False
passo = main.passo_de_kite([(0, 1)], proibidos=proibidos)
print(f"  bicho embaixo, buraco embaixo -> {passo}")
if passo is not None and main.KITE_PASSOS[passo] == (0, 1):
    falhas.append("fugiu para dentro do buraco")

# o mesmo quadrado ensinado uma segunda vez nao entra duas vezes
antes = len(lugares)
main.aprende_o_que_derrubou(estado, lugares)
if len(lugares) != antes:
    falhas.append("guardou o mesmo quadrado duas vezes")

print("\nVEREDITO:", "OK - percebe, aprende e nao repete"
      if not falhas else "FALHOU: " + "; ".join(falhas))
