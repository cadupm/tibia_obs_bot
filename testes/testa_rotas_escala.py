# -*- coding: utf-8 -*-
"""Toda rota gravada tem de estar na escala do MINIMAP_PX_SQM atual.

Relatado: "ele ta clicando errado, antes tava correto" - depois de eu medir
MINIMAP_PX_SQM (2.0 -> 1.0, "A escala do minimapa estava dobrada"). Os dois
arquivos de rota do usuario tinham sido gravados quando a CONFIG (nao a
fisica) dizia 2.0, e load_waypoints() guarda essa escala junto com os pontos
justamente para reconverter se o zoom do minimapa mudar de verdade. So que a
minha correcao nao foi uma mudanca de zoom: foi consertar um numero errado. O
codigo nao distingue as duas coisas - ele so ve "a escala do arquivo difere da
escala atual" e reconverte, dividindo cada ponto pela metade.

Medido: os dois arquivos (elder.json, padrao.json) tinham escala_px_sqm=2.0
com MINIMAP_PX_SQM=1.0 hoje; cada waypoint carregava a METADE da distancia
gravada. Migrados batendo byte a byte com o que carregava ANTES do meu fix
(multiplicar os pontos pela escala velha e regravar com a escala nova).

Este teste guarda contra a mesma classe de erro se repetir em silencio: toda
rota em rotas/ tem de estar gravada na escala de hoje. Se um dia alguem mudar
MINIMAP_PX_SQM de novo sem migrar os arquivos, ele acusa aqui - em vez de so
aparecer como "o bot esta clicando errado" numa cacada.
"""
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import main

PASTA = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "rotas")

falhas = []
arquivos = sorted(glob.glob(os.path.join(PASTA, "*.json")))
print(f"MINIMAP_PX_SQM atual: {main.MINIMAP_PX_SQM}")
print(f"{len(arquivos)} rota(s) em {PASTA}\n")

for caminho in arquivos:
    with io.open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    nome = os.path.basename(caminho)
    if not isinstance(dados, dict):
        print(f"  {nome}: formato antigo (lista de pixel) - sem escala para "
              f"conferir")
        continue
    escala = dados.get("escala_px_sqm")
    pontos = dados.get("pontos", [])
    bate = escala is not None and abs(escala - main.MINIMAP_PX_SQM) <= 0.05
    print(f"  {nome}: escala_px_sqm={escala}  pontos={len(pontos)}  "
          f"{'bate' if bate else 'NAO BATE'} com o MINIMAP_PX_SQM de hoje")
    if not bate:
        falhas.append(
            f"{nome} foi gravado com escala {escala}, e MINIMAP_PX_SQM hoje "
            f"e {main.MINIMAP_PX_SQM}. load_waypoints() vai RECONVERTER cada "
            f"ponto por essa diferenca - certo quando o zoom do minimapa "
            f"mudou de verdade, errado quando so a config foi corrigida. "
            f"Migre o arquivo (multiplique pontos pela escala velha, grave "
            f"com a escala de hoje) antes de caçar com ele")

print("\nVEREDITO:", "OK - todas as rotas na escala de hoje"
      if not falhas else "FALHOU: " + "; ".join(falhas))
