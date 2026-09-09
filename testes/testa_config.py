# -*- coding: utf-8 -*-
"""O config.json vale para o main.py, e nao so para a GUI.

So a GUI lia esse arquivo. Rodando pela linha de comando - inclusive os modos
de diagnostico - o bot usava os valores PADRAO do codigo: `--loot` conferia a
tecla '-' mesmo com outra configurada, e `--teclas` media as diagonais padrao.
Diagnostico que mede outra configuracao que nao a sua responde a pergunta
errada, e com toda a confianca.
"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import main

falhas = []
guardado = {k: getattr(main, k) for k in
            ("LOOT_BOTAO", "LOOT_DIST", "KITE_DIST", "ENABLE_LOOT",
             "ATTACK_MODE", "KITE_DIAGONAIS_TECLAS")}


def com_config(cfg):
    """Escreve um config temporario, carrega e devolve quantas chaves entraram."""
    caminho = os.path.join(tempfile.gettempdir(), "cfg_teste.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    return main.carrega_config(caminho)


# ------------------------------------- 1) os tipos certos, e nao texto cru
entraram = com_config({"LOOT_BOTAO": "direito", "LOOT_DIST": "2",
                       "KITE_DIST": "5.0", "ENABLE_LOOT": 0,
                       "ATTACK_MODE": "kite"})
print(f"{entraram} chave(s) aplicadas")
print(f"  LOOT_BOTAO = {main.LOOT_BOTAO!r}")
print(f"  LOOT_DIST   = {main.LOOT_DIST!r}  (veio como texto '2')")
print(f"  KITE_DIST   = {main.KITE_DIST!r}  (veio como texto '5.0')")
if main.KITE_DIST != 5:
    falhas.append(f"KITE_DIST virou {main.KITE_DIST!r}: '5.0' e cinco, e a GUI "
                  f"pode gravar assim")
print(f"  ENABLE_LOOT = {main.ENABLE_LOOT!r} (veio como 0)")
if main.LOOT_BOTAO != "direito":
    falhas.append("nao aplicou LOOT_BOTAO")
if main.LOOT_DIST != 2 or not isinstance(main.LOOT_DIST, int):
    falhas.append(f"LOOT_DIST virou {main.LOOT_DIST!r}: numero escrito como "
                  f"texto tem de virar numero, senao a comparacao de distancia "
                  f"estoura")
if main.ENABLE_LOOT is not False:
    falhas.append(f"ENABLE_LOOT virou {main.ENABLE_LOOT!r}, esperava False")

# --------------------------- 2) chave estranha nao vira atributo novo
com_config({"COISA_QUE_NAO_EXISTE": 1, "loot_hotkey": "x"})
print(f"\nchave desconhecida virou atributo? "
      f"{hasattr(main, 'COISA_QUE_NAO_EXISTE')}")
print(f"chave minuscula foi aplicada? {main.LOOT_BOTAO == 'x'}")
if hasattr(main, "COISA_QUE_NAO_EXISTE"):
    falhas.append("chave estranha do arquivo virou constante do modulo")
if main.LOOT_BOTAO == "x":
    falhas.append("chave minuscula foi aplicada: so MAIUSCULA e constante")

# --------------------------- 3) valor impossivel nao derruba o arranque
antes = main.LOOT_DIST
entraram = com_config({"LOOT_DIST": "duas casas", "LOOT_BOTAO": "esquerdo"})
print(f"\ncom LOOT_DIST='duas casas': LOOT_DIST segue {main.LOOT_DIST!r}, "
      f"e LOOT_BOTAO ainda foi aplicada? {main.LOOT_BOTAO == "esquerdo"}")
if main.LOOT_DIST != antes:
    falhas.append("valor impossivel corrompeu a constante")
if main.LOOT_BOTAO != "esquerdo":
    falhas.append("uma chave ruim impediu as outras de entrar")

# --------------------------- 4) arquivo que nao existe: segue com os padroes
n = main.carrega_config(os.path.join(tempfile.gettempdir(), "nao_existe_1234.json"))
print(f"arquivo inexistente: {n} chave(s), sem estourar")
if n != 0:
    falhas.append("arquivo inexistente devolveu algo")

# ------------- 4b) null num campo de texto e VAZIO, e nao a palavra "None"
# A GUI gravava campo de texto vazio como None; o json escreve null; o
# carregador fazia str(None) = "None" e isso virava o valor. Foi assim que
# LOOT_MOD virou a string "None" e o clique passou a segurar uma tecla chamada
# "None" - que nao existe, entao o pyautogui nao apertava nada e ninguem
# reclamava.
com_config({"LOOT_MOD": None, "LOOT_BOTAO": None})
print(f"\ntexto vindo como null: LOOT_MOD = {main.LOOT_MOD!r}, "
      f"LOOT_BOTAO = {main.LOOT_BOTAO!r}")
if main.LOOT_MOD != "" or main.LOOT_BOTAO != "":
    falhas.append(f"null num campo de texto virou {main.LOOT_MOD!r}: tem de "
                  f"virar vazio, e nao a palavra 'None'")

# ------------- 4c) tecla que nao existe e descartada, com aviso
# Achado em config de verdade: as diagonais tinham o TEXTO DA DICA da interface
# como valor. O pyautogui nao estoura com nome que nao conhece - ele so nao
# aperta nada, e o personagem fica parado sem erro em lugar nenhum.
import pyautogui as _pg
com_config({"KITE_DIAGONAIS": True,
            "KITE_DIAGONAIS_TECLAS": "cima-esq,cima-dir,baixo-esq,baixo-dir"})
ruins = [t for t in main.KITE_PASSOS if t not in _pg.KEYBOARD_KEYS]
print(f"com o texto da dica como valor: {len(main.KITE_PASSOS)} tecla(s) de "
      f"andar, invalidas: {ruins or 'nenhuma'}")
if ruins:
    falhas.append(f"teclas inexistentes entraram em KITE_PASSOS: {ruins}. O "
                  f"bot decide andar, manda a tecla e o personagem fica "
                  f"parado sem nenhum erro")
if len(main.KITE_PASSOS) != 4:
    falhas.append(f"sobraram {len(main.KITE_PASSOS)} teclas; com todas as "
                  f"diagonais invalidas tem de sobrar so as 4 setas")

# --------------------------- 5) as teclas de andar sao refeitas
com_config({"KITE_DIAGONAIS": True, "KITE_DIAGONAIS_TECLAS": "q,e,z,c"})
print(f"\nteclas de andar depois da config: {sorted(main.KITE_PASSOS)}")
for t in ("q", "e", "z", "c"):
    if t not in main.KITE_PASSOS:
        falhas.append(f"a tecla {t!r} da config nao entrou em KITE_PASSOS: "
                      f"decidir por uma tecla e consultar a tabela velha e "
                      f"KeyError no meio da cacada")
        break

for k, v in guardado.items():          # devolve o modulo como estava
    setattr(main, k, v)
main.atualiza_passos()

print("\nVEREDITO:", "OK - a sua configuracao vale tambem fora da GUI"
      if not falhas else "FALHOU: " + "; ".join(falhas))
