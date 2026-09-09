# -*- coding: utf-8 -*-
"""Pegar o loot dos bichos que acabaram de morrer.

O gesto e IGUAL nos tres modos de luta e cabe numa frase: chegar no corpo e
CLICAR NELE com o botao direito. Clique com o direito sobre um corpo saqueia no
cliente - sabendo que clicou nele, esta feito, e nao ha o que conferir depois.

O caminho ate aqui foi errando:

  - a posicao do corpo vinha de odometria e errava por 1 SQM, e para cobrir isso
    o bot VARRIA os nove quadrados em volta, com a tecla, o cursor pulando de um
    para outro. Varrer e chutar: clique ou tecla em quadrado sem corpo nao
    saqueia nada, e clique direito em chao vazio ainda abre menu de contexto;
  - agora o quadrado e IDENTIFICADO na tela (ver testa_acha_corpo.py) e, nao
    dando para identificar, o bot LARGA o corpo em vez de clicar no que nao e
    corpo. A tecla de saque ficou: UMA apertada, no proprio quadrado do corpo,
    com o cursor ja em cima dele por causa do clique. Nao passeia.

E o corpo nao tem barra de vida: a posicao e guardada em coordenada ABSOLUTA do
odometro, nao em offset. Offset guardado envelhece a cada passo, e corrigi-lo
foi a origem de dois bugs seguidos.
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
def clica_jogo(x, y, pausa=0.09, botao="esquerdo", mod=""):
    """
    Clique na tela do jogo, como o cliente responderia.

    O ESQUERDO ANDA. O bot passou a se aproximar do corpo clicando no quadrado
    dele na tela, em vez de clicar no minimapa - sem escala para errar. Um
    falso que so REGISTRA o clique deixa o personagem parado, e o teste passa a
    medir um bot que nunca chega: 17 cliques para um corpo a 2 SQM.
    """
    acoes.append(("clique", botao, mod, (x, y)))
    if botao == "esquerdo":
        vx, vy, vw, vh = main.GAME_VIEW
        mc, ml = (vw // main.TILE_PX) // 2, (vh // main.TILE_PX) // 2
        off = (round((x - vx) / main.TILE_PX - 0.5 - mc),
               round((y - vy) / main.TILE_PX - 0.5 - ml))
        odo.pos[0] += off[0] * main.MINIMAP_PX_SQM
        odo.pos[1] += off[1] * main.MINIMAP_PX_SQM


main.click_game = clica_jogo
main.focus_window = lambda win: True
main.pyautogui = type("P", (), {
    "press": staticmethod(lambda t: acoes.append(("tecla", t)))})()
main.time = type("T", (), {"time": staticmethod(lambda: relogio["t"]),
                           "sleep": staticmethod(lambda s: None)})()


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


def cliques():
    """
    Os cliques de SAQUE: os do botao configurado, no corpo.

    O clique de aproximacao e do botao ESQUERDO e serve para ANDAR ate o
    quadrado. Contar os dois juntos misturava "cheguei" com "saqueei".
    """
    return [a for a in acoes
            if a[0] == "clique" and a[1] == main.LOOT_BOTAO]


def cliques_de_andar():
    """Os cliques de aproximacao: clique no quadrado da tela para caminhar."""
    return [a for a in acoes
            if a[0] == "clique" and a[1] != main.LOOT_BOTAO]


def teclas_de_saque():
    """Teclas mandadas, tirando a de fechar menu."""
    return [a[1] for a in acoes
            if a[0] == "tecla" and a[1] != main.STOP_WALK_KEY]


falhas = []
print(f"gesto: 1 clique com o botao {main.LOOT_BOTAO}"
      + (f" + {main.LOOT_MOD}" if main.LOOT_MOD else "")
      + f", a {main.LOOT_DIST} SQM do corpo")
print(f"tecla de saque: {main.LOOT_TECLA!r}"
      + (f" + {main.NUMPAD_DO_SINAL[main.LOOT_TECLA]!r} (numpad)"
         if main.LOOT_TECLA_NUMPAD and main.LOOT_TECLA in main.NUMPAD_DO_SINAL
         else "") + f", uma vez, no quadrado do corpo")
print(f"so saqueia se identificou na tela: {main.LOOT_SO_SE_ACHOU}")
print(f"fila de corpos: ate {main.LOOT_MAX_CORPOS} | busca num raio de "
      f"{main.LOOT_BUSCA_RAIO} SQM ({len(main.anel_de_busca())} quadrados)\n")

# ------------------------------------------- 1) IGUAL NOS TRES MODOS
# O que muda entre stand, chase e kite e a distancia de onde se parte. O gesto
# tem de ser o mesmo: chegar e clicar.
print("o mesmo corpo, partindo das distancias de cada modo:")
gestos = {}
for modo, dist in (("stand", 1), ("chase", 2), ("kite", main.KITE_DIST)):
    estado = zera()
    main.marca_o_corpo(estado, (dist, 0), odo, na_tela=True)
    acabou = saqueia_ate_o_fim(estado)
    # andar e clique no quadrado da tela (o normal) ou no minimapa (corpo fora
    # da area do jogo); as duas formas contam como "foi ate ele"
    andou = [a for a in acoes if a[0] == "mapa"] + cliques_de_andar()
    gestos[modo] = (len(cliques()), len(teclas_de_saque()))
    print(f"  {modo:<6} (corpo a {dist} SQM): {len(andou)} passo(s) para "
          f"chegar, {len(cliques())} clique(s) no corpo, "
          f"{len(teclas_de_saque())} tecla(s), terminou={acabou}")
    if not acabou:
        falhas.append(f"{modo}: nao terminou o saque")
    if not cliques():
        falhas.append(f"{modo}: nunca clicou no corpo")
    if dist > main.LOOT_DIST and not andou:
        falhas.append(f"{modo}: corpo a {dist} SQM e nao andou ate ele")

print(f"  gesto (cliques, teclas) por modo: {gestos}")
if len(set(gestos.values())) != 1:
    falhas.append(f"o gesto difere entre os modos: {gestos}. Tem de ser o "
                  f"mesmo - so a distancia de partida muda")

# --------------------- 2) SO O CLIQUE, e num lugar so: era a reclamacao
estado = zera()
main.marca_o_corpo(estado, (1, 0), odo, na_tela=True)
saqueia_ate_o_fim(estado)
pontos = {c[3] for c in cliques()}
print(f"\num corpo: {len(cliques())} clique(s) em {len(pontos)} ponto(s) "
      f"{sorted(pontos)}, teclas {teclas_de_saque()}")
if len(pontos) != 1:
    falhas.append(f"clicou em {len(pontos)} pontos diferentes: o pedido e "
                  f"clique NO CORPO, nao em volta dele")
if len(cliques()) != 1:
    falhas.append(f"{len(cliques())} clique(s), esperava 1 - o segundo "
                  f"clique cai na bolsa que o primeiro abriu")
esperadas = ([main.LOOT_TECLA]
             + ([main.NUMPAD_DO_SINAL[main.LOOT_TECLA]]
                if main.LOOT_TECLA_NUMPAD
                and main.LOOT_TECLA in main.NUMPAD_DO_SINAL else [])
             ) if main.LOOT_TECLA else []
if teclas_de_saque() != esperadas:
    falhas.append(f"mandou {teclas_de_saque()}, esperava {esperadas}: uma "
                  f"apertada no corpo, e nao uma varredura")


# --------------------- 3) o clique cai no quadrado do corpo, botao certo
if cliques():
    _, botao, mod, ponto = cliques()[0]
    esperado = main.ponto_do_quadrado(Janela(), (1, 0))
    print(f"  clicou em {ponto} com {botao!r}; o corpo esta em {esperado}")
    if ponto != esperado:
        falhas.append(f"clicou em {ponto}, o corpo esta em {esperado}")
    if botao != main.LOOT_BOTAO:
        falhas.append(f"clicou com o botao {botao}, e nao {main.LOOT_BOTAO}")
    if mod != main.LOOT_MOD:
        falhas.append(f"modificador {mod!r}, esperava {main.LOOT_MOD!r}")

# --------------------- 4) fechar o menu de contexto que possa ter aberto
fechou = [a for a in acoes if a[0] == "tecla" and a[1] == main.STOP_WALK_KEY]
print(f"  apertou {main.STOP_WALK_KEY!r} depois do clique? {bool(fechou)}")
if main.LOOT_FECHA_MENU and main.STOP_WALK_KEY and not fechou:
    falhas.append("nao fechou o menu: sem 'classic control' o clique direito "
                  "abre menu de contexto, que fica na frente e engole o resto")

# ------------------------------------ 5) VARIOS corpos numa briga
estado = zera()
for off in ((1, 0), (3, 0), (0, 3)):
    main.marca_o_corpo(estado, off, odo, na_tela=True)
print(f"\ntres bichos mortos: {len(estado['corpos'])} corpo(s) na fila")
if len(estado["corpos"]) != 3:
    falhas.append(f"{len(estado['corpos'])} corpos na fila, esperava 3: "
                  f"guardar um so deixa os outros no chao")
acoes.clear()
acabou = saqueia_ate_o_fim(estado)
print(f"  saqueou todos? {acabou} | {len(cliques())} clique(s) em corpo, "
      f"sobrou {len(estado.get('corpos') or [])} na fila")
if not acabou or estado.get("corpos"):
    falhas.append("nao esvaziou a fila de corpos")
if len(cliques()) != 3:
    falhas.append(f"{len(cliques())} clique(s) para 3 corpos: cada corpo tem "
                  f"de receber o seu, e so o seu")

# ------------------------ 6) o corpo NAO envelhece: posicao absoluta
estado = zera()
main.marca_o_corpo(estado, (4, 0), odo, na_tela=True)
odo.pos = [4, 0]                       # andou 2 SQM na direcao do corpo
agora = main.onde_esta_o_corpo(estado["corpos"][0], odo)
print(f"\ncorpo visto a 4 SQM; depois de andar 2 SQM esta a "
      f"{agora[0]:.0f},{agora[1]:.0f}")
if abs(agora[0] - 2) > 0.01:
    falhas.append(f"o corpo andou junto com o personagem: {agora}")

# ------------ 7) desconta o caminho andado entre ver o bicho e a morte
estado = zera()
odo.pos = [6, 0]                       # andou 3 SQM desde que viu o bicho
main.marca_o_corpo(estado, (4, 0), odo, visto_em=(0, 0))
agora = main.onde_esta_o_corpo(estado["corpos"][0], odo)
print(f"viu o bicho a 4 SQM e andou 3 na direcao dele -> corpo a "
      f"{agora[0]:.0f},{agora[1]:.0f} (esperado 1)")
if abs(agora[0] - 1) > 0.01:
    falhas.append(f"nao descontou o caminho andado: {agora}")

# ------------------------ 8) duas mortes no mesmo lugar: um corpo
estado = zera()
main.marca_o_corpo(estado, (1, 0), odo, na_tela=True)
main.marca_o_corpo(estado, (1, 0), odo, na_tela=True)
print(f"\ndois bichos mortos no MESMO quadrado: "
      f"{len(estado['corpos'])} corpo(s) na fila (esperado 1)")
if len(estado["corpos"]) != 1:
    falhas.append(f"{len(estado['corpos'])} corpos para o mesmo quadrado: "
                  f"clicar duas vezes no mesmo lugar e so perder tempo")

# ------------------------------ 9) prazo: corpo inalcancavel nao trava
estado = zera()
main.marca_o_corpo(estado, (6, 0), odo, na_tela=True)
main.click_minimap = lambda _w, _p: None          # nao anda
relogio["t"] += main.LOOT_PRAZO + 1
preso = not saqueia_ate_o_fim(estado)
main.click_minimap = clica_mapa
print(f"corpo que nao da para alcancar: "
      f"{'PRESO para sempre' if preso else 'desistiu e liberou a rota'}")
if preso:
    falhas.append("corpo inalcancavel prende a rota para sempre: o bot para de "
                  "cacar sem uma linha de erro")

# ------------------ 9b) e desistir de UM nao larga os outros da fila
estado = zera()
main.marca_o_corpo(estado, (6, 0), odo, na_tela=True)    # esse nao da
main.marca_o_corpo(estado, (1, 0), odo, na_tela=True)    # esse da
main.click_minimap = lambda _w, _p: None
acoes.clear()
relogio["t"] += main.LOOT_PRAZO + 1
saqueia_ate_o_fim(estado)
main.click_minimap = clica_mapa
print(f"desistindo do primeiro, o segundo foi clicado? {bool(cliques())}")
if not cliques():
    falhas.append("desistir de um corpo largou o resto da fila")

# ------------------ 10) corpo fora da area do jogo nao vira clique no painel
_vx, _vy, vw, vh = main.GAME_VIEW
fora = ((vw // main.TILE_PX) // 2 + 1, 0)
estado = zera()
estado["corpos"] = [{"abs": (fora[0] * main.MINIMAP_PX_SQM, 0),
                     "off": fora, "desde": relogio["t"], "comecou": None,
                     "fila": None, "clicou": False, "apertadas": 0,
                     "na_tela": True}]
main.LOOT_DIST = fora[0] + 1           # ja esta "no alcance", so fora da tela
acoes.clear()
saqueia_ate_o_fim(estado)
print(f"\ncorpo em {fora}, fora da area do jogo: {len(cliques())} clique(s)")
if cliques():
    falhas.append(f"clicou em {fora}, que esta fora da area do jogo: o cursor "
                  f"cai no painel lateral")
main.LOOT_DIST = 1

# ------------------ 11) a VARREDURA nao existe mais no codigo
# A tecla ficou - uma apertada, no proprio quadrado do corpo. O que saiu foi
# varrer: a tecla em nove quadrados com o cursor pulando de um para outro, para
# cobrir um palpite que podia estar errado. O quadrado agora e identificado na
# tela, e o cursor ja esta em cima dele por causa do clique.
sobrou = [n for n in ("LOOT_USA_TECLA", "LOOT_VARRE", "LOOT_TENTATIVAS",
                      "LOOT_MAX_APERTADAS", "LOOT_POR_VEZ", "fila_do_saque",
                      "quadrados_do_saque", "mira_mouse")
          if hasattr(main, n)]
print(f"\nrestos da varredura de tecla: {sobrou or 'nenhum'}")
if sobrou:
    falhas.append(f"a varredura de tecla deixou restos: {sobrou}. Codigo "
                  f"desligado mas presente volta a ser ligado por acidente")

# ------------------------------------------ 12) desligado nao faz nada
main.ENABLE_LOOT = False
estado = zera()
main.marca_o_corpo(estado, (1, 0), odo, na_tela=True)
print(f"\ncom ENABLE_LOOT desligado: guardou corpo? "
      f"{bool(estado.get('corpos'))}, agiu? {bool(acoes)}")
if estado.get("corpos") or acoes:
    falhas.append("desligado e mesmo assim mexeu")
main.ENABLE_LOOT = True

print("\nVEREDITO:", "OK - um clique no corpo, um corpo por vez, e nada a mais"
      if not falhas else "FALHOU: " + "; ".join(falhas))
