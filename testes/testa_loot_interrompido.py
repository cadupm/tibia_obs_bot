# -*- coding: utf-8 -*-
"""Briga no meio do caminho nao pode custar o corpo.

Relatado em cacada: "ta indo saquear mas se encontra outro bicho ele para e
ataca, nao continua o saque".

Parar e lutar esta certo - bicho na tela, clique no mapa troca chase por stand
no cliente e parado em cima do corpo o personagem apanha de graca. O errado e o
corpo ser LARGADO por causa disso: LOOT_PRAZO e "o tempo de CHEGAR no corpo" e
era contado no relogio de parede, desde a primeira tentativa. A briga passa
dentro desse prazo sem que o bot tenha dado um passo atras do corpo, e quando a
lista fica limpa de novo o prazo ja venceu - o corpo e descartado sem nunca ter
recebido um clique.

O mundo aqui e fisico: o clique esquerdo ANDA o personagem um quadrado na
direcao pedida, e a tela e desenhada a partir de onde ele esta. Falso que so
registra o clique nao mede aproximacao nenhuma - ja custou um teste neste
projeto.

Roteiro: o bicho A morre LONGE (3 SQM), o bot comeca a andar ate o corpo, o
bicho B aparece no meio do caminho e e morto colado, e depois a lista fica
limpa. O exigido: OS DOIS corpos recebem clique de saque, e o log nao diz
"desisto dele" para o corpo de A.
"""
import io
import os
import sys
from contextlib import redirect_stdout
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

_vx, _vy, VW, VH = main.GAME_VIEW
MEIO_COL, MEIO_LIN = (VW // main.TILE_PX) // 2, (VH // main.TILE_PX) // 2
CHAO = np.random.default_rng(23).integers(40, 70, (VH, VW, 3), dtype=np.uint8)

SPRITE_A = np.random.default_rng(5).integers(0, 255, (17, 20, 3),
                                             dtype=np.uint8)
SPRITE_B = np.random.default_rng(6).integers(0, 255, (17, 20, 3),
                                             dtype=np.uint8)
assert not main.sprite_igual(SPRITE_A, SPRITE_B), \
    "os dois bichos do teste tem de ser distinguiveis"

# tudo em coordenada de MUNDO, em SQM, com o personagem comecando em (0,0)
A_MORRE_EM = (5, 0)         # longe: exige varios cliques para chegar
B_MORRE_EM = (1, 1)         # colado: saqueado na hora
B_VEM_DE = (2, -2)          # onde B aparece, na tela


def desenha(img, off, cor, tamanho=44):
    x0 = (MEIO_COL + off[0]) * main.TILE_PX + (main.TILE_PX - tamanho) // 2
    y0 = (MEIO_LIN + off[1]) * main.TILE_PX + (main.TILE_PX - tamanho) // 2
    if 0 <= y0 < VH - tamanho and 0 <= x0 < VW - tamanho:
        img[y0:y0 + tamanho, x0:x0 + tamanho] = cor
    return img


def barra(img, off):
    x = (MEIO_COL + off[0]) * main.TILE_PX + 18
    y = (MEIO_LIN + off[1] - main.CREATURE_BAR_ABOVE) * main.TILE_PX + 10
    if 0 <= y < VH - 4 and 0 <= x < VW - 31:
        img[y:y + 4, x:x + 31] = (0, 0, 0)
        img[y + 1:y + 3, x + 1:x + 30] = (0, 95, 0)
    return img


class Janela:
    isActive = True
    title = "falso"
    isMinimized = False


# onde o personagem esta e para onde o cliente esta levando ele
MUNDO = {"ch": [0, 0], "indo": None}


class OdoFalso:
    """Todos os odometros do laco olham para o MESMO personagem."""

    def __init__(self, _win=None):
        self.parado = 9

    @property
    def pos(self):
        return [MUNDO["ch"][0] * main.MINIMAP_PX_SQM,
                MUNDO["ch"][1] * main.MINIMAP_PX_SQM]

    def atualiza(self):
        pass

    def resync(self):
        pass

    def ancora(self, alvo):
        pass

    def mudou_de_andar(self):
        return False


# ---------------------------------------------------------------- roteiro
# cada leitura: bichos vivos {nome: quadrado de mundo}, corpos, lista, alvo
FASES = []


def fase(vezes, vivos, corpos, lista, alvo):
    for _ in range(vezes):
        FASES.append((dict(vivos), list(corpos), list(lista), alvo))


A_VIVO = {"A": A_MORRE_EM}
fase(2, {}, [], [], None)                            # cave vazia
fase(2, A_VIVO, [], ["A"], None)                     # A aparece
fase(6, A_VIVO, [], ["A"], "A")                      # engajado, apanhando
# A MORRE longe. Sao 5 leituras: da para a morte fechar e o clique no corpo
# sair, e B chega com o personagem AINDA A CAMINHO - que e o caso a medir.
fase(5, {}, [A_MORRE_EM], [], None)
# B aparece no meio da caminhada e e morto colado
B_VIVO = {"B": B_VEM_DE}
fase(2, B_VIVO, [A_MORRE_EM], ["B"], None)
fase(4, B_VIVO, [A_MORRE_EM], ["B"], "B")
B_COLADO = {"B": B_MORRE_EM}
fase(16, B_COLADO, [A_MORRE_EM], ["B"], "B")         # B cola e a briga demora
fase(60, {}, [A_MORRE_EM, B_MORRE_EM], [], None)     # B MORRE colado

SPRITES = {"A": SPRITE_A, "B": SPRITE_B}
fita, quadro = [], {"i": 0}


def agora():
    return min(quadro["i"], len(FASES) - 1)


def tela_agora():
    vivos, corpos, _lista, _alvo = FASES[agora()]
    ch = MUNDO["ch"]
    img = CHAO.copy()
    for onde in corpos:
        desenha(img, (onde[0] - ch[0], onde[1] - ch[1]), (95, 75, 55))
    for onde in vivos.values():
        off = (onde[0] - ch[0], onde[1] - ch[1])
        desenha(img, off, (170, 40, 40))
        barra(img, off)
    return img


def battle_agora(_win):
    _vivos, _corpos, lista, alvo = FASES[agora()]
    return (len(lista), alvo is not None, 0.9 if alvo else None,
            [SPRITES[n] for n in lista],
            SPRITES[alvo] if alvo else None)


def loop_sleep(_s):
    quadro["i"] += 1
    # O CLIENTE ANDA ENTRE UMA LEITURA E OUTRA, um quadrado por vez, ate ficar
    # COLADO no destino. E a caminhada que o clique pediu.
    indo = MUNDO["indo"]
    # BICHO VIVO NA TELA CANCELA A CAMINHADA. No cliente e o que acontece de
    # dois jeitos: o bot manda a tecla de parar ao entrar em briga, e o proprio
    # bicho fica no caminho. Sem isso o personagem atravessaria a briga andando
    # e o teste nunca mediria a interrupcao.
    if FASES[min(quadro["i"], len(FASES) - 1)][0]:
        MUNDO["indo"] = indo = None
    if indo is not None:
        falta = (indo[0] - MUNDO["ch"][0], indo[1] - MUNDO["ch"][1])
        if max(abs(falta[0]), abs(falta[1])) <= 1:
            MUNDO["indo"] = None
        else:
            MUNDO["ch"][0] += (falta[0] > 0) - (falta[0] < 0)
            MUNDO["ch"][1] += (falta[1] > 0) - (falta[1] < 0)
    if quadro["i"] >= len(FASES):
        main.STOP = True


def clica_jogo(x, y, pausa=0.09, botao="esquerdo", mod=""):
    """
    O cliente respondendo ao clique.

    CLIQUE EM COISA LONGE E ORDEM DE IR ATE ELA: o personagem anda sozinho, um
    quadrado por leitura, ate ficar do lado. Nao chega de uma vez - se o teste
    teleportasse, nao haveria caminhada para a briga interromper, que e
    justamente o que se quer medir.
    """
    fita.append((agora(), botao, (x, y)))
    alvo = (round((x - _vx) / main.TILE_PX - 0.5) - MEIO_COL,
            round((y - _vy) / main.TILE_PX - 0.5) - MEIO_LIN)
    MUNDO["indo"] = [MUNDO["ch"][0] + alvo[0], MUNDO["ch"][1] + alvo[1]]


main.setup_windows = lambda: (Janela(), Janela())
main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
main.read_bars = lambda win: (1.0, 1.0)
main.battle_state = battle_agora
main.grab = lambda regiao: tela_agora()
main.Odometro = OdoFalso
main.client_rect = lambda win: (0, 0, 1920, 1009)
main.detect_marks = lambda win, mm=None, cor=None: []
main.is_usable = lambda win: True
main.focus_window = lambda win: True
main.restore_windows = lambda: None
main.keyboard = type("K", (), {"is_pressed": staticmethod(lambda k: False)})()
def aperta(t):
    fita.append((agora(), "tecla", t))
    if t == main.STOP_WALK_KEY:
        # no cliente esta tecla para TODAS as acoes, e isso inclui a caminhada
        # que o clique no corpo tinha pedido
        MUNDO["indo"] = None


main.pyautogui = type("P", (), {
    "press": staticmethod(aperta),
    "keyDown": staticmethod(lambda t: None),
    "keyUp": staticmethod(lambda t: None)})()
main.click_minimap = lambda w, p: fita.append((agora(), "mapa", p))
main.click_game = clica_jogo
main.time = type("T", (), {"time": staticmethod(lambda: quadro["i"] * 0.3),
                           "sleep": staticmethod(loop_sleep)})()
main.load_monsters = lambda caminho=None: dict(SPRITES)
main.load_loot_flags = lambda caminho=None: {"A": True, "B": True}
main.load_waypoints = lambda caminho=None: []
main.load_evitar = lambda caminho=None: {}
main.ONLY_KNOWN_MONSTERS = True
main.AUTO_LEARN = False
# A ROTA LIGADA, para medir a regra de ouro: ela nao pode retomar o
# trajeto com corpo pendente. Sem marcas no minimapa ela nao anda para
# lugar nenhum, mas a linha 'retomando o trajeto' so sai quando o laco
# CHEGA no bloco da rota - e chegar la ja e o erro, se ha corpo na fila.
main.ENABLE_WALK = True
main.USE_MAP_MARKS = False
main.USE_ROUTE_ORDER = False
main.ATTACK_MODE = "stand"
main.ENABLE_HEAL = main.ENABLE_MANA = False
main.ENABLE_SPELL = main.ENABLE_AUTOCAST = False
main.ENABLE_PARALISIA = False
main.ENABLE_LOOT = True
main.LOOT_SO_MARCADOS = False
main.LOOT_SO_SE_ACHOU = False
main.LOOT_PRAZO = 3.0            # a briga do meio dura mais do que isso
main.ATTACK_CONFIRM = 2
main.STOP = False

saida = io.StringIO()
with redirect_stdout(saida):
    main.run_bot()
log = saida.getvalue()

if os.environ.get("VERBOSO"):
    for l in log.splitlines():
        if "[loot]" in l or "[attack]" in l:
            print("   " + l)

# ------------------------------------------------------- o que aconteceu
saques = [f for f in fita if f[1] == main.LOOT_BOTAO]
andadas = [f for f in fita if f[1] == "esquerdo"]
desistiu = [l for l in log.splitlines() if "desisto dele" in l]
largou = [l for l in log.splitlines() if "ficou para tras na rota" in l]
saqueados = [l for l in log.splitlines()
             if "Saqueado" in l or "saqueio na hora" in l]

print(f"A morre em {A_MORRE_EM} (longe, exige caminhada) e B em "
      f"{B_MORRE_EM} (colado)\n")
print(f"cliques de ANDAR (esquerdo, que nao deviam existir): "
      f"{len(andadas)}")
print(f"cliques de saque: {len(saques)}")
for f in saques:
    print(f"   leitura {f[0]}: {f[2]}")
print(f"\ncorpos saqueados: {len(saqueados)}")
for l in saqueados:
    print("   " + l.strip())
if desistiu:
    print(f"\ndesistencias:")
    for l in desistiu:
        print("   " + l.strip())
if largou:
    print(f"\nlargados por idade:")
    for l in largou:
        print("   " + l.strip())

# A REGRA DE OURO: a rota nao pode andar com CORPO PENDENTE. Retomar o
# trajeto entre uma briga e outra, com a fila vazia, esta certo - o errado e
# sair andando deixando corpo no chao. Entao a conta e a fila, leitura a
# leitura, e nao "antes do ultimo saque".
linhas = log.splitlines()
retomou, na_fila, com_corpo_pendente = [], 0, []
for i, l in enumerate(linhas):
    if "corpo(s) na fila" in l:
        na_fila = int(l.split("; ")[1].split(" corpo")[0])
    elif ("Saqueado" in l or "largo ele" in l or "; sigo" in l
          or "saqueio na hora" in l or "ficou para tras" in l):
        na_fila = max(na_fila - 1, 0)
    elif "retomando o trajeto" in l:
        retomou.append(i)
        if na_fila:
            com_corpo_pendente.append((i, na_fila))
antes_do_saque = com_corpo_pendente
print(chr(10) + f"regra de ouro: 'retomando o trajeto' nas linhas "
      f"{retomou}; com corpo ainda na fila: {com_corpo_pendente or 'nenhuma'}")

falhas = []
if antes_do_saque:
    falhas.append(
        f"a rota foi retomada com corpo ainda na fila {antes_do_saque} "
        f"(linha, corpos): mata, LOOTEIA, ataca o proximo ate acabar a battle "
        f"list, e SO DEPOIS segue para o ponto da rota")
if not retomou:
    falhas.append("a rota nunca foi retomada: depois de acabar a battle list e "
                  "recolher os corpos o bot tem de seguir o trajeto")
if desistiu:
    falhas.append(
        f"desistiu de {len(desistiu)} corpo(s) por prazo. O prazo e o tempo de "
        f"CHEGAR no corpo, e a briga do meio nao e tempo tentando chegar - "
        f"contado no relogio de parede, a briga consome o prazo inteiro e o "
        f"corpo e largado sem nunca ter recebido um clique")
# A BRIGA TEM DE CAIR NO MEIO DO SAQUE. Se o corpo de A fosse clicado e
# saqueado antes de B aparecer, o teste nao mediria interrupcao nenhuma - so
# um saque tranquilo seguido de outro. A prova e ter [attack] entre o clique
# no corpo de A e o "Saqueado" dele.
clicou_em = next((i for i, l in enumerate(linhas)
                  if "1 clique com o botao" in l), None)
saqueou_em = next((i for i, l in enumerate(linhas)
                   if "Saqueado" in l), None)
brigou_no_meio = (clicou_em is not None and saqueou_em is not None
                  and any("[attack]" in l
                          for l in linhas[clicou_em:saqueou_em]))
print(f"a briga caiu ENTRE o clique no corpo e o saque dele? "
      f"{brigou_no_meio}")
if not brigou_no_meio:
    falhas.append("a briga nao caiu no meio do saque: o roteiro tem de por o "
                  "bicho novo com o personagem AINDA A CAMINHO do corpo, "
                  "senao nao ha interrupcao para medir")
if len(saqueados) < 2:
    falhas.append(f"saqueou {len(saqueados)} de 2 corpos: o de B esta colado e "
                  f"o de A ficou esperando a briga acabar")
if andadas:
    falhas.append(
        f"{len(andadas)} clique(s) de andar {[f[2] for f in andadas]}. "
        f"Clicar no corpo JA e a ordem de ir ate ele; clicar de novo enquanto "
        f"o personagem anda joga o clique adiante dele, e foi assim que "
        f"apareceu em cacada: 'clicou nele e depois clicou mais duas vezes a "
        f"frente'")
# UM CLIQUE POR APROXIMACAO. Sao 2 corpos; a briga cancelou a caminhada ate um
# deles, e essa e a unica razao que autoriza um clique novo naquele corpo - a
# tecla de parar solta todas as acoes no cliente, inclusive a caminhada que o
# clique tinha pedido. Fora isso, clicar de novo enquanto o personagem anda e o
# que jogava o clique adiante do corpo.
recomecos = [l for l in linhas if "clico nele outra vez" in l]
esperado_cliques = 2 + len(recomecos)
print(f"cliques: {len(saques)} para 2 corpos + {len(recomecos)} caminhada(s) "
      f"cancelada(s) pela briga")
if len(saques) != esperado_cliques:
    falhas.append(f"{len(saques)} cliques de saque, esperava "
                  f"{esperado_cliques}: um por corpo, mais um por caminhada "
                  f"que a briga cancelou")

print("\nVEREDITO:", "OK - a briga do meio nao custa o corpo"
      if not falhas else "FALHOU: " + "; ".join(falhas))
