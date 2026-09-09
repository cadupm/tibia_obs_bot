# -*- coding: utf-8 -*-
"""Saquear so ALGUNS dos monstros que ataca.

ATACAR e SAQUEAR sao escolhas separadas. O bot continua atacando o que sempre
atacou; a lista de monstros diz de quem vale pegar o corpo. Isso importa em dois
casos concretos:

  - a caverna tem bicho de loot bom e bicho que so da lixo, e cada corpo custa
    uma parada (e, se estiver longe, uma caminhada);
  - com o auto-aprendizado ligado, todo bicho novo que aparece entra na lista -
    e sem interruptor viraria mais uma viagem ate o corpo.

Como o bot sabe QUEM morreu: a trava de alvo guarda o sprite do bicho que sumiu
da battle list, e monstros.json liga sprite a nome. O criterio de igualdade e o
mesmo do resto do projeto (diferenca media OU correlacao), que e o que aguenta o
sprite escurecido do bicho quase morto.

O que se mede aqui:
  - com o interruptor DESLIGADO, saqueia todos (nao muda nada para quem nao
    pediu nada);
  - LIGADO, saqueia o marcado e ignora o desmarcado - mas ATACA os dois;
  - bicho nao reconhecido fica de fora quando so os marcados valem: marcar so
    faz sentido se o que nao foi marcado ficar de fora;
  - o formato antigo do arquivo (so o sprite) continua valendo como "saqueia";
  - salvar a lista por outro motivo nao apaga a escolha de ninguem.
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

_vx, _vy, VW, VH = main.GAME_VIEW
MEIO_COL, MEIO_LIN = (VW // main.TILE_PX) // 2, (VH // main.TILE_PX) // 2
CHAO = np.random.default_rng(23).integers(40, 70, (VH, VW, 3), dtype=np.uint8)


def sprite(semente):
    """
    Um sprite RECONHECIVELMENTE diferente dos outros.

    Primeira versao deste teste usava cor num quadradinho de 5x5 sobre fundo
    igual: a diferenca media entre dois deles dava 8.3, abaixo de
    MONSTER_DIFF_MAX (12), e o bot os considerava O MESMO BICHO - com razao,
    porque as imagens eram quase iguais. Nada filtrava, e a culpa era do
    fixture, nao do codigo. Ruido diferente por bicho e o que garante que
    sprite_igual os separe, como sprites de especies diferentes no jogo.
    """
    return np.random.default_rng(semente).integers(
        0, 255, (17, 20, 3), dtype=np.uint8)


BOM = sprite(1)                    # o que vale saquear
LIXO = sprite(2)                   # o que nao vale
DESCONHECIDO = sprite(3)           # nunca cadastrado
MONSTROS = {"bicho bom": BOM, "bicho lixo": LIXO}
assert not main.sprite_igual(BOM, LIXO), "o fixture tem de ser distinguivel"
assert not main.sprite_igual(BOM, DESCONHECIDO)

ONDE = (1, 0)


def desenha(img, off, cor, tamanho=44):
    x0 = (MEIO_COL + off[0]) * main.TILE_PX + (main.TILE_PX - tamanho) // 2
    y0 = (MEIO_LIN + off[1]) * main.TILE_PX + (main.TILE_PX - tamanho) // 2
    img[y0:y0 + tamanho, x0:x0 + tamanho] = cor
    return img


def barra(img, off):
    x = (MEIO_COL + off[0]) * main.TILE_PX + 18
    y = (MEIO_LIN + off[1] - main.CREATURE_BAR_ABOVE) * main.TILE_PX + 10
    img[y:y + 4, x:x + 31] = (0, 0, 0)
    img[y + 1:y + 3, x + 1:x + 30] = (0, 95, 0)
    return img


TELA_VIVO = barra(desenha(CHAO.copy(), ONDE, (170, 40, 40)), ONDE)
TELA_MORTO = desenha(CHAO.copy(), ONDE, (95, 75, 55))


class Janela:
    isActive = True
    title = "falso"
    isMinimized = False


class OdoFalso:
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


def roda(quem_morre, so_marcados, marcas):
    """Um bicho aparece, e atacado, morre. Devolve o que o bot fez."""
    fita, quadro = [], {"i": 0}
    sp = MONSTROS[quem_morre]
    roteiro = ([(0, False, None, [], None)] * 2
               + [(1, False, None, [sp], None)] * 3
               + [(1, True, 0.9, [sp], sp)] * 6
               + [(0, False, None, [], None)] * 30)

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
    main.grab = lambda regiao: (TELA_VIVO if roteiro[agora()][0] > 0
                                else TELA_MORTO)
    main.Odometro = OdoFalso
    main.client_rect = lambda win: (0, 0, 1920, 1009)
    main.detect_marks = lambda win, mm=None, cor=None: []
    main.is_usable = lambda win: True
    main.focus_window = lambda win: True
    main.restore_windows = lambda: None
    main.keyboard = type("K", (), {
        "is_pressed": staticmethod(lambda k: False)})()
    main.pyautogui = type("P", (), {
        "press": staticmethod(lambda t: fita.append(("tecla", t))),
        "keyDown": staticmethod(lambda t: None),
        "keyUp": staticmethod(lambda t: None)})()
    main.click_minimap = lambda w, p: fita.append(("mapa", p))
    main.click_game = lambda x, y, pausa=0.09, botao="esquerdo", mod="": \
        fita.append(("clique", (x, y)))
    main.time = type("T", (), {
        "time": staticmethod(lambda: quadro["i"] * 0.3),
        "sleep": staticmethod(loop_sleep)})()
    main.load_monsters = lambda caminho=None: dict(MONSTROS)
    main.load_loot_flags = lambda caminho=None: dict(marcas)
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
    main.LOOT_SO_MARCADOS = so_marcados
    main.LOOT_SO_SE_ACHOU = False
    main.ATTACK_CONFIRM = 2
    main.STOP = False

    saida = io.StringIO()
    with redirect_stdout(saida):
        main.run_bot()
    log = saida.getvalue()
    return {
        "atacou": sum(1 for a in fita
                      if a[0] == "tecla" and a[1] == main.ATTACK_HOTKEY),
        "saqueou": sum(1 for a in fita if a[0] == "clique"),
        "ignorou": "nao esta marcado para saque" in log,
        "log": log,
    }


_load_monsters_real = main.load_monsters
_load_loot_flags_real = main.load_loot_flags

falhas = []
TODOS = {"bicho bom": True, "bicho lixo": True}
SO_BOM = {"bicho bom": True, "bicho lixo": False}

print("um bicho aparece, e atacado e morre. Atacar e saquear sao separados:\n")
print(f"  {'so marcados':<12} {'quem morreu':<12} {'atacou':>7} {'saqueou':>8} "
      f"{'ignorou':>8}")
casos = ((False, "bicho bom", TODOS), (False, "bicho lixo", TODOS),
         (True, "bicho bom", SO_BOM), (True, "bicho lixo", SO_BOM))
res = {}
for so_marcados, quem, marcas in casos:
    r = roda(quem, so_marcados, marcas)
    res[(so_marcados, quem)] = r
    print(f"  {str(so_marcados):<12} {quem:<12} {r['atacou']:>7} "
          f"{r['saqueou']:>8} {str(r['ignorou']):>8}")

# 1) DESLIGADO nao muda nada: saqueia os dois
for quem in ("bicho bom", "bicho lixo"):
    if not res[(False, quem)]["saqueou"]:
        falhas.append(f"com o interruptor desligado, '{quem}' nao foi "
                      f"saqueado: desligado tem de saquear todos, senao a "
                      f"opcao nova tira loot de quem nao pediu nada")

# 2) LIGADO: saqueia o marcado, ignora o desmarcado
if not res[(True, "bicho bom")]["saqueou"]:
    falhas.append("com so-os-marcados ligado, o bicho MARCADO nao foi saqueado")
if res[(True, "bicho lixo")]["saqueou"]:
    falhas.append("com so-os-marcados ligado, o bicho DESMARCADO foi saqueado")
if not res[(True, "bicho lixo")]["ignorou"]:
    falhas.append("ignorou o corpo sem dizer no log por que: o log tem de "
                  "nomear o bicho e o motivo")

# 3) mas ATACA os dois: as escolhas sao separadas
print()
for quem in ("bicho bom", "bicho lixo"):
    n = res[(True, quem)]["atacou"]
    print(f"  com so-os-marcados ligado, atacou '{quem}': {n}x")
    if not n:
        falhas.append(f"deixou de ATACAR '{quem}' por causa da escolha de "
                      f"saque: sao decisoes separadas")

# 4) bicho NAO RECONHECIDO fica de fora quando so os marcados valem
main.LOOT_SO_MARCADOS = True
entra_lig, _nome = main.vale_saquear(DESCONHECIDO, MONSTROS, SO_BOM)
main.LOOT_SO_MARCADOS = False
entra_des, _n = main.vale_saquear(DESCONHECIDO, MONSTROS, SO_BOM)
print(f"\nsprite nao cadastrado: com so-os-marcados ligado entra? {entra_lig} "
      f"| desligado entra? {entra_des}")
if entra_lig:
    falhas.append("bicho nao reconhecido entrou no saque com so-os-marcados "
                  "ligado: marcar so faz sentido se o nao-marcado ficar fora")
if not entra_des:
    falhas.append("bicho nao reconhecido ficou de fora com o interruptor "
                  "DESLIGADO: desligado nao filtra nada")

# 5) o FORMATO ANTIGO (so o sprite) continua valendo como "saqueia"
# roda() substitui load_monsters e load_loot_flags por versoes de mentira; sem
# devolver as de verdade, estes dois casos leriam o fixture em vez do arquivo -
# e passariam sem medir nada.
main.load_monsters = _load_monsters_real
main.load_loot_flags = _load_loot_flags_real
arq = os.path.join(tempfile.gettempdir(), "monstros_teste.json")
with open(arq, "w", encoding="utf-8") as f:
    json.dump({"velho": BOM.tolist(),
               "novo": {"sprite": LIXO.tolist(), "loot": False}}, f)
sprites = main.load_monsters(arq)
flags = main.load_loot_flags(arq)
print(f"\narquivo com as duas formas: sprites={sorted(sprites)}, flags={flags}")
if sprites.get("velho") is None or sprites.get("novo") is None:
    falhas.append(f"nao leu os sprites das duas formas: {sorted(sprites)}")
if flags != {"velho": True, "novo": False}:
    falhas.append(f"flags lidas como {flags}: forma antiga (so o sprite) tem "
                  f"de valer como 'saqueia'")

# 6) salvar por outro motivo NAO apaga a escolha de ninguem
saida = io.StringIO()
with redirect_stdout(saida):
    main.save_monsters(sprites, arq)          # sem passar loot=
depois = main.load_loot_flags(arq)
print(f"depois de salvar sem passar as flags: {depois}")
if depois != {"velho": True, "novo": False}:
    falhas.append(f"salvar a lista sem passar as flags apagou a escolha: "
                  f"{depois}. Aprender um sprite ou renomear nao pode "
                  f"religar o loot de ninguem")
os.remove(arq)

print("\nVEREDITO:", "OK - ataca todos, saqueia so os escolhidos"
      if not falhas else "FALHOU: " + "; ".join(falhas))
