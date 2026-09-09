# -*- coding: utf-8 -*-
"""Achar o corpo NA TELA, em vez de tentar e errar no anel em volta.

A posicao do corpo vinha de odometria e erra por 1 SQM com facilidade - dai a
varredura do anel, que e tentativa e erro. Mas ha um sinal direto na tela: o
quadrado onde o bicho estava MUDA quando ele morre (sprite de bicho -> sprite
de corpo), e o quadrado vizinho que nunca teve bicho continua igual. Quem mudou
e onde caiu.

Nao e reconhecimento de sprite de corpo: isso mudaria de especie para especie e
precisaria de uma tabela por bicho. E "este quadrado ficou diferente", que vale
para qualquer bicho, inclusive um que o bot nunca viu.

O que se mede aqui:
  - acha o quadrado certo, e nao o vizinho;
  - acha mesmo com o personagem tendo ANDADO entre os dois quadros (o viewport
    acompanha o personagem, entao o mesmo lugar do mundo aparece deslocado);
  - com chao animado em tudo, ou com dois quadrados mudando igual, ele DIZ que
    nao sabe em vez de chutar - e ai vale o palpite com a varredura;
  - o quadrado do proprio personagem nao e escolhido a esmo.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import numpy as np
import main

rng = np.random.default_rng(7)
_vx, _vy, VW, VH = main.GAME_VIEW
MEIO_COL, MEIO_LIN = (VW // main.TILE_PX) // 2, (VH // main.TILE_PX) // 2


def chao():
    """Uma caverna de pedra: textura fixa, para o chao nao mudar sozinho."""
    return rng.integers(40, 70, (VH, VW, 3), dtype=np.uint8)


def poe(img, offset, cor, tamanho=44):
    """Desenha um bicho/corpo no quadrado dado."""
    x0 = (MEIO_COL + offset[0]) * main.TILE_PX + (main.TILE_PX - tamanho) // 2
    y0 = (MEIO_LIN + offset[1]) * main.TILE_PX + (main.TILE_PX - tamanho) // 2
    img[y0:y0 + tamanho, x0:x0 + tamanho] = cor
    return img


falhas = []
print(f"limiar de mudanca: {main.LOOT_DIFF_MIN} por pixel | margem sobre o "
      f"segundo: {main.LOOT_DIFF_MARGEM}x")
print(f"anel de busca: {len(main.quadrados_do_saque())} quadrados\n")

# --------------------------------- 1) o basico: bicho em (2,0), morre ali
BASE = chao()
antes = poe(BASE.copy(), (2, 0), (170, 40, 40))       # bicho vivo, vermelho
depois = poe(BASE.copy(), (2, 0), (90, 70, 50))       # corpo, marrom
achou, nota, segundo = main.acha_o_corpo(antes, depois, (2, 0), (0, 0))
print(f"bicho e corpo em (2,0), palpite certo: achou {achou} "
      f"(mudou {nota:.0f}, segundo {segundo:.0f})")
if achou != (2, 0):
    falhas.append(f"palpite certo e achou {achou}, esperava (2,0)")

# ------------------- 2) o palpite ERRA por 1 SQM: e para isso que serve
achou, nota, segundo = main.acha_o_corpo(antes, depois, (3, 0), (0, 0))
print(f"palpite errado em 1 SQM (3,0): achou {achou} "
      f"(mudou {nota:.0f}, segundo {segundo:.0f})")
if achou != (2, 0):
    falhas.append(f"com palpite errado em 1 SQM achou {achou}, esperava (2,0). "
                  f"Corrigir o erro do palpite e a razao de existir disto")

# --------------- 3) o personagem ANDOU entre os dois quadros
# O viewport acompanha o personagem: andando 1 SQM para a direita, o mesmo
# lugar do mundo aparece 1 quadrado mais a esquerda no quadro novo.
antes2 = poe(chao().copy(), (2, 0), (170, 40, 40))
base_dep = chao()
depois2 = poe(base_dep.copy(), (1, 0), (90, 70, 50))   # corpo, ja deslocado
# ...mas o chao tem de ser o MESMO lugar do mundo, deslocado junto
desl = np.roll(antes2, -main.TILE_PX, axis=1)
depois2 = poe(desl.copy(), (1, 0), (90, 70, 50))
achou, nota, segundo = main.acha_o_corpo(antes2, depois2, (1, 0), (1, 0))
print(f"personagem andou 1 SQM: achou {achou} "
      f"(mudou {nota:.0f}, segundo {segundo:.0f})")
if achou != (1, 0):
    falhas.append(f"com o personagem andando achou {achou}, esperava (1,0): o "
                  f"alinhamento entre os quadros nao esta sendo feito")

# --------------- 4) chao animado em TUDO: tem de admitir que nao sabe
ruidoso_a = chao()
ruidoso_b = chao()                              # textura toda diferente
achou, nota, segundo = main.acha_o_corpo(ruidoso_a, ruidoso_b, (2, 0), (0, 0))
print(f"\nchao mudando em tudo (agua/fogo): achou {achou} "
      f"(maior {nota:.0f}, segundo {segundo:.0f})")
if achou is not None:
    falhas.append(f"com tudo mudando ele chutou {achou}. Tem de dizer que nao "
                  f"sabe e deixar o palpite da odometria com a varredura")

# --------------- 5) dois quadrados mudando igual: tambem nao sabe
empate_a = poe(poe(BASE.copy(), (2, 0), (170, 40, 40)), (0, 2), (170, 40, 40))
empate_b = poe(poe(BASE.copy(), (2, 0), (90, 70, 50)), (0, 2), (90, 70, 50))
achou, nota, segundo = main.acha_o_corpo(empate_a, empate_b, (1, 1), (0, 0))
print(f"dois bichos morrendo em quadrados diferentes: achou {achou} "
      f"(maior {nota:.0f}, segundo {segundo:.0f})")
if achou is not None:
    falhas.append(f"com empate ele escolheu {achou} sem margem: e chute")

# --------------- 6) nada mudou: nao ha corpo para achar
achou, nota, segundo = main.acha_o_corpo(BASE, BASE.copy(), (2, 0), (0, 0))
print(f"nada mudou na tela: achou {achou} (maior {nota:.0f})")
if achou is not None:
    falhas.append(f"sem mudanca nenhuma ele apontou {achou}")

# --------------- 7) desligado devolve nada, sem estourar
main.LOOT_ACHA_CORPO = False
achou, _n, _s = main.acha_o_corpo(antes, depois, (2, 0), (0, 0))
print(f"com LOOT_ACHA_CORPO desligado: achou {achou}")
if achou is not None:
    falhas.append("desligado e mesmo assim opinou")
main.LOOT_ACHA_CORPO = True

# --------------- 7b) desligar a VARREDURA nao pode encolher a BUSCA
# Sao dois aneis com o mesmo desenho e razoes opostas: a varredura de tecla e
# chutar em volta, e a busca na tela e medir. Compartilhando a mesma funcao,
# desligar a varredura fazia o bot procurar o corpo num quadrado so - o do
# palpite, que a busca existe justamente para corrigir.
guardado = main.LOOT_VARRE
main.LOOT_VARRE = False
busca_sem, varre_sem = len(main.anel_de_busca()), len(main.quadrados_do_saque())
main.LOOT_VARRE = True
busca_com = len(main.anel_de_busca())
main.LOOT_VARRE = guardado
print(f"\ncom a varredura desligada: busca em {busca_sem} quadrado(s), "
      f"varredura em {varre_sem}")
if busca_sem != busca_com or busca_sem < 9:
    falhas.append(f"desligar a varredura encolheu a busca para {busca_sem} "
                  f"quadrado(s): o bot passaria a procurar o corpo so no "
                  f"quadrado do palpite, que e o erro que a busca corrige")

# --------------- 8) quanto o corpo muda, de fato: o numero que calibra
print(f"\npara calibrar LOOT_DIFF_MIN (hoje {main.LOOT_DIFF_MIN}):")
for rotulo, a, b in (("bicho -> corpo", antes, depois),
                     ("chao -> chao (mesmo lugar)", BASE, BASE.copy()),
                     ("chao -> outro chao", ruidoso_a, ruidoso_b)):
    d = main.mudou_quanto(main.recorte_do_quadrado(a, (2, 0)),
                          main.recorte_do_quadrado(b, (2, 0)))
    print(f"  {rotulo:<28} {d:>6.1f} por pixel")

print("\nVEREDITO:", "OK - separa o quadrado do corpo, e admite quando nao da"
      if not falhas else "FALHOU: " + "; ".join(falhas))
