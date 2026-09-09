# -*- coding: utf-8 -*-
"""O painel cabe na tela e da para chegar em tudo dentro dele.

Este teste existe porque a falha foi silenciosa: a aba Combate ganhou Kite,
Paralisia e Loot, a janela passou da altura da tela e o bloco "Monstros para
atacar" ficou abaixo do corte, sem barra de rolagem - sem erro, sem log, sem
nada. A GUI abria bonita e faltava metade.

O que se mede aqui:
  - a janela nao passa da borda de baixo da tela;
  - conteudo maior que a aba ganha barra de rolagem;
  - rolando ate o fim, o ULTIMO bloco de cada aba fica visivel;
  - a roda do mouse rola a aba, mas NAO quando o ponteiro esta sobre um widget
    que rola sozinho (a lista de monstros, a arvore da rota) - senao as duas
    rolagens brigam.

Precisa de um ambiente com tela (tkinter). Sem isso, PULA.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o gui.py
import tkinter as tk

try:
    _raiz = tk.Tk()
except tk.TclError as erro:
    print(f"PULADO: sem tela para abrir janela ({erro})")
    print("VEREDITO: PULADO - a GUI precisa de um ambiente grafico")
    raise SystemExit(0)

import gui
import main

painel = gui.Painel(_raiz)
_raiz.update_idletasks()
_raiz.update()
_raiz.update_idletasks()
# O corte de altura e agendado com after_idle no painel. Esperar que ele tenha
# rodado deixava o teste FLAKY: sozinho passava, dentro do runner (com a
# maquina ocupada) media alturas ainda em zero e reprovava sem defeito nenhum.
# Chamar de proposito e deterministico e exercita o mesmo codigo.
painel._ajusta_altura()
_raiz.update_idletasks()
_raiz.update()

falhas = []
tela_h = _raiz.winfo_screenheight()
topo = gui.ALTURA_BARRAS + 40
alto = _raiz.winfo_reqheight()
print(f"tela {_raiz.winfo_screenwidth()}x{tela_h} | janela "
      f"{_raiz.winfo_reqwidth()}x{alto} em y={topo} -> borda de baixo em "
      f"{topo + alto}")
if topo + alto > tela_h:
    falhas.append(f"a janela passa da tela: borda em {topo + alto}, tela tem "
                  f"{tela_h}. O que sobra embaixo fica inalcancavel")

print()
for indice, (nome, _blocos) in enumerate(gui.ABAS):
    canvas, dentro, barra = painel.telas[indice]
    painel.notas.select(indice)
    _raiz.update_idletasks()
    _raiz.update()
    precisa, cabe = dentro.winfo_reqheight(), canvas.winfo_height()
    rola = precisa > cabe
    tem_barra = bool(barra.winfo_ismapped())
    print(f"  {nome:<9} conteudo {precisa:>4}px em {cabe:>4}px "
          f"-> {'rola' if rola else 'cabe inteiro'}, "
          f"barra {'sim' if tem_barra else 'nao'}")
    if rola and not tem_barra:
        falhas.append(f"aba {nome}: conteudo de {precisa}px em {cabe}px e "
                      f"nenhuma barra de rolagem")

    # o ultimo bloco da aba fica alcancavel rolando ate o fim?
    filhos = [w for w in dentro.winfo_children() if w.winfo_ismapped()]
    if filhos:
        canvas.yview_moveto(1.0)
        _raiz.update_idletasks()
        ultimo = filhos[-1]
        y = ultimo.winfo_rooty() - canvas.winfo_rooty()
        visivel = -2 <= y < cabe
        print(f"            ultimo bloco a {y}px do topo depois de rolar "
              f"-> {'visivel' if visivel else 'FORA DA VISTA'}")
        if not visivel:
            falhas.append(f"aba {nome}: rolando ate o fim, o ultimo bloco "
                          f"ainda fica em y={y} (visivel e 0..{cabe})")
        canvas.yview_moveto(0.0)
        _raiz.update_idletasks()

# ------------------------------------------------- a roda do mouse
def roda(canvas, sobre, do_fim=False):
    """
    Gira a roda sobre `sobre` e devolve o yview antes e depois.

    A posicao de partida importa por dois motivos que ja quebraram o teste:

      - partindo de um ponto fixo (era 0.35), a aba Combate encurtou, 0.35
        virou o FIM da rolagem e girar para baixo nao tinha mais para onde ir -
        o teste reprovava por falta de espaco, e nao por defeito;
      - o widget que se quer testar precisa estar VISIVEL, senao o ponteiro cai
        noutro lugar e a exclusao nem e exercitada. A lista de monstros fica no
        fim da aba: no topo da rolagem ela nao esta na tela.

    Por isso: do fim rolando para CIMA quando o alvo esta embaixo, do topo
    rolando para BAIXO quando e area comum. Nos dois casos ha para onde ir.
    """
    canvas.yview_moveto(1.0 if do_fim else 0.0)
    _raiz.update_idletasks()
    antes = canvas.yview()[0]
    painel._liga_roda(canvas)
    painel._roda(type("E", (), {"delta": 120 if do_fim else -120,
                                "x_root": sobre.winfo_rootx() + 5,
                                "y_root": sobre.winfo_rooty() + 5})())
    _raiz.update_idletasks()
    return antes, canvas.yview()[0]

print()
# A ABA TEM DE TER PARA ONDE ROLAR, senao o teste mede falta de espaco e nao
# defeito. Qual aba e a mais alta muda conforme o painel ganha e perde campos -
# a Combate ja foi a maior e hoje tem tres linhas -, entao a escolha e por
# medida, e nao por indice fixo.
rolaveis = []
for i, (canvas, dentro, _barra) in enumerate(painel.telas):
    painel.notas.select(i)
    _raiz.update_idletasks()
    _raiz.update()
    if dentro.winfo_reqheight() > canvas.winfo_height() + 4:
        rolaveis.append(i)
if not rolaveis:
    print("nenhuma aba precisa rolar: o painel inteiro cabe na tela, e a roda "
          "nao tem o que exercitar")
else:
    i = rolaveis[0]
    painel.notas.select(i)
    _raiz.update_idletasks()
    _raiz.update()
    canvas = painel.telas[i][0]
    antes, depois = roda(canvas, canvas)
    nome = painel.notas.tab(i, "text")
    print(f"roda sobre area comum da {nome}: {antes:.3f} -> {depois:.3f}")
    if depois == antes:
        falhas.append(f"a roda do mouse nao rola a aba {nome}")

for atributo, rotulo in (("lista_monstros", "lista de monstros"),
                         ("lista_rota", "arvore da rota")):
    widget = getattr(painel, atributo, None)
    if widget is None:
        falhas.append(f"nao achei o widget {atributo} para testar a roda")
        continue
    painel.notas.select(1 if atributo == "lista_monstros" else 2)
    _raiz.update_idletasks()
    _raiz.update()
    canvas = painel.telas[1 if atributo == "lista_monstros" else 2][0]
    # do fim para cima: e onde esses dois widgets estao, e la ha para onde subir
    antes, depois = roda(canvas, widget, do_fim=True)
    parou = abs(depois - antes) < 1e-6
    print(f"roda sobre a {rotulo} ({widget.winfo_class()}): "
          f"{antes:.3f} -> {depois:.3f} "
          f"-> {'a aba ficou parada' if parou else 'ROLOU A ABA JUNTO'}")
    if not parou:
        falhas.append(f"a roda sobre a {rotulo} rolou a aba junto: quem tem "
                      f"rolagem propria fica com a roda, senao as duas brigam")

# ------------------------------------------------- a caixa de marcar do saque
# Era "$ " no texto do Listbox mais um botao "Saquear: sim/nao" para alternar o
# selecionado: duas etapas para uma decisao de um clique, e um simbolo a
# explicar. Agora e Treeview com coluna clicavel - o gesto que se espera de uma
# caixa de marcar.
painel.notas.select(1)
_raiz.update_idletasks()
_raiz.update()
lista = painel.lista_monstros
print(f"\nlista de monstros: {lista.winfo_class()}, "
      f"{len(lista.get_children())} linha(s)")
if lista.winfo_class() != "Treeview":
    falhas.append(f"a lista e {lista.winfo_class()}: sem coluna nao ha caixa "
                  f"de marcar clicavel")
elif not lista.get_children():
    print("  (lista vazia; nao ha o que clicar)")
else:
    gravou = []
    real_save = main.save_monsters
    main.save_monsters = lambda m, caminho=None, loot=None: \
        gravou.append(dict(loot or {}))
    alvo = lista.get_children()[0]

    def clica_em(coluna):
        caixa = lista.bbox(alvo, coluna)
        if not caixa:
            return None
        ev = type("E", (), {"x": caixa[0] + caixa[2] // 2,
                            "y": caixa[1] + caixa[3] // 2})()
        painel._clique_na_lista(ev)
        _raiz.update_idletasks()
        return lista.item(alvo, "values")[0]

    antes = lista.item(alvo, "values")[0]
    depois = clica_em("saque")
    print(f"  clique na coluna $: {antes!r} -> {depois!r}")
    if depois == antes:
        falhas.append("clicar na coluna do saque nao alternou a marca")
    if not gravou:
        falhas.append("alternou a marca e nao gravou: a escolha se perderia "
                      "ao fechar o painel")
    elif alvo not in gravou[-1]:
        falhas.append(f"gravou sem a flag de {alvo!r}: {gravou[-1]}")

    antes2 = lista.item(alvo, "values")[0]
    depois2 = clica_em("nome")
    print(f"  clique na coluna do nome: {antes2!r} -> {depois2!r} "
          f"(nao devia mudar)")
    if depois2 != antes2:
        falhas.append("clicar no NOME alternou a marca: so a coluna da caixa "
                      "alterna, senao escolher um monstro para renomear "
                      "mudaria o saque dele sem querer")

    # o iid da linha E o nome, e e por ele que as acoes acham o monstro
    lista.selection_set(alvo)
    if painel._nome_selecionado() != alvo:
        falhas.append(f"_nome_selecionado devolveu "
                      f"{painel._nome_selecionado()!r}, esperava {alvo!r}")
    main.save_monsters = real_save

_raiz.destroy()
print("\nVEREDITO:", "OK - o painel cabe na tela e tudo dentro dele e alcancavel"
      if not falhas else "FALHOU: " + "; ".join(falhas))
