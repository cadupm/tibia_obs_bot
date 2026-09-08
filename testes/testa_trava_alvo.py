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

# 2) o bicho morre: some da lista. Uma leitura sem ele NAO basta - leitura ruim
# e comum, e enquanto o bot acha que ha bicho ele nao clica no mapa (clique
# durante o ataque troca chase/stand no cliente).
pode = roda(f"o bicho morre e some da lista "
            f"({main.TARGET_GONE_READS} leituras para valer)",
            [(True, A, [A, B]),                        # engajado, dois na lista
             (False, None, [A, B])]                    # leitura ruim: segura
            + [(False, None, [B])] * main.TARGET_GONE_READS)   # A sumiu de vez
esperado = [False, False] + [False] * (main.TARGET_GONE_READS - 1) + [True]
if pode != esperado:
    falhas.append(f"morte: esperava {esperado}, saiu {pode}")

# 3) dois bichos IGUAIS: so libera quando o numero cai e continua caido
pode = roda("dois bichos iguais, um morre",
            [(True, A, [A, A]),
             (False, None, [A, A])]                    # os dois vivos: segura
            + [(False, None, [A])] * main.TARGET_GONE_READS)   # um morreu
esperado = [False, False] + [False] * (main.TARGET_GONE_READS - 1) + [True]
if pode != esperado:
    falhas.append(f"dois iguais: esperava {esperado}, saiu {pode}")

# 4) a entrada PISCA: sumiu uma leitura e voltou. Nao pode contar como morte.
pode = roda("entrada piscou e voltou",
            [(True, A, [A]),
             (False, None, []),           # apagao de uma leitura
             (False, None, [A]),          # voltou: o bicho esta vivo
             (False, None, [A])])
if any(pode):
    falhas.append(f"tratou piscada como morte: {pode}")

# 4) leitura ruim teimosa: solta depois de TARGET_LOST_MAX
longa = [(True, A, [A])] + [(False, None, [A])] * 40
pode = roda(f"moldura sumida por mais de {main.TARGET_LOST_MAX:.0f}s", longa)
if pode[-1] is not True:
    falhas.append("nunca soltou o alvo travado")
soltou_em = next((i for i, v in enumerate(pode) if v), None)
print(f"  soltou na leitura {soltou_em} (~{soltou_em * 0.2:.1f}s)")

# 5) o bicho fica quase morto e o cliente ESCURECE o sprite dele na lista.
# Continua sendo ele: escurecer nao e morrer.
ESCURO = (A.astype(float) * 0.35).astype(np.uint8)
pode = roda("sprite escurecido (bicho quase morto)",
            [(True, A, [A])] + [(False, None, [ESCURO])] * 4)
print("  o sprite escuro casa com o claro?", main.sprite_igual(ESCURO, A))
if any(pode):
    falhas.append(f"tratou sprite escurecido como morte: {pode}")

print("\nVEREDITO:", "OK - so troca quando some da lista" if not falhas
      else "FALHOU: " + "; ".join(falhas))
