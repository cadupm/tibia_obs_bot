# -*- coding: utf-8 -*-
"""Pegar o loot dos bichos que acabaram de morrer.

O gesto e IGUAL nos tres modos de luta: chegar no corpo, clicar nele, e varrer
a tecla de saque em volta. O que muda entre stand, chase e kite e so a
distancia de onde se parte - e distancia se resolve andando.

Cada peca ja falhou sozinha em jogo, e por isso cada uma tem caso aqui:

  - chegar perto:  em kite o personagem fica a KITE_DIST do bicho
  - clicar:        a tecla depende de estar configurada no cliente; o clique
                   direito no corpo e o gesto que qualquer cliente entende
  - mirar:         a tecla age sobre o que esta debaixo do cursor, e o cursor
                   ficava no minimapa, do ultimo clique de rota
  - a tecla certa: o '-' da fileira de cima e o '-' do numpad sao teclas
                   diferentes, e a hotkey do cliente pode estar em qualquer uma
  - VARIOS corpos: guardar um so deixava no chao todo bicho da briga menos o
                   ultimo, e numa caverna se mata em grupo

E o corpo nao tem barra de vida: o que se guarda, no momento da morte, e onde o
bicho estava - em coordenada ABSOLUTA do odometro, nao em offset. Offset
guardado envelhece a cada passo, e corrigi-lo foi a origem de dois bugs
seguidos.
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


def clica_mapa(_win, passo):
    acoes.append(("mapa", passo))
    odo.pos[0] += passo[0]                 # o personagem chega onde clicou
    odo.pos[1] += passo[1]


mirado = []
main.click_minimap = clica_mapa
main.client_rect = lambda win: (0, 0, 1920, 1009)
main.mira_mouse = lambda x, y: mirado.append((x, y))
main.click_game = lambda x, y, pausa=0.09, botao="esquerdo", mod="": \
    acoes.append(("clique", botao, mod, (x, y)))
main.focus_window = lambda win: True
main.pyautogui = type("P", (), {
    "press": staticmethod(lambda t: acoes.append(("tecla", t)))})()
main.time = type("T", (), {"time": staticmethod(lambda: relogio["t"]),
                           "sleep": staticmethod(lambda s: None)})()


def ponto_para_off(p):
    """Volta do ponto na tela para o offset em SQM: o inverso de mirar."""
    vx, vy, vw, vh = main.GAME_VIEW
    mc, ml = (vw // main.TILE_PX) // 2, (vh // main.TILE_PX) // 2
    return (round((p[0] - vx) / main.TILE_PX - 0.5 - mc),
            round((p[1] - vy) / main.TILE_PX - 0.5 - ml))


def saqueia_ate_o_fim(estado, voltas=80):
    """Roda o loot ate ele largar tudo, como o laco faria."""
    for _ in range(voltas):
        relogio["t"] += 0.5
        if not main.loot(Janela(), Janela(), estado, SemEspera(), odo):
            return True
    return False


def zera(pos=(0, 0)):
    odo.pos = list(pos)
    acoes.clear()
    mirado.clear()
    return {}


falhas = []
FILA = main.fila_do_saque()
QUADRADOS, APERTADAS = len(set(FILA)), len(FILA)
print(f"tecla de saque: {main.LOOT_HOTKEY!r}"
      + (f" + {main.NUMPAD_DO_SINAL[main.LOOT_HOTKEY]!r} (numpad)"
         if main.LOOT_HOTKEY_NUMPAD and main.LOOT_HOTKEY in main.NUMPAD_DO_SINAL
         else "")
      + f" | alcance: {main.LOOT_DIST} SQM")
print(f"clique: {main.LOOT_CLIQUES}x botao {main.LOOT_BOTAO}"
      + (f" com {main.LOOT_MOD}" if main.LOOT_MOD else "")
      + f" | varredura: {QUADRADOS} quadrado(s) em {APERTADAS} apertada(s)")
print(f"fila de corpos: ate {main.LOOT_MAX_CORPOS}\n")

# ------------------------------------------- 1) IGUAL NOS TRES MODOS
# O que muda entre stand, chase e kite e a distancia de onde se parte. O gesto
# tem de ser o mesmo: chegar, clicar, varrer.
print("o mesmo corpo, partindo das distancias de cada modo:")
resumo = {}
for modo, dist in (("stand", 1), ("chase", 2), ("kite", main.KITE_DIST)):
    estado = zera()
    main.marca_o_corpo(estado, (dist, 0), odo)
    acabou = saqueia_ate_o_fim(estado)
    cliques = [a for a in acoes if a[0] == "clique"]
    teclas = [a for a in acoes if a[0] == "tecla" and a[1] != main.STOP_WALK_KEY]
    andou = [a for a in acoes if a[0] == "mapa"]
    resumo[modo] = (len(cliques), len(teclas), acabou)
    print(f"  {modo:<6} (corpo a {dist} SQM): {len(andou)} clique(s) de mapa "
          f"para chegar, {len(cliques)} clique(s) no corpo, {len(teclas)} "
          f"tecla(s), terminou={acabou}")
    if not acabou:
        falhas.append(f"{modo}: nao terminou o saque")
    if not cliques:
        falhas.append(f"{modo}: nunca clicou no corpo")
    if dist > main.LOOT_DIST and not andou:
        falhas.append(f"{modo}: corpo a {dist} SQM e nao andou ate ele")

gestos = {m: r[:2] for m, r in resumo.items()}
print(f"  gesto (cliques, teclas) por modo: {gestos}")
if len(set(gestos.values())) != 1:
    falhas.append(f"o gesto de saque difere entre os modos: {gestos}. Tem de "
                  f"ser o mesmo - so a distancia de partida muda")

# ------------------------------------- 2) clicou com o botao configurado
estado = zera()
main.marca_o_corpo(estado, (1, 0), odo)
saqueia_ate_o_fim(estado)
cliques = [a for a in acoes if a[0] == "clique"]
print(f"\nclique no corpo: {cliques[:1]}")
if not cliques:
    falhas.append("nao clicou no corpo")
else:
    _, botao, mod, ponto = cliques[0]
    esperado = main.ponto_do_quadrado(Janela(), (1, 0))
    if botao != main.LOOT_BOTAO:
        falhas.append(f"clicou com o botao {botao}, e nao {main.LOOT_BOTAO}")
    if mod != main.LOOT_MOD:
        falhas.append(f"clicou com modificador {mod!r}, esperava "
                      f"{main.LOOT_MOD!r}")
    if ponto != esperado:
        falhas.append(f"clicou em {ponto}, o corpo esta em {esperado}")
if len(cliques) != main.LOOT_CLIQUES:
    falhas.append(f"{len(cliques)} clique(s) no corpo, esperava "
                  f"{main.LOOT_CLIQUES}. Varrer o anel a CLIQUE abre um menu "
                  f"de contexto por quadrado vazio e atravanca o cliente")

# --------------------------- 3) a tecla tambem sai, nas duas versoes
teclas = {a[1] for a in acoes if a[0] == "tecla"}
print(f"teclas mandadas: {sorted(teclas)}")
if main.LOOT_HOTKEY not in teclas:
    falhas.append(f"nao mandou {main.LOOT_HOTKEY!r}")
gemea = main.NUMPAD_DO_SINAL.get(main.LOOT_HOTKEY)
if main.LOOT_HOTKEY_NUMPAD and gemea and gemea not in teclas:
    falhas.append(f"nao mandou {gemea!r}: com a hotkey do cliente no menos do "
                  f"numpad (VK_SUBTRACT), o '-' de cima (VK_OEM_MINUS) nao "
                  f"chega la e o bot nao pega nada")

# ------------------------------------ 4) VARIOS corpos numa briga
estado = zera()
for off in ((1, 0), (3, 0), (0, 3)):
    main.marca_o_corpo(estado, off, odo)
print(f"\ntres bichos mortos: {len(estado['corpos'])} corpo(s) na fila")
if len(estado["corpos"]) != 3:
    falhas.append(f"{len(estado['corpos'])} corpos na fila, esperava 3: "
                  f"guardar um so deixa os outros no chao")
acoes.clear()
acabou = saqueia_ate_o_fim(estado)
cliques = [a for a in acoes if a[0] == "clique"]
print(f"  saqueou todos? {acabou} | {len(cliques)} clique(s) em corpo, "
      f"sobrou {len(estado.get('corpos') or [])} na fila")
if not acabou or estado.get("corpos"):
    falhas.append("nao esvaziou a fila de corpos")
if len(cliques) < 3:
    falhas.append(f"clicou em {len(cliques)} corpo(s) de 3: cada corpo tem de "
                  f"receber o seu clique")

# ------------------------ 5) o corpo NAO envelhece: posicao absoluta
estado = zera()
main.marca_o_corpo(estado, (4, 0), odo)
odo.pos = [4, 0]                       # andou 2 SQM na direcao do corpo
agora = main.onde_esta_o_corpo(estado["corpos"][0], odo)
print(f"\ncorpo visto a 4 SQM; depois de andar 2 SQM esta a "
      f"{agora[0]:.0f},{agora[1]:.0f}")
if abs(agora[0] - 2) > 0.01:
    falhas.append(f"o corpo andou junto com o personagem: {agora}")

# ------------ 6) desconta o caminho andado entre ver o bicho e a morte
estado = zera()
odo.pos = [6, 0]                       # andou 3 SQM desde que viu o bicho
main.marca_o_corpo(estado, (4, 0), odo, visto_em=(0, 0))
agora = main.onde_esta_o_corpo(estado["corpos"][0], odo)
print(f"viu o bicho a 4 SQM e andou 3 na direcao dele -> corpo a "
      f"{agora[0]:.0f},{agora[1]:.0f} (esperado 1)")
if abs(agora[0] - 1) > 0.01:
    falhas.append(f"nao descontou o caminho andado: {agora}")

# ------------------------ 7) duas mortes no mesmo lugar: um corpo
estado = zera()
main.marca_o_corpo(estado, (1, 0), odo)
main.marca_o_corpo(estado, (1, 0), odo)
print(f"\ndois bichos mortos no MESMO quadrado: "
      f"{len(estado['corpos'])} corpo(s) na fila (esperado 1)")
if len(estado["corpos"]) != 1:
    falhas.append(f"{len(estado['corpos'])} corpos para o mesmo quadrado: "
                  f"saquear duas vezes o mesmo lugar e so perder tempo")

# ------------------------------ 8) prazo: corpo inalcancavel nao trava
estado = zera()
main.marca_o_corpo(estado, (6, 0), odo)
main.click_minimap = lambda _w, _p: None          # nao anda
relogio["t"] += main.LOOT_PRAZO + 1
preso = not saqueia_ate_o_fim(estado)
main.click_minimap = clica_mapa
print(f"corpo que nao da para alcancar: "
      f"{'PRESO para sempre' if preso else 'desistiu e liberou a rota'}")
if preso:
    falhas.append("corpo inalcancavel prende a rota para sempre: o bot para de "
                  "cacar sem uma linha de erro")

# ------------------ 8b) e desistir de UM nao larga os outros da fila
estado = zera()
main.marca_o_corpo(estado, (6, 0), odo)     # esse nao da
main.marca_o_corpo(estado, (1, 0), odo)     # esse da
main.click_minimap = lambda _w, _p: None
acoes.clear()
relogio["t"] += main.LOOT_PRAZO + 1
saqueia_ate_o_fim(estado)
main.click_minimap = clica_mapa
cliques = [a for a in acoes if a[0] == "clique"]
print(f"desistindo do primeiro, o segundo foi saqueado? {bool(cliques)}")
if not cliques:
    falhas.append("desistir de um corpo largou o resto da fila")

# ------------------------------------- 9) varredura acompanha o corpo
estado = zera()
main.marca_o_corpo(estado, (1, 0), odo)
main.loot(Janela(), Janela(), estado, SemEspera(), odo)   # clique
mirado.clear()
main.loot(Janela(), Janela(), estado, SemEspera(), odo)   # comeca a varrer
odo.pos = [2, 0]                       # anda 1 SQM: o corpo cai para offset 0
saqueia_ate_o_fim(estado)
varridos = {ponto_para_off(m) for m in mirado[main.LOOT_POR_VEZ:]}
print(f"\nandou 1 SQM no meio da varredura: cobre o quadrado do corpo (0,0)? "
      f"{(0, 0) in varridos}")
if (0, 0) not in varridos:
    falhas.append("a varredura envelheceu: depois do passo nao cobre mais o "
                  "quadrado do corpo")

# ------------------------------ 10) teto de apertadas sem perder cobertura
print(f"fila de um corpo: {APERTADAS} apertada(s) (teto "
      f"{main.LOOT_MAX_APERTADAS}) cobrindo {QUADRADOS} quadrado(s)")
if APERTADAS > main.LOOT_MAX_APERTADAS:
    falhas.append(f"a fila passa do teto: {APERTADAS}")
if QUADRADOS != len(main.quadrados_do_saque()):
    falhas.append(f"o teto cortou a COBERTURA: {QUADRADOS} de "
                  f"{len(main.quadrados_do_saque())}. Em rodadas do anel, "
                  f"cortar no teto so tira repeticao")

# ------------------------ 11) quadrado fora da area do jogo nao e mirado
_vx, _vy, vw, vh = main.GAME_VIEW
borda = ((vw // main.TILE_PX) // 2, 0)
print(f"quadrado na borda {borda}: na tela? {main.dentro_da_tela(borda)}; "
      f"um alem, {(borda[0] + 1, 0)}: {main.dentro_da_tela((borda[0] + 1, 0))}")
if not main.dentro_da_tela(borda) or main.dentro_da_tela((borda[0] + 1, 0)):
    falhas.append("dentro_da_tela nao corta na borda da area do jogo: com "
                  "LOOT_DIST alto o cursor iria parar no painel lateral")

# ------------------------------------------ 12) desligado nao faz nada
main.ENABLE_LOOT = False
estado = zera()
main.marca_o_corpo(estado, (1, 0), odo)
print(f"\ncom ENABLE_LOOT desligado: guardou corpo? {bool(estado.get('corpos'))}"
      f", agiu? {bool(acoes)}")
if estado.get("corpos") or acoes:
    falhas.append("desligado e mesmo assim mexeu")
main.ENABLE_LOOT = True

print("\nVEREDITO:", "OK - o mesmo saque nos tres modos, e a fila esvazia"
      if not falhas else "FALHOU: " + "; ".join(falhas))
