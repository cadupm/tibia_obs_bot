"""Roda o bot e correlaciona o que ele fez com o estado da Battle List."""
import sys, threading, time
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

DURACAO = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0

acoes = []
_press = main.pyautogui.press


def press_espiao(tecla, *a, **k):
    acoes.append((time.time(), tecla))
    return _press(tecla, *a, **k)


main.pyautogui.press = press_espiao          # registra cada tecla enviada

t = threading.Thread(target=main.run_bot, daemon=True)
t.start()
time.sleep(6)

leitura = main.find_projector() if main.OBS_MODE else main.find_tibia()
t0 = time.time()
linhas = []
while time.time() - t0 < DURACAO:
    try:
        n, alvo, alvo_hp = main.battle_state(leitura)
        hp, mana = main.read_bars(leitura)
        linhas.append((round(time.time() - t0, 1), n, alvo, alvo_hp, hp, mana))
    except Exception:
        linhas.append((round(time.time() - t0, 1), None, None, None, None, None))
    time.sleep(0.5)

main.STOP = True
t.join(timeout=6)

print("\ntempo | entr | alvo  | hp_alvo | hp   | mana | teclas")
for ts, n, alvo, alvo_hp, hp, mana in linhas:
    if n is None:
        print(f"{ts:5.1f}s | ERRO")
        continue
    janela = [k for (quando, k) in acoes if 0 <= (quando - t0) - ts < 0.5]
    print(f"{ts:5.1f}s | {n:4d} | {str(alvo):5s} | "
          f"{'   -   ' if alvo_hp is None else format(alvo_hp, '6.0%') + ' '} | "
          f"{hp:4.0%} | {mana:4.0%} | {' '.join(janela) if janela else '-'}")

validas = [(ts, n, a) for ts, n, a, _, _, _ in linhas if n is not None]
ataques = [q - t0 for q, k in acoes if k == main.ATTACK_HOTKEY]
magias = [q - t0 for q, k in acoes if k == main.SPELL_HOTKEY]
print(f"\namostras validas: {len(validas)}/{len(linhas)}")
print(f"ataques ({main.ATTACK_HOTKEY}): {len(ataques)} | "
      f"magias ({main.SPELL_HOTKEY}): {len(magias)}")

# 1) atacou sempre que tinha bicho sem alvo?
faltou = [ts for ts, n, a in validas if n > 0 and not a
          and not any(-0.2 <= q - ts <= 2.0 for q in ataques)]
print(f"momentos com bicho e sem alvo: {len([1 for _, n, a in validas if n > 0 and not a])}"
      f" | sem ataque em 2s: {len(faltou)}")

# 2) conjurou enquanto o alvo estava engajado?
engajado = [ts for ts, n, a in validas if a]
sem_magia = [ts for ts in engajado
             if not any(-0.2 <= q - ts <= 1.5 for q in magias)]
print(f"momentos com alvo engajado: {len(engajado)} | sem magia em 1.5s: {len(sem_magia)}")
if len(magias) > 1:
    intervalos = [round(b - a, 2) for a, b in zip(magias, magias[1:])]
    print(f"intervalos entre magias: {intervalos[:12]} "
          f"(cooldown configurado {main.SPELL_COOLDOWN}s)")

# 3) trocou de alvo com bicho vivo? (space apertado logo apos ler alvo=True)
trocas = [ts for ts, n, a in validas if a
          and any(0 <= q - ts <= 0.6 for q in ataques)]
print(f"apertou ataque com alvo vivo: {len(trocas)} vez(es) {trocas[:6]}")

print("VEREDITO ataque:", "ok" if not faltou else "deixou bicho sem atacar")
print("VEREDITO nao-troca:", "ok" if not trocas else "trocou de alvo com bicho vivo")
print("VEREDITO magia:", "ok" if engajado and not sem_magia
      else ("sem alvo engajado no periodo" if not engajado else "faltou magia no alvo"))
main.restore_windows()
