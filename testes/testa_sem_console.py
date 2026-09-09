# -*- coding: utf-8 -*-
"""O painel funciona SEM CONSOLE.

Aberto por atalho ou com pythonw - o jeito natural de rodar um painel, sem
janela preta atras - o Python deixa `sys.stdout` e `sys.stderr` em None. O
FilaDeSaida chamava `original.write(...)` e estourava no PRIMEIRO print do bot:

    [gui] iniciando; o foco vai para o jogo
    [erro] AttributeError: 'NoneType' object has no attribute 'write'
    [gui] bot encerrado

A cacada morria no arranque, e o painel seguia aberto como se estivesse tudo
bem. Console ausente nao e erro: e so nao ter para onde ecoar - o log do painel
continua tendo de receber tudo.
"""
import os
import sys
import queue
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o gui.py
import gui

falhas = []

# ------------------------------------- 1) sem console: escreve sem estourar
fila = queue.Queue()
saida = gui.FilaDeSaida(fila, None)       # None = pythonw, sem console
try:
    saida.write("[bot] primeira linha" + chr(10))
    saida.write("   \n")                  # espaco em branco nao vira linha
    saida.flush()
    print("sem console: write e flush passaram")
except Exception as erro:
    falhas.append(f"sem console, o write estourou: {type(erro).__name__}: "
                  f"{erro} - e assim que a cacada morria no arranque")
    print(f"sem console: ESTOUROU {type(erro).__name__}: {erro}")

recebido = []
while not fila.empty():
    recebido.append(fila.get())
print(f"  o log recebeu {recebido}")
if recebido != ["[bot] primeira linha"]:
    falhas.append(f"o log recebeu {recebido}, esperava so a linha com texto")

# ------------------------------------- 2) com console: ecoa nos dois
class Espiao:
    def __init__(self):
        self.texto = []
        self.vezes = 0

    def write(self, t):
        self.texto.append(t)

    def flush(self):
        self.vezes += 1


espiao = Espiao()
fila = queue.Queue()
saida = gui.FilaDeSaida(fila, espiao)
saida.write("[bot] com console" + chr(10))
saida.flush()
print(f"\ncom console: ecoou {espiao.texto}, flush {espiao.vezes}x")
if not espiao.texto:
    falhas.append("com console, nao ecoou no console")
if fila.empty():
    falhas.append("com console, nao mandou para o log do painel")

# ------------------------- 3) o print() do Python aceita como stdout
# `print` pergunta o retorno do write em algumas situacoes, e o traceback
# pergunta isatty/writable antes de escrever. Faltando qualquer um deles, o
# erro aparece DENTRO do tratamento de erro - o pior lugar.
import traceback
fila = queue.Queue()
antigo, antigo_err = sys.stdout, sys.stderr
sys.stdout = gui.FilaDeSaida(fila, None)
sys.stderr = gui.FilaDeSaida(fila, None)
estourou = None
try:
    print("[bot] pelo print de verdade")
    try:
        raise ValueError("erro de mentira, para ver se o traceback sai")
    except ValueError:
        traceback.print_exc()
except Exception as erro:
    estourou = erro
finally:
    sys.stdout, sys.stderr = antigo, antigo_err

linhas = []
while not fila.empty():
    linhas.append(fila.get())
print(f"\nprint() e traceback.print_exc() com stdout/stderr trocados: "
      f"{'ESTOUROU ' + str(estourou) if estourou else 'ok'}")
print(f"  chegaram {len(linhas)} bloco(s) no log")
for l in linhas:
    print("    | " + l.splitlines()[0][:70])
if estourou:
    falhas.append(f"print/traceback estourou com o FilaDeSaida: {estourou}")
if not any("pelo print de verdade" in l for l in linhas):
    falhas.append("o print() comum nao chegou ao log")
if not any("erro de mentira" in l for l in linhas):
    falhas.append("o traceback nao chegou ao log: erro do bot ficaria invisivel")

print("\nVEREDITO:", "OK - o painel escreve no log com ou sem console"
      if not falhas else "FALHOU: " + "; ".join(falhas))
