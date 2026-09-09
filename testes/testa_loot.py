# -*- coding: utf-8 -*-
"""Pegar o loot do bicho que acabou de morrer.

A tecla de saque rapido do cliente resolve o saque em si; o que o bot tem de
fazer e CHEGAR PERTO, MIRAR O CURSOR no corpo e APERTAR A TECLA CERTA. Cada um
dos tres ja falhou sozinho em jogo:

  - chegar perto:  em kite o personagem fica a KITE_DIST do bicho
  - mirar:         a tecla age sobre o que esta debaixo do cursor, e o cursor
                   ficava no minimapa, do ultimo clique de rota
  - a tecla certa: o '-' da fileira de cima e o '-' do numpad sao teclas
                   diferentes, e a hotkey do cliente pode estar em qualquer uma

E o corpo nao tem barra de vida: o que se guarda, no momento da morte, e onde o
bicho estava - uma estimativa que erra por 1 SQM com facilidade, dai a
varredura dos quadrados em volta.
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


def ponto_para_off(p):
    """Volta do ponto na tela para o offset em SQM: o inverso de mirar."""
    vx, vy, vw, vh = main.GAME_VIEW
    mc, ml = (vw // main.TILE_PX) // 2, (vh // main.TILE_PX) // 2
    return (round((p[0] - vx) / main.TILE_PX - 0.5 - mc),
            round((p[1] - vy) / main.TILE_PX - 0.5 - ml))


def saqueia_ate_o_fim(estado, voltas=40):
    """Roda o loot ate ele largar o corpo, como o laco faria."""
    for _ in range(voltas):
        relogio["t"] += 0.5
        if not main.loot(Janela(), Janela(), estado, SemEspera(), odo):
            return True
    return False


falhas = []
FILA = main.fila_do_saque()
QUADRADOS = len(set(FILA))
APERTADAS = len(FILA)
print(f"tecla de saque: {main.LOOT_HOTKEY!r}"
      + (f" + {main.NUMPAD_DO_SINAL[main.LOOT_HOTKEY]!r} (numpad)"
         if main.LOOT_HOTKEY_NUMPAD and main.LOOT_HOTKEY in main.NUMPAD_DO_SINAL
         else "")
      + f" | alcance: {main.LOOT_DIST} SQM")
print(f"varredura: {QUADRADOS} quadrado(s) em {APERTADAS} apertada(s) "
      f"(teto {main.LOOT_MAX_APERTADAS}), {main.LOOT_POR_VEZ} por leitura\n")

# ----------------------------------------- 1) em stand: o corpo esta colado
estado = {}
main.marca_o_corpo(estado, (1, 0), odo)
acoes.clear(); mirado.clear()
acabou = saqueia_ate_o_fim(estado)
miradas = len(mirado)
cliques = [a for a in acoes if a[0] == "clique"]
print(f"corpo colado (1 SQM): {miradas} mirada(s), {len(cliques)} clique(s), "
      f"terminou? {acabou}")
if not acabou:
    falhas.append("colado: a varredura nunca terminou")
if miradas != APERTADAS:
    falhas.append(f"colado: {miradas} miradas, esperava {APERTADAS}")
if cliques:
    falhas.append("colado: andou sem precisar")

# ---------------------- 1b) varreu QUADRADOS DIFERENTES, e nao o mesmo N vezes
alvos = {m for m in mirado}
print(f"  quadrados distintos mirados: {len(alvos)} (esperava {QUADRADOS})")
if len(alvos) != QUADRADOS:
    falhas.append(f"varreu {len(alvos)} quadrados distintos, esperava "
                  f"{QUADRADOS}: a estimativa erra por 1 SQM e sem varrer o "
                  f"anel o bot nao pega nada")
# o estimado tem de vir PRIMEIRO: e o mais provavel
if mirado and mirado[0] != main.ponto_do_quadrado(Janela(), (1, 0)):
    falhas.append(f"comecou por {mirado[0]}, e nao pelo quadrado estimado "
                  f"{main.ponto_do_quadrado(Janela(), (1, 0))}")

# -------------------- 1c) a tecla do NUMPAD tambem sai (hotkey pode estar la)
teclas = {a[1] for a in acoes if a[0] == "tecla"}
print(f"  teclas mandadas: {sorted(teclas)}")
if main.LOOT_HOTKEY not in teclas:
    falhas.append(f"nao mandou {main.LOOT_HOTKEY!r}")
gemea = main.NUMPAD_DO_SINAL.get(main.LOOT_HOTKEY)
if main.LOOT_HOTKEY_NUMPAD and gemea and gemea not in teclas:
    falhas.append(f"nao mandou {gemea!r}: com a hotkey do cliente no menos do "
                  f"numpad (VK_SUBTRACT), o '-' de cima (VK_OEM_MINUS) nao "
                  f"chega la e o bot nao pega nada")

# --------------------------------- 2) em kite: o corpo esta a 4 SQM, precisa ir
odo.pos = [0, 0]
estado = {}
main.marca_o_corpo(estado, (4, 0), odo)
acoes.clear(); mirado.clear()
acabou = saqueia_ate_o_fim(estado)
cliques = [a for a in acoes if a[0] == "clique"]
print(f"\ncorpo a 4 SQM:       {len(mirado)} mirada(s), "
      f"{len(cliques)} clique(s) {[c[1] for c in cliques]}")
print(f"  posicao final do personagem: {tuple(odo.pos)} "
      f"(em px de minimapa, {main.MINIMAP_PX_SQM} = 1 SQM)")
if not cliques:
    falhas.append("longe: nao andou ate o corpo")
if not acabou:
    falhas.append("longe: nao terminou de saquear")

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
main.click_minimap = clica

# ---------------- 4b) mas o prazo NAO corta uma varredura ja em andamento
odo.pos = [0, 0]
estado = {}
main.marca_o_corpo(estado, (1, 0), odo)
mirado.clear()
main.loot(Janela(), Janela(), estado, SemEspera(), odo)   # comeca a varrer
relogio["t"] += main.LOOT_PRAZO + 1                       # estoura o prazo
antes = len(mirado)
acabou = saqueia_ate_o_fim(estado)
print(f"prazo estourado no MEIO da varredura: continuou? "
      f"{len(mirado) > antes} ({len(mirado)} miradas no total)")
if len(mirado) != APERTADAS:
    falhas.append(f"o prazo cortou a varredura pela metade: {len(mirado)} "
                  f"miradas de {APERTADAS} - metade do loot ficaria dentro "
                  f"do corpo")

# ------------------------------------------- 5) desligado nao faz nada
main.ENABLE_LOOT = False
estado = {}
main.marca_o_corpo(estado, (1, 0), odo)
acoes.clear()
print(f"\ncom ENABLE_LOOT desligado: guardou corpo? "
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
print(f"mirou em {mirado[:1]}, quadrado do corpo em {esperado}")
if not mirado:
    falhas.append("apertou a tecla sem mirar o cursor no corpo")
elif mirado[0] != esperado:
    falhas.append(f"mirou em {mirado[0]}, o corpo esta em {esperado}")

# ------------- 7) o corpo nao envelhece: desconta o caminho andado ate a morte
estado = {}
odo.pos = [6, 0]                       # andou 3 SQM desde que viu o bicho
main.marca_o_corpo(estado, (4, 0), odo, visto_em=(0, 0))
print(f"\nviu o bicho a 4 SQM e andou 3 na direcao dele -> corpo em "
      f"{estado['loot_onde']}")
if abs(estado["loot_onde"][0] - 1) > 0.1:
    falhas.append(f"nao descontou o caminho andado: {estado['loot_onde']} "
                  f"(esperava perto de (1, 0))")

# ------------- 8) corpo novo nao herda a fila do anterior
estado = {}
odo.pos = [0, 0]
main.marca_o_corpo(estado, (1, 0), odo)
main.loot(Janela(), Janela(), estado, SemEspera(), odo)    # deixa fila pela metade
sobrou = len(estado.get("loot_fila") or [])
main.marca_o_corpo(estado, (0, 1), odo)                    # outro bicho morreu
print(f"corpo novo com {sobrou} quadrados pendentes do anterior: fila agora "
      f"= {estado.get('loot_fila')}")
if estado.get("loot_fila") is not None:
    falhas.append("o corpo novo herdou a fila do anterior: varreria em volta "
                  "do corpo errado")

# ---- 9) o personagem anda NO MEIO da varredura: os quadrados acompanham o corpo
# A fila guardava offsets do PERSONAGEM. Um passo no meio da varredura e todo o
# resto dela mirava um quadrado ao lado - justamente o erro que a varredura
# existe para cobrir.
odo.pos = [0, 0]
estado = {}
main.marca_o_corpo(estado, (1, 0), odo)
mirado.clear()
main.loot(Janela(), Janela(), estado, SemEspera(), odo)   # comeca a varrer
odo.pos = [2, 0]                       # anda 1 SQM: o corpo cai para offset 0
saqueia_ate_o_fim(estado)
varridos = {ponto_para_off(m) for m in mirado[main.LOOT_POR_VEZ:]}
print(f"\nandou 1 SQM no meio da varredura: o corpo passou de (1,0) para (0,0)")
print(f"  os quadrados varridos depois disso cobrem (0,0)? {(0, 0) in varridos}")
if (0, 0) not in varridos:
    falhas.append("a fila envelheceu: depois do passo, a varredura nao cobre "
                  "mais o quadrado do corpo")

# ---- 10) corpo que sai do alcance NAO pode prender a cacada para sempre
# loot() devolvendo True SEGURA A ROTA. Com a varredura ja montada, o prazo era
# pulado - e um corpo fora de alcance prendia o bot para sempre, sem erro.
odo.pos = [0, 0]
estado = {}
main.marca_o_corpo(estado, (1, 0), odo)
main.loot(Janela(), Janela(), estado, SemEspera(), odo)   # monta a fila
odo.pos = [-40, 0]                     # o corpo fica longe
main.click_minimap = lambda _w, _p: None                  # e nao da para voltar
relogio["t"] += main.LOOT_PRAZO + 1
preso = True
for _ in range(80):
    relogio["t"] += 1.0
    if not main.loot(Janela(), Janela(), estado, SemEspera(), odo):
        preso = False
        break
main.click_minimap = clica
print(f"corpo fora de alcance com a varredura comecada: "
      f"{'PRESO para sempre' if preso else 'desistiu e liberou a rota'}")
if preso:
    falhas.append("corpo inalcancavel com a fila montada prende a rota para "
                  "sempre: o bot para de cacar sem uma linha de erro")

# ---- 11) teto de apertadas, sem perder cobertura
print(f"\nfila de um corpo: {APERTADAS} apertada(s) (teto "
      f"{main.LOOT_MAX_APERTADAS}) cobrindo {QUADRADOS} quadrado(s)")
if APERTADAS > main.LOOT_MAX_APERTADAS:
    falhas.append(f"a fila passa do teto: {APERTADAS}")
esperados = len(main.quadrados_do_saque())
if QUADRADOS != esperados:
    falhas.append(f"o teto cortou a COBERTURA: {QUADRADOS} quadrados de "
                  f"{esperados}. Em rodadas do anel, cortar no teto so tira "
                  f"repeticao - se tirou quadrado, a fila voltou a ser em "
                  f"blocos")

# ---- 12) quadrado fora da area do jogo nao leva o cursor para o painel
_vx, _vy, vw, vh = main.GAME_VIEW
borda = ((vw // main.TILE_PX) // 2, 0)
print(f"quadrado na borda {borda}: na tela? {main.dentro_da_tela(borda)}; "
      f"um alem, {(borda[0] + 1, 0)}: {main.dentro_da_tela((borda[0] + 1, 0))}")
if not main.dentro_da_tela(borda) or main.dentro_da_tela((borda[0] + 1, 0)):
    falhas.append("dentro_da_tela nao corta na borda da area do jogo: com "
                  "LOOT_DIST alto o cursor iria parar no painel lateral")

print("\nVEREDITO:", "OK - vai ate o corpo, varre os quadrados e volta a rota"
      if not falhas else "FALHOU: " + "; ".join(falhas))
