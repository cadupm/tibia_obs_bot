# -*- coding: utf-8 -*-
"""O corpo esta onde uma BARRA DE VIDA DESAPARECEU.

Fato do cliente, dito por quem joga: bicho morto perde a barra de vida e o
nome, sobrando so a sprite do cadaver. Entao o quadrado que tinha barra e nao
tem mais e, por definicao, onde ele caiu.

Isso substitui uma comparacao de IMAGEM que decidia no ruido. Numa cacada de
verdade ela media:

    14 contra 12 (limiar 12)
    16 contra 12
    17 contra 17

O vencedor mal passava do limiar e mal passava do segundo - e punha corpo a 2, 3
e 5 SQM num modo stand CORPO A CORPO, onde todo corpo tem de estar a 1. Os
unicos saques que funcionaram foram os que sairam a 1 SQM, por acidente.

A barra que sumiu e o MESMO detector que o bot ja usa para achar criatura, e a
resposta e discreta: sumiu ou nao sumiu. Nao ha limiar para calibrar nem empate
para desfazer.

O que se mede aqui:
  - um bicho morre: o quadrado dele e apontado, exato;
  - dois morrem juntos: os dois quadrados, o mais perto primeiro;
  - o sobrevivente NAO e apontado;
  - com o personagem tendo ANDADO entre as duas leituras, o deslocamento e
    descontado;
  - ninguem sumiu -> lista vazia, e ai o bot cai na comparacao de imagem.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import main

falhas = []
print("barras antes -> barras agora  =>  onde os bichos morreram\n")


def mostra(rotulo, havia, agora, andou, esperado):
    global falhas
    deu = main.barras_que_sumiram(havia, agora, andou)
    print(f"  {rotulo}")
    print(f"     havia {list(havia)} | agora {list(agora)} | "
          f"andou {andou} -> {deu}")
    if deu != esperado:
        falhas.append(f"{rotulo}: deu {deu}, esperava {esperado}")


# ------------------------------------------- 1) um bicho, uma morte
mostra("um bicho colado morre",
       havia=[(1, 0)], agora=[], andou=(0, 0), esperado=[(1, 0)])

# ------------------------------------------- 2) o sobrevivente nao conta
mostra("dois bichos, morre o de (1,0)",
       havia=[(1, 0), (0, 2)], agora=[(0, 2)], andou=(0, 0),
       esperado=[(1, 0)])

# ------------------------------------------- 3) dois de uma vez, perto primeiro
# Com o grupo todo com pouca vida, duas entradas somem na mesma leitura. A
# primeira a saquear e a mais perto: e a que nao exige andar.
mostra("morrem os dois, o de (3,3) e o de (1,0)",
       havia=[(3, 3), (1, 0)], agora=[], andou=(0, 0),
       esperado=[(1, 0), (3, 3)])

# ------------------------------------------- 4) o personagem ANDOU
# Offset e relativo ao personagem, e o personagem se move: andando 1 SQM para a
# direita, o bicho que estava em (2,0) aparece em (1,0). Sem descontar, o
# quadrado sai errado - que era exatamente o erro que a odometria cometia.
mostra("bicho em (2,0) morre depois de o personagem andar 1 para a direita",
       havia=[(2, 0)], agora=[], andou=(1, 0), esperado=[(1, 0)])
mostra("...e o sobrevivente de (4,0), agora em (3,0), continua vivo",
       havia=[(2, 0), (4, 0)], agora=[(3, 0)], andou=(1, 0),
       esperado=[(1, 0)])

# ------------------------------------------- 5) ninguem sumiu
mostra("ninguem sumiu (o bicho morreu fora da tela)",
       havia=[(1, 0)], agora=[(1, 0)], andou=(0, 0), esperado=[])
mostra("nao havia barra nenhuma de referencia",
       havia=[], agora=[], andou=(0, 0), esperado=[])

# ------------------------------------------- 6) repetido nao vira dois corpos
mostra("a mesma barra listada duas vezes",
       havia=[(1, 0), (1, 0)], agora=[], andou=(0, 0), esperado=[(1, 0)])

# ---------------------------- 7) o caso do log: stand corpo a corpo
# Em stand os bichos que batem em voce estao COLADOS, entao todo corpo sai a
# 1 SQM. A comparacao de imagem punha corpo a 5 SQM; o desaparecimento da barra
# nao tem como: ele so aponta quadrado que TINHA barra.
havia = [(1, 0), (0, 1), (-1, 0)]
deu = main.barras_que_sumiram(havia, [(0, 1), (-1, 0)], (0, 0))
longe = [q for q in deu if max(abs(q[0]), abs(q[1])) > 1]
print(f"\n  tres bichos colados, morre o de (1,0): {deu}")
print(f"     algum corpo apontado longe de 1 SQM? {longe or 'nenhum'}")
if longe:
    falhas.append(f"apontou corpo longe ({longe}) com todos os bichos colados: "
                  f"so pode apontar quadrado que TINHA barra")

print("\nVEREDITO:", "OK - o quadrado onde a barra sumiu e onde o bicho caiu"
      if not falhas else "FALHOU: " + "; ".join(falhas))
