# -*- coding: utf-8 -*-
"""Roda a suite inteira e diz o estado dela sem enfeitar.

Existe porque ler a suite a olho ja deu errado duas vezes: um teste imprime DOIS
vereditos (o testa_grudado roda outro cenario dentro de si) e um grep pelo
primeiro "OK" escondia um "FALHOU" na mesma saida; outro imprime um traceback de
proposito, para provar que o laco aguenta erro, e parecia quebrado.

As regras aqui sao explicitas:
  - QUALQUER veredito "FALHOU" reprova o arquivo, mesmo que outro diga OK;
  - "PULADO" e uma terceira categoria, e nao um sucesso: e teste que nao rodou
    por falta de uma captura de tela local;
  - saida sem nenhum veredito conta como erro, nao como sucesso silencioso.

    python testes/roda_tudo.py            todos
    python testes/roda_tudo.py loot rota  so os que casam com esses pedacos
"""
import os
import re
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)


def vereditos(saida):
    # o \s* nao e enfeite: um dos testes imprime o veredito indentado, e sem
    # isso ele contava como "nenhum veredito" e virava ERRO
    return [v.strip() for v in
            re.findall(r"^[ \t]*VEREDITO[^\r\n]*", saida, re.M)]


def classifica(saida, codigo):
    linhas = vereditos(saida)
    if any("FALHOU" in v for v in linhas):
        return "FALHOU"
    if any("PULADO" in v for v in linhas):
        return "PULADO"
    if linhas and codigo == 0:
        return "ok"
    return "ERRO"


def main():
    filtros = [a.lower() for a in sys.argv[1:]]
    arquivos = sorted(f for f in os.listdir(AQUI)
                      if f.startswith("testa_") and f.endswith(".py")
                      and (not filtros or any(x in f.lower() for x in filtros)))
    if not arquivos:
        print("nenhum teste casou com", filtros)
        return 1

    contagem = {"ok": 0, "FALHOU": 0, "PULADO": 0, "ERRO": 0}
    ruins = []
    inicio = time.time()
    for nome in arquivos:
        t0 = time.time()
        r = subprocess.run([sys.executable, os.path.join(AQUI, nome)],
                           capture_output=True, text=True, cwd=RAIZ)
        saida = (r.stdout or "") + (r.stderr or "")
        estado = classifica(saida, r.returncode)
        contagem[estado] += 1
        marca = {"ok": "  ", "FALHOU": "->", "PULADO": " ~", "ERRO": "->"}[estado]
        print(f"{marca} {nome:<30} {estado:<7} {time.time() - t0:>5.1f}s")
        if estado != "ok":
            ruins.append((nome, estado, saida))

    print(f"\n{len(arquivos)} teste(s) em {time.time() - inicio:.0f}s: "
          + ", ".join(f"{n} {k}" for k, n in contagem.items() if n))

    for nome, estado, saida in ruins:
        print(f"\n--- {nome} ({estado})")
        linhas = vereditos(saida)
        if linhas:
            for v in linhas:
                print("    " + v)
        else:
            for linha in saida.strip().splitlines()[-6:]:
                print("    " + linha)

    return 1 if contagem["FALHOU"] or contagem["ERRO"] else 0


if __name__ == "__main__":
    sys.exit(main())
