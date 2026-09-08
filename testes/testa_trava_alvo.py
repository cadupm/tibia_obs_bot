# -*- coding: utf-8 -*-
"""So troca de alvo quando o bicho SUMIR da battle list.

Roda a trava contra leituras montadas a mao, incluindo o caso que o usuario
descreveu: o bicho com 1 de vida, moldura piscando, entrada ainda na lista.
"""
import sys
import numpy as np
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

A = np.full((17, 20, 3), 40, dtype=np.uint8)      # sprite do bicho A
A[3:8, 3:8] = (200, 30, 30)
B = np.full((17, 20, 3), 40, dtype=np.uint8)      # sprite do bicho B
B[9:14, 9:14] = (30, 200, 30)


def roda(nome, leituras):
    """leituras: (alvo, alvo_sprite, [sprites]) por quadro; imprime as decisoes."""
    trava = main.TravaDeAlvo()
    saida = []
    tempo = 0.0
    for alvo, alvo_sprite, sprites in leituras:
        tempo += 0.2
        saida.append(trava.atualiza(alvo, alvo_sprite, sprites, agora=tempo))
    print(f"\n{nome}")
    print("  pode apertar a tecla de atacar:", saida)
    return saida


falhas = []

# 1) engaja A e A vai morrendo: moldura some por leitura ruim, entrada continua
pode = roda("bicho com 1 de vida, moldura piscando",
            [(False, None, [A]),          # antes de engajar: pode atacar
             (True, A, [A]),              # engajou
             (False, None, [A]),          # moldura sumiu, ele continua na lista
             (False, None, [A]),
             (False, None, [A]),
             (True, A, [A])])             # moldura voltou
if pode != [True, False, False, False, False, False]:
    falhas.append("segurou errado com o bicho ainda na lista")

# 2) o bicho morre: some da lista
pode = roda("o bicho morre e some da lista",
            [(True, A, [A, B]),           # engajado, dois na lista
             (False, None, [A, B]),       # leitura ruim: nao pode trocar
             (False, None, [B])])         # A sumiu: pode
if pode != [False, False, True]:
    falhas.append("nao liberou quando o bicho sumiu")

# 3) dois bichos IGUAIS: so libera quando o numero cai
pode = roda("dois bichos iguais, um morre",
            [(True, A, [A, A]),
             (False, None, [A, A]),       # os dois vivos: segura
             (False, None, [A])])         # um morreu: libera
if pode != [False, False, True]:
    falhas.append("errou com dois bichos iguais")

# 4) leitura ruim teimosa: solta depois de TARGET_LOST_MAX
longa = [(True, A, [A])] + [(False, None, [A])] * 40
pode = roda(f"moldura sumida por mais de {main.TARGET_LOST_MAX:.0f}s", longa)
if pode[-1] is not True:
    falhas.append("nunca soltou o alvo travado")
soltou_em = next((i for i, v in enumerate(pode) if v), None)
print(f"  soltou na leitura {soltou_em} (~{soltou_em * 0.2:.1f}s)")

print("\nVEREDITO:", "OK - so troca quando some da lista" if not falhas
      else "FALHOU: " + "; ".join(falhas))
