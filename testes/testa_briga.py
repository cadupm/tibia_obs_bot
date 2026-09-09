# -*- coding: utf-8 -*-
"""A caverna em C, agora com BRIGAS no meio do caminho (o caso que quebrava).

Durante a briga o trajeto e cancelado: o follow_marks nao roda, so o track_marks
- e o personagem ainda se mexe, porque em chase/kite ele da passos sozinho. E
quando o rastreio se perde de vez, entra o rumo: quem esta atras das costas nao
e escolhido.

SOBRE O TAMANHO DO EMPURRAO. Ele ja foi de +-2.5 por quadro, o que dava uma
mediana de MEIA BANDEIRA arrastada por briga (medido: 6.9 unidades de arco, com
15 entre bandeiras vizinhas), com briga nova a cada ~12 quadros enquanto andar
uma perna leva 8. Nesse regime o personagem era levado pelo mundo mais depressa
do que conseguia andar, e o teste reprovava o bot por isso: instrumentando os
cliques, TODOS eram perfeitos - destino certo, erro zero - e mesmo assim ele
ficava indo e voltando. A taxa de aprovacao era de 3 em 12 sementes, e varias
"falhas" tinham a varredura completa e correta.

Teste que reprova decisao certa nao mede o bot, mede o proprio ruido. Agora o
empurrao e fisico (mediana ~2 de 15, uns 2 SQM por briga), o que e o que os
passos de chase/kite realmente fazem. O teste continua tendo dentes: com a
regra de ouro desligada ele reprova - ver testa_briga_dentes.py.
"""
import math, random
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

import os
random.seed(int(os.environ.get('SEMENTE', '3')))
RAIO, VEL = 52, 2
R = 34
ANG = [-100, -75, -50, -25, 0, 25, 50, 75, 100]
NOMES = ["P1", "P2", "P3", "P4", "ENT", "P5", "P6", "P7", "P8"]
CAMINHO = [(round(R * math.cos(math.radians(a))),
            round(R * math.sin(math.radians(a)))) for a in ANG]
MARCAS = dict(zip(NOMES, CAMINHO))


class Mundo:
    def __init__(self):
        self.acumulado = [0.0]
        for i in range(1, len(CAMINHO)):
            self.acumulado.append(self.acumulado[-1]
                                  + math.dist(CAMINHO[i - 1], CAMINHO[i]))
        self.t = self.acumulado[4]
        self.destino = None
        self.pedra = 0

    @property
    def pos(self):
        for i in range(1, len(self.acumulado)):
            if self.t <= self.acumulado[i]:
                a, b = CAMINHO[i - 1], CAMINHO[i]
                f = ((self.t - self.acumulado[i - 1])
                     / (self.acumulado[i] - self.acumulado[i - 1]))
                return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
        return CAMINHO[-1]

    def anda(self):
        if self.destino is None:
            return
        d = self.destino - self.t
        self.t += max(-VEL, min(VEL, d))
        if abs(self.destino - self.t) < 0.01:
            self.t, self.destino = self.destino, None

    def empurrao(self, quanto):
        """O bicho empurra o personagem para tras enquanto ele luta."""
        self.t = max(0.0, min(self.acumulado[-1], self.t + quanto))


mundo = Mundo()


class Odo:
    def __init__(self):
        self.pos = [0, 0]

    @property
    def parado(self):
        return 0 if mundo.destino is not None else 9

    def atualiza(self):
        self.pos[0] += random.randint(-6, 6)
        self.pos[1] += random.randint(-6, 6)

    def ancora(self, alvo):
        pass


cegueira = {"ate": -1, "quadro": 0}


def visiveis(win, mm=None, cor=None):
    px, py = mundo.pos
    vistas = [(int(round(m[0] - px)), int(round(m[1] - py))) for m in CAMINHO]
    vistas = [v for v in vistas if abs(v[0]) <= RAIO and abs(v[1]) <= RAIO]
    return sorted(vistas, key=lambda m: abs(m[0]) + abs(m[1]))


def clica(win, passo):
    px, py = mundo.pos
    destino = (px + passo[0], py + passo[1])
    i = min(range(len(CAMINHO)), key=lambda k: math.dist(CAMINHO[k], destino))
    if math.dist(CAMINHO[i], destino) > main.MARK_MERGE:
        mundo.pedra += 1
        return
    mundo.destino = mundo.acumulado[i]


main.detect_marks, main.click_minimap = visiveis, clica
odo, estado, cd = Odo(), {}, main.Cooldown(0)
def nome(p):
    """
    Qual bandeira e esta, pela MAIS PROXIMA.

    Era um raio fixo de 3, e a chegada e registrada dentro do track_marks
    enquanto a etiqueta so e lida um quadro depois - tempo de o empurrao da
    briga tirar o personagem do raio. Dava "?" em cima de bandeira de ponta, e
    o veredito concluia que a ponta nunca fora alcancada, reprovando varredura
    completa. As bandeiras estao a 15 de distancia entre si, entao a mais
    proxima nunca e ambigua; "?" agora significa longe de todas mesmo.
    """
    perto = min(MARCAS.items(), key=lambda nm: math.dist(nm[1], p))
    return perto[0] if math.dist(perto[1], p) <= 7 else "?"

visitas, antes, brigas = [], 0, 0
lutando = 0
for quadro in range(9000):
    cegueira["quadro"] = quadro
    odo.atualiza()

    # 1 chance em 60 de aparecer bicho quando esta andando
    if not lutando and random.random() < 1 / 12:
        lutando = random.randint(8, 40)
        brigas += 1
        mundo.destino = None                 # o trajeto e cancelado
        estado["cliques"] = 0

    if lutando:
        lutando -= 1
        mundo.empurrao(random.uniform(-0.8, 0.8))   # empurrao do bicho
        main.track_marks(None, estado, andando=False)   # so acompanha
        if lutando == 0 and random.random() < 0.5:
            # travada: o personagem andou muito sem o bot ler nada e o
            # casamento entre quadros nao fecha mais
            mundo.empurrao(random.choice((-3, 3)))
    else:
        mundo.anda()
        main.follow_marks(None, odo, estado, cd)

    if estado.get("ordem", 0) != antes:
        antes = estado["ordem"]
        visitas.append(nome(mundo.pos))
    if len(visitas) >= 24:
        break

print("\ncorredor em C:", " ".join(NOMES), "(ENT = entrada, no meio)")
print("visitas:", " ".join(visitas))
print(f"brigas no caminho: {brigas} | cliques em parede: {mundo.pedra}")

# "?" e AMOSTRAGEM, nao decisao: e o quadro em que a chegada foi contada com o
# personagem entre duas bandeiras. Contar isso como inversao reprovava varredura
# perfeita - por isso os "?" saem antes de julgar o vaivem.
pontas = [v for v in visitas if v in ("P1", "P8")]
nomeadas = [v for v in visitas if v != "?"]
inverteu_fora_da_ponta = [nomeadas[i] for i in range(1, len(nomeadas) - 1)
                          if nomeadas[i - 1] == nomeadas[i + 1]
                          and nomeadas[i] not in ("P1", "P8")]
print("pontas alcancadas:", set(pontas),
      "| inversoes fora da ponta:", inverteu_fora_da_ponta)
print("VEREDITO:", "OK" if len(set(pontas)) == 2 and not inverteu_fora_da_ponta
      and mundo.pedra == 0 else "FALHOU")
