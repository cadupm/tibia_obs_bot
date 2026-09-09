# -*- coding: utf-8 -*-
"""Bicho que ANDA mexe a barra de lugar - e isso nao e uma morte.

Relatado em cacada: "quando o monstro morre, o bot acerta o clique exatamente
no corpo dele porem da mais alguns cliques e passa do monstro. O que deveria
acontecer eh clicar apenas aquela primeira vez e lootear com o '-'".

Os cliques a mais eram cliques de ANDAR, atras de corpos que nao existiam. O
quadrado da morte vem de uma diferenca de conjuntos - a barra que havia e nao
ha mais -, mas barra tambem deixa de haver quando o bicho ANDA um quadrado, ou
quando ele sai da tela. Os bichos se mexem enquanto se aproximam, o registro
enchia de quadrado que nao era corpo, e a morte consumia "o mais recente"
deles: o ULTIMO item de uma iteracao de CONJUNTO, ou seja, ordem arbitraria.

Por isso o teste roda VARIOS ARRANJOS da mesma briga. Com um arranjo so ele
passava por sorte de hash - medido a parte, em 5 arranjos 4 acertavam e 1
apontava o quadrado de onde um bicho apenas tinha dado um passo.

Cada arranjo tem uma fase de APROXIMACAO em que os tres se mexem (e o quarto
bicho anda para fora da tela e sai da battle list), e depois a briga de melee,
em que quem esta batendo em voce fica parado e morre um por um.

O que se mede, por arranjo:
  - os corpos marcados sao exatamente os quadrados de morte - nenhum quadrado
    inventado, apesar de todo o movimento anterior;
  - ha um clique de saque em cada corpo, e um so;
  - a tecla de saque sai uma vez por corpo, colada no clique;
  - ZERO cliques de andar: os corpos estao colados, e clique de andar aqui e o
    bot indo atras de corpo que nao existe - e o que faz ele passar do monstro.

E ha um arranjo AMBIGUO no fim, com os outros dois bichos dando um passo na
mesma leitura da morte. Ali a geometria admite duas explicacoes ("A morreu e B
andou" / "B morreu e A andou") e nenhuma conta de posicao decide. O exigido
nesse caso e o bot NAO INVENTAR quadrado: perde-se aquele corpo, e nao se
gasta clique nem caminhada.
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
CHAO = np.random.default_rng(71).integers(40, 70, (VH, VW, 3), dtype=np.uint8)


def sprite(semente):
    return np.random.default_rng(semente).integers(
        0, 255, (17, 20, 3), dtype=np.uint8)


SPRITES = [sprite(80 + i) for i in range(4)]
NOMES = ["melee A", "melee B", "melee C", "andarilho"]
MONSTROS = dict(zip(NOMES, SPRITES))
for i in range(4):
    for j in range(i + 1, 4):
        assert not main.sprite_igual(SPRITES[i], SPRITES[j]), \
            "os sprites do teste tem de ser distinguiveis"

# Cada arranjo: onde cada um dos tres melee fica parado (= onde morre) e para
# onde ele da o passo na aproximacao. Tudo a 1 SQM, que e onde bicho de melee
# morre - ele estava batendo em voce.
ARRANJOS = [
    {"nome": "(1,0) (0,1) (-1,0)",
     "paradas": [(1, 0), (0, 1), (-1, 0)],
     "passos": [(1, 0), (1, 1), (-1, 1)]},
    {"nome": "(0,-1) (1,0) (-1,0)",
     "paradas": [(0, -1), (1, 0), (-1, 0)],
     "passos": [(0, -1), (1, -1), (-1, -1)]},
    {"nome": "(-1,-1) (0,1) (1,0)",
     "paradas": [(-1, -1), (0, 1), (1, 0)],
     "passos": [(-1, -1), (1, 1), (1, -1)]},
    {"nome": "(1,1) (0,-1) (-1,0)",
     "paradas": [(1, 1), (0, -1), (-1, 0)],
     "passos": [(1, 1), (1, -1), (-1, -1)]},
    {"nome": "(1,1) (-1,0) (0,-1)",
     "paradas": [(1, 1), (-1, 0), (0, -1)],
     "passos": [(1, 1), (-1, 1), (1, -1)]},
]
ANDARILHO = [(3, -2), (4, -3), (5, -4), (6, -5)]


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


def moldura_do_alvo(img, off):
    """A moldura vermelha que o cliente desenha no bicho atacado.

    Medida na tela de verdade: RGB (190,62,62), 4 px de espessura, alinhada ao
    quadrado. E o unico desenho do cliente que respeita a grade, e por isso o
    localizador do corpo.
    """
    x0 = (MEIO_COL + off[0]) * main.TILE_PX
    y0 = (MEIO_LIN + off[1]) * main.TILE_PX
    t, g = main.TILE_PX, main.ALVO_GROSSURA
    if 0 <= y0 < VH - t and 0 <= x0 < VW - t:
        img[y0:y0 + g, x0:x0 + t] = main.ALVO_COR
        img[y0 + t - g:y0 + t, x0:x0 + t] = main.ALVO_COR
        img[y0:y0 + t, x0:x0 + g] = main.ALVO_COR
        img[y0:y0 + t, x0 + t - g:x0 + t] = main.ALVO_COR
    return img


def tela(vivos, corpos, alvo=None):
    """Vivos de pe com barra; corpos como cadaver, SEM barra e SEM nome."""
    img = CHAO.copy()
    for off in corpos:
        desenha(img, off, (95, 75, 55))
    for off in vivos.values():
        desenha(img, off, (170, 40, 40))
        barra(img, off)
    if alvo is not None and alvo in vivos:
        moldura_do_alvo(img, vivos[alvo])
    return img


def monta_quadros(arranjo, mexe_na_morte=False, autotarget=True):
    """
    A briga inteira, quadro por quadro.

    `mexe_na_morte` faz os dois sobreviventes darem um passo na mesma leitura
    em que o primeiro morre - o caso em que a geometria nao decide.

    `autotarget=False` e o cliente NAO passando a moldura para o proximo bicho
    sozinho: depois da morte fica um tempo sem alvo, o bot tem de reengajar, e
    a morte so fecha pelo debounce de TARGET_GONE_READS leituras. Nesse
    intervalo os bichos vivos continuam ANDANDO - e era ai que o registro se
    estragava, porque o passo deles era anotado depois da morte e virava "o
    desaparecimento mais recente".

    Devolve (quadros, quadrados em que os bichos morreram).
    """
    p, q = arranjo["paradas"], arranjo["passos"]
    todos = {0: p[0], 1: p[1], 2: p[2], 3: ANDARILHO[0]}
    quadros = [({}, [], [], None), ({}, [], [], None),
               (dict(todos), [], [0, 1, 2, 3], None),
               (dict(todos), [], [0, 1, 2, 3], 0)]
    # APROXIMACAO: os tres se mexem e o andarilho avanca. E daqui que vinha o
    # lixo do registro - quadrado que perdeu a barra sem ninguem morrer.
    for i, onde in enumerate((q, p, q)):
        quadros.append(({0: onde[0], 1: onde[1], 2: onde[2],
                         3: ANDARILHO[min(i + 1, len(ANDARILHO) - 1)]},
                        [], [0, 1, 2, 3], 0))
    # o andarilho sai da tela E da battle list: barra que sumiu sem morte
    quadros.append(({0: p[0], 1: p[1], 2: p[2]}, [], [0, 1, 2], 0))
    quadros.append(({0: p[0], 1: p[1], 2: p[2]}, [], [0, 1, 2], 0))

    # MELEE: quem esta batendo em voce fica parado, e morre um por um
    vivos = {1: p[1], 2: p[2]}
    if mexe_na_morte:
        vivos = {1: q[1], 2: q[2]}
    mortes = [p[0]]
    if autotarget:
        quadros += [(dict(vivos), list(mortes), [1, 2], 1)] * 4
    else:
        # SEM ALVO, e os vivos se mexendo: as leituras de espera do debounce
        for i in range(4):
            onde = q if i % 2 else p
            quadros.append(({1: onde[1], 2: onde[2]}, list(mortes),
                            [1, 2], None))
        vivos = {1: p[1], 2: p[2]}
        quadros += [(dict(vivos), list(mortes), [1, 2], 1)] * 3
    mortes.append(vivos[1])
    vivos = {2: vivos[2]}
    if autotarget:
        quadros += [(dict(vivos), list(mortes), [2], 2)] * 4
    else:
        for i in range(4):
            onde = q if i % 2 else p
            quadros.append(({2: onde[2]}, list(mortes), [2], None))
        vivos = {2: p[2]}
        quadros += [(dict(vivos), list(mortes), [2], 2)] * 3
    mortes.append(vivos[2])
    quadros += [({}, list(mortes), [], None)] * 40
    return quadros, mortes


class Janela:
    isActive = True
    title = "falso"
    isMinimized = False


class OdoFalso:
    """Personagem parado: saque colado e clique direito, que nao anda."""

    def __init__(self, _win=None):
        self.pos = [0, 0]
        self.parado = 9

    def atualiza(self):
        pass

    def resync(self):
        pass

    def ancora(self, alvo):
        pass

    def mudou_de_andar(self):
        return False


def roda(arranjo, mexe_na_morte=False, autotarget=True):
    quadros, mortes = monta_quadros(arranjo, mexe_na_morte, autotarget)
    telas = [tela(v, c, a) for v, c, _l, a in quadros]
    roteiro = [(len(lista), alvo is not None,
                0.9 if alvo is not None else None,
                [SPRITES[i] for i in lista],
                SPRITES[alvo] if alvo is not None else None)
               for _v, _c, lista, alvo in quadros]
    fita, quadro = [], {"i": 0}

    def agora():
        return min(quadro["i"], len(roteiro) - 1)

    def loop_sleep(_s):
        quadro["i"] += 1
        if quadro["i"] >= len(roteiro):
            main.STOP = True

    main.setup_windows = lambda: (Janela(), Janela())
    main.ensure_bars = lambda win, force=False: ((0, 0, 10, 2), (0, 0, 10, 2))
    main.read_bars = lambda win: (1.0, 1.0)
    main.battle_state = lambda win: roteiro[agora()]
    main.grab = lambda regiao: telas[agora()]
    main.Odometro = OdoFalso
    main.client_rect = lambda win: (0, 0, 1920, 1009)
    main.detect_marks = lambda win, mm=None, cor=None: []
    main.is_usable = lambda win: True
    main.focus_window = lambda win: True
    main.restore_windows = lambda: None
    main.keyboard = type("K", (), {
        "is_pressed": staticmethod(lambda k: False)})()
    main.pyautogui = type("P", (), {
        "press": staticmethod(lambda t: fita.append((agora(), "tecla", t))),
        "keyDown": staticmethod(lambda t: None),
        "keyUp": staticmethod(lambda t: None)})()
    main.click_minimap = lambda w, p: fita.append((agora(), "mapa", p))
    main.click_game = lambda x, y, pausa=0.09, botao="esquerdo", mod="": \
        fita.append((agora(), "clique " + botao, (x, y)))
    main.time = type("T", (), {
        "time": staticmethod(lambda: quadro["i"] * 0.3),
        "sleep": staticmethod(loop_sleep)})()
    main.load_monsters = lambda caminho=None: dict(MONSTROS)
    main.load_loot_flags = lambda caminho=None: {n: True for n in NOMES}
    main.load_waypoints = lambda caminho=None: []
    main.load_evitar = lambda caminho=None: {}
    main.ONLY_KNOWN_MONSTERS = True
    main.AUTO_LEARN = False
    main.ENABLE_WALK = False
    main.USE_MAP_MARKS = False
    main.USE_ROUTE_ORDER = False
    main.ATTACK_MODE = "stand"
    main.ENABLE_HEAL = main.ENABLE_MANA = False
    main.ENABLE_SPELL = main.ENABLE_AUTOCAST = False
    main.ENABLE_PARALISIA = False
    main.ENABLE_LOOT = True
    main.LOOT_SO_MARCADOS = False
    main.LOOT_SO_SE_ACHOU = False
    main.ATTACK_CONFIRM = 2
    main.STOP = False

    saida = io.StringIO()
    with redirect_stdout(saida):
        main.run_bot()
    log = saida.getvalue()

    marcados = []
    for linha in log.splitlines():
        if "a moldura do alvo estava em (" in linha:
            miolo = linha.split("estava em (")[1].split(")")[0]
            x, y = (int(v) for v in miolo.split(","))
            marcados.append((x, y))
        elif "a barra de vida sumiu em [" in linha:
            miolo = linha.split("sumiu em [")[1].split("]")[0]
            for par in miolo.replace("(", "").split("),"):
                par = par.replace(")", "").strip()
                if par:
                    x, y = (int(v) for v in par.split(","))
                    marcados.append((x, y))
    return {
        "mortes": mortes, "marcados": marcados, "log": log,
        "saques": [f[2] for f in fita if f[1] == "clique " + main.LOOT_BOTAO],
        "andadas": [f[2] for f in fita if f[1] == "clique esquerdo"],
        "teclas": [f for f in fita
                   if f[1] == "tecla" and f[2] == main.LOOT_TECLA]}


falhas = []
print("os bichos se mexem na aproximacao e morrem parados, em melee.\n"
      "cada arranjo troca os quadrados: a escolha de 'qual barra sumiu' saia "
      "de uma\niteracao de conjunto, e acertava ou errava conforme o hash das "
      "posicoes.\n")
print(f"  {'arranjo':<22} {'mortes':<26} {'corpos marcados':<26} "
      f"{'saques':<7} {'tecla':<6} andadas")
for arranjo in ARRANJOS:
    r = roda(arranjo)
    esperados = sorted(r["mortes"])
    pontos = sorted(main.ponto_do_quadrado(Janela(), q) for q in esperados)
    saiu = sorted(r["saques"])
    print(f"  {arranjo['nome']:<22} {str(esperados):<26} "
          f"{str(sorted(r['marcados'])):<26} {len(r['saques']):<7} "
          f"{len(r['teclas']):<6} {len(r['andadas'])}")
    if os.environ.get("VERBOSO"):
        for l in r["log"].splitlines():
            if "[loot]" in l:
                print("      " + l)
    if sorted(r["marcados"]) != esperados:
        sobra = sorted(set(r["marcados"]) - set(esperados))
        falta = sorted(set(esperados) - set(r["marcados"]))
        falhas.append(
            f"{arranjo['nome']}: marcou {sorted(r['marcados'])}, esperava "
            f"{esperados}"
            + (f"; quadrado sem morte nenhuma: {sobra} - barra que apenas "
               f"ANDOU entrou como morte" if sobra else "")
            + (f"; morte perdida: {falta}" if falta else ""))
    if saiu != pontos:
        falhas.append(f"{arranjo['nome']}: clicou em {saiu}, esperava "
                      f"{pontos}")
    if len(r["teclas"]) != len(esperados):
        falhas.append(f"{arranjo['nome']}: a tecla {main.LOOT_TECLA!r} saiu "
                      f"{len(r['teclas'])} vez(es), esperava "
                      f"{len(esperados)} - uma por corpo, colada no clique")
    if r["andadas"]:
        falhas.append(
            f"{arranjo['nome']}: {len(r['andadas'])} clique(s) de ANDAR "
            f"{r['andadas']}. Os corpos estao todos colados, nenhum exige "
            f"caminhada - clique de andar aqui e o bot indo atras de um corpo "
            f"que nao existe, e e o que faz ele passar do monstro")

# ------------------------------- sem o cliente passar a moldura sozinho
print(chr(10) + "SEM AUTOTARGET (a moldura nao passa sozinha; a morte fecha pelo"
      " debounce, e nas leituras de espera os vivos continuam andando):")
print(f"  {'arranjo':<22} {'mortes':<26} {'corpos marcados':<26} "
      f"{'saques':<7} {'tecla':<6} andadas")
for arranjo in ARRANJOS:
    r = roda(arranjo, autotarget=False)
    esperados = sorted(r["mortes"])
    pontos = sorted(main.ponto_do_quadrado(Janela(), q) for q in esperados)
    print(f"  {arranjo['nome']:<22} {str(esperados):<26} "
          f"{str(sorted(r['marcados'])):<26} {len(r['saques']):<7} "
          f"{len(r['teclas']):<6} {len(r['andadas'])}")
    if os.environ.get("VERBOSO"):
        for l in r["log"].splitlines():
            if "[loot]" in l:
                print("      " + l)
    inventados = sorted(set(r["marcados"]) - set(esperados))
    if inventados:
        falhas.append(
            f"sem autotarget, {arranjo['nome']}: marcou corpo em "
            f"{inventados}, onde ninguem morreu. Sao quadrados de onde um "
            f"bicho VIVO saiu andando durante a espera do debounce - anotados "
            f"depois da morte, eles viram 'o desaparecimento mais recente'")
    if sorted(r["marcados"]) != esperados:
        falta = sorted(set(esperados) - set(r["marcados"]))
        if falta:
            falhas.append(f"sem autotarget, {arranjo['nome']}: morte perdida "
                          f"em {falta}")
    if sorted(r["saques"]) != pontos:
        falhas.append(f"sem autotarget, {arranjo['nome']}: clicou em "
                      f"{sorted(r['saques'])}, esperava {pontos}")
    if r["andadas"]:
        falhas.append(
            f"sem autotarget, {arranjo['nome']}: {len(r['andadas'])} "
            f"clique(s) de ANDAR {r['andadas']} - o bot indo atras de corpo "
            f"que nao existe, que e o que faz ele passar do monstro")

# ---------------------------------------------------- a leitura ambigua
amb = roda(ARRANJOS[0], mexe_na_morte=True)
print(f"\nleitura AMBIGUA (os dois sobreviventes andam na leitura da morte):")
print(f"  mortes de verdade: {sorted(amb['mortes'])}")
print(f"  corpos marcados:   {sorted(amb['marcados'])}")
print(f"  saques: {len(amb['saques'])}   andadas: {len(amb['andadas'])}")
disse = [l for l in amb["log"].splitlines() if "nao chuto o quadrado" in l]
for l in disse:
    print("   " + l.strip())
inventados = sorted(set(amb["marcados"]) - set(amb["mortes"]))
if inventados:
    falhas.append(f"ambiguo: inventou corpo em {inventados}; na duvida o certo "
                  f"e nao marcar nada")
if amb["andadas"]:
    falhas.append(f"ambiguo: {len(amb['andadas'])} clique(s) de andar atras de "
                  f"corpo que nao existe")

# COM A MOLDURA, A LEITURA AMBIGUA DEIXA DE SER AMBIGUA. Ela marca QUAL bicho
# esta sendo atacado, e o que morre e esse - nao ha o que confundir com o passo
# de um vizinho. Antes de existir, esta morte se perdia.
if len(set(amb["marcados"])) != 3:
    falhas.append(f"ambiguo: marcou {len(set(amb['marcados']))} corpo(s), "
                  f"esperava 3. A moldura do alvo diz qual bicho morreu, "
                  f"entao o passo de um vizinho na mesma leitura nao confunde "
                  f"mais nada")

print("\nVEREDITO:", "OK - barra que andou nao e morte; um clique e a tecla "
      "por corpo" if not falhas else "FALHOU: " + "; ".join(falhas))
