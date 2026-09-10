# -*- coding: utf-8 -*-
"""restore_windows() devolve a janela EXATAMENTE como estava, nao so o alpha.

Bug real, medido ao vivo no Tibia do usuario: a janela do jogo nunca tinha
WS_EX_LAYERED ligado (GWL_EXSTYLE sem o bit), e get_alpha() devolve 255 tanto
para "nao e layered" quanto para "e layered e vale 255" - as duas coisas
parecem a mesma "opacidade 255", mas sao ESTILOS DIFERENTES de janela.

O bot precisa deixar o Tibia quase invisivel em modo OBS (para o projetor
aparecer atraves dele), e isso e feito com set_alpha(), que LIGA WS_EX_LAYERED
e nunca desliga. Restaurar so o "alpha=255" no fim deixava a janela com um
estilo que ela nunca tinha antes: permanentemente layered, so que em 255 - o
que e visualmente identico mas estruturalmente diferente, e e exatamente o
tipo de coisa que pode atrapalhar o hook do OBS Game Capture (ja fragil por
causa do BattlEye, que e a razao do projeto inteiro depender do OBS).

eh_layered() busca do LOCAL CORRETO (GWL_EXSTYLE, via GetWindowLongW) se a
janela era layered ANTES de o bot mexer - e nao infere isso do alpha. Com essa
informacao, restore_windows() desliga o estilo por completo quando ele nao
existia, em vez de so devolver o numero.

Aqui se cria uma janela Win32 de verdade (invisivel, sem precisar do Tibia) e
se roda o ciclo inteiro: capturar o estado, forcar baixa opacidade (o que o
bot faz para o truque do OBS funcionar), e restaurar - exigindo que o
GWL_EXSTYLE final seja BYTE A BYTE igual ao inicial.
"""
import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
import main

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
WS_EX_LAYERED = 0x00080000
GWL_EXSTYLE = -20


class JanelaDeVerdade:
    """O suficiente do pygetwindow.Win32Window para as funcoes de janela."""

    def __init__(self, hwnd):
        self._hWnd = hwnd
        self.title = "janela de teste (invisivel)"


falhas = []


def cria_janela(estilo_inicial=0):
    hwnd = u32.CreateWindowExW(estilo_inicial, "Static", "teste_layered",
                               0x80000000,     # WS_POPUP: nao precisa de pai
                               0, 0, 50, 50, None, None,
                               k32.GetModuleHandleW(None), None)
    if not hwnd:
        raise OSError("nao consegui criar a janela de teste")
    return JanelaDeVerdade(hwnd)


def exstyle(win):
    return u32.GetWindowLongW(win._hWnd, GWL_EXSTYLE)


# --------------------------------------------------- 1) o caso do usuario
# uma janela comum, NUNCA layered - como o Tibia estava.
win = cria_janela()
antes = exstyle(win)
print(f"janela criada: EXSTYLE={antes:#x}  layered? {main.eh_layered(win)}  "
      f"alpha={main.get_alpha(win)}")
if main.eh_layered(win):
    falhas.append("a janela recem-criada ja apareceu como layered: o teste "
                  "nao criou o cenario certo")
if main.get_alpha(win) != 255:
    falhas.append(f"alpha inicial {main.get_alpha(win)}, esperava 255")

# o que setup_windows() faz quando acha a janela opaca em modo OBS
main._ALPHA_ORIGINAL.append((win, main.get_alpha(win), main.eh_layered(win)))
main.set_alpha(win, main.OBS_ALPHA_TIBIA)
durante = exstyle(win)
print(f"depois de set_alpha({main.OBS_ALPHA_TIBIA}): EXSTYLE={durante:#x}  "
      f"layered? {main.eh_layered(win)}  alpha={main.get_alpha(win)}")
if not main.eh_layered(win):
    falhas.append("set_alpha nao ligou o estilo layered")
if main.get_alpha(win) != main.OBS_ALPHA_TIBIA:
    falhas.append(f"alpha durante {main.get_alpha(win)}, esperava "
                  f"{main.OBS_ALPHA_TIBIA}")

# restore_windows() consome a pilha e devolve a janela
main.restore_windows()
depois = exstyle(win)
print(f"depois de restore_windows(): EXSTYLE={depois:#x}  "
      f"layered? {main.eh_layered(win)}  alpha={main.get_alpha(win)}")

if depois != antes:
    falhas.append(
        f"EXSTYLE nao voltou ao original: era {antes:#x}, ficou {depois:#x}. "
        f"So restaurar o alpha (sem tirar WS_EX_LAYERED) deixa a janela "
        f"permanentemente layered mesmo quando ela nunca foi - o bug medido "
        f"no Tibia do usuario")
if main.eh_layered(win):
    falhas.append("a janela continua layered depois do restore")
if main.get_alpha(win) != 255:
    falhas.append(f"alpha final {main.get_alpha(win)}, esperava 255")

u32.DestroyWindow(win._hWnd)

# --------------------------------------- 2) uma janela QUE JA ERA layered
# (o outro ramo: modo direto, quando alpha < 250 chega ja layered). Restaurar
# tem de devolver o ALPHA ORIGINAL, e continuar layered - nao tirar o estilo
# de quem sempre teve.
win2 = cria_janela(estilo_inicial=WS_EX_LAYERED)
main.set_alpha(win2, 120)          # alpha "original" do usuario, ja layered
original_layered = main.eh_layered(win2)
original_alpha = main.get_alpha(win2)
print(f"\njanela ja layered: alpha original={original_alpha}  "
      f"layered? {original_layered}")

main._ALPHA_ORIGINAL.append((win2, original_alpha, original_layered))
main.set_alpha(win2, 255)          # o bot forca visivel (modo direto)
main.restore_windows()
print(f"depois do restore: alpha={main.get_alpha(win2)}  "
      f"layered? {main.eh_layered(win2)}")

if main.get_alpha(win2) != original_alpha:
    falhas.append(f"janela que ja era layered voltou com alpha "
                  f"{main.get_alpha(win2)}, esperava o original "
                  f"{original_alpha}")
if not main.eh_layered(win2):
    falhas.append("janela que sempre foi layered perdeu o estilo no restore - "
                  "so devia perder quem nunca teve")

u32.DestroyWindow(win2._hWnd)

print("\nVEREDITO:", "OK - restaura o estilo exato, nao so o numero do alpha"
      if not falhas else "FALHOU: " + "; ".join(falhas))
