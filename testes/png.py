# -*- coding: utf-8 -*-
"""Leitor de PNG em numpy, sem dependencia externa.

Existe porque os testes precisam abrir as capturas de tela salvas e o projeto
nao usa Pillow: o mss escreve PNG mas nao le. Cobre o que as capturas produzem -
8 bits por canal, RGB ou RGBA, sem entrelacamento - e nada mais.
"""
import struct
import zlib

import numpy as np


def le(caminho):
    """Devolve a imagem como array (altura, largura, 3) em uint8."""
    with open(caminho, "rb") as f:
        dados = f.read()
    if dados[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{caminho} nao e PNG")

    pos, cabecalho, pedacos = 8, None, []
    while pos < len(dados):
        tamanho, tipo = struct.unpack(">I4s", dados[pos:pos + 8])
        corpo = dados[pos + 8:pos + 8 + tamanho]
        pos += 12 + tamanho                      # 12 = tamanho + tipo + crc
        if tipo == b"IHDR":
            cabecalho = struct.unpack(">IIBBBBB", corpo)
        elif tipo == b"IDAT":
            pedacos.append(corpo)
        elif tipo == b"IEND":
            break

    larg, alt, bits, cor, _comp, _filtro, entrelace = cabecalho
    if bits != 8 or entrelace or cor not in (2, 6):
        raise ValueError(f"PNG fora do previsto: bits={bits} cor={cor} "
                         f"entrelace={entrelace}")
    canais = 3 if cor == 2 else 4
    cru = zlib.decompress(b"".join(pedacos))

    # cada linha vem com um byte de filtro na frente, e o filtro se desfaz
    # olhando a linha de cima (b) e o pixel a esquerda (a)
    passo = larg * canais
    saida = np.zeros((alt, passo), dtype=np.uint8)
    anterior = np.zeros(passo, dtype=np.int16)
    for y in range(alt):
        inicio = y * (passo + 1)
        filtro = cru[inicio]
        linha = np.frombuffer(cru[inicio + 1:inicio + 1 + passo],
                              dtype=np.uint8).astype(np.int16).copy()
        if filtro == 1:                          # Sub
            for x in range(canais, passo):
                linha[x] = (linha[x] + linha[x - canais]) & 0xFF
        elif filtro == 2:                        # Up
            linha = (linha + anterior) & 0xFF
        elif filtro == 3:                        # Average
            for x in range(passo):
                esq = linha[x - canais] if x >= canais else 0
                linha[x] = (linha[x] + ((esq + anterior[x]) >> 1)) & 0xFF
        elif filtro == 4:                        # Paeth
            for x in range(passo):
                a = linha[x - canais] if x >= canais else 0
                b = anterior[x]
                c = anterior[x - canais] if x >= canais else 0
                p = a + b - c
                escolha = min((abs(p - a), a), (abs(p - b), b),
                              (abs(p - c), c))[1]
                linha[x] = (linha[x] + escolha) & 0xFF
        elif filtro != 0:
            raise ValueError(f"filtro de PNG desconhecido: {filtro}")
        saida[y] = linha.astype(np.uint8)
        anterior = linha

    img = saida.reshape(alt, larg, canais)
    return img[:, :, :3]
