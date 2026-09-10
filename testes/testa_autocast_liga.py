# -*- coding: utf-8 -*-
"""O painel tem de dar um jeito de ligar/desligar ENABLE_AUTOCAST.

Bug real: ao enxugar o painel (pedido do usuario: "na de autocast tirar essa
'autocast'"), o bloco inteiro que continha o campo AUTOCAST_MANA_FLOOR foi
removido - e junto com o campo saiu o INTERRUPTOR do bloco (ENABLE_AUTOCAST),
que era outra coisa. Sem widget nenhum ligado a ele, o valor ficou congelado
no que estava salvo (False) e sem jeito de mudar pelo painel: os quatro slots
de autocast podiam estar todos "ativo" que nao adiantava nada, porque
run_autocast() verifica ENABLE_AUTOCAST primeiro.

O proprio relatorio de config no arranque ja acusava isso ("ENABLE_AUTOCAST =
False (padrao True)"), mas so avisava - nao dava como corrigir sem editar o
json a mao. Usuario: "pq o autocast nao ta pegando?"

Este teste garante que existe ALGUM widget no painel escrevendo em
ENABLE_AUTOCAST, para essa classe de erro - campo removido leva o interruptor
do bloco junto - nao se repetir em silencio noutra aba.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import tkinter as tk

import main
import gui

falhas = []

try:
    raiz = tk.Tk()
except tk.TclError as erro:
    print(f"sem display disponivel ({erro}); pulando")
    raise SystemExit(0)

try:
    painel = gui.Painel(raiz)
    raiz.update_idletasks()

    tem_widget = "ENABLE_AUTOCAST" in painel.vars
    print(f"ENABLE_AUTOCAST tem widget no painel? {tem_widget}")
    if not tem_widget:
        falhas.append(
            "nenhum widget do painel controla ENABLE_AUTOCAST - o valor so "
            "pode ser mudado editando o config.json a mao. E exatamente o "
            "bug relatado: os slots de autocast todos marcados 'ativo' e "
            "nada disparava, porque o interruptor geral estava preso em "
            "False sem como religar pela tela")

    if tem_widget:
        var, tipo = painel.vars["ENABLE_AUTOCAST"]
        var.set(True)
        painel.aplicar()
        ligou = main.ENABLE_AUTOCAST is True
        print(f"marcar o widget e Aplicar liga main.ENABLE_AUTOCAST? {ligou}")
        if not ligou:
            falhas.append("marcar o widget nao chega a ligar "
                          "main.ENABLE_AUTOCAST depois de aplicar()")

        var.set(False)
        painel.aplicar()
        desligou = main.ENABLE_AUTOCAST is False
        print(f"desmarcar desliga de volta? {desligou}")
        if not desligou:
            falhas.append("desmarcar o widget nao desliga "
                          "main.ENABLE_AUTOCAST")

    # os quatro slots continuam com o proprio "ativo" - isso NUNCA se perdeu
    tem_slots = bool(getattr(painel, "autocast_vars", None))
    print(f"os slots individuais de autocast continuam no painel? {tem_slots}")
    if not tem_slots:
        falhas.append("os slots de autocast (linhas com tecla e intervalo) "
                      "sumiram do painel")
finally:
    raiz.destroy()

print("\nVEREDITO:", "OK - o painel liga e desliga ENABLE_AUTOCAST"
      if not falhas else "FALHOU: " + "; ".join(falhas))
