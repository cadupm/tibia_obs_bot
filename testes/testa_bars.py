import numpy as np, sys
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"
import main

def usar(arr):
    h, w = arr.shape[:2]
    main.client_rect = lambda win: (0, 0, w, h)
    main.grab = lambda reg: arr[reg[1]:reg[1]+reg[3], reg[0]:reg[0]+reg[2]]

def sintetica(cw, hp_t, mana_t, hpf, manaf, cor_hp=(0,190,0)):
    img = np.full((90, cw, 3), 70, np.uint8)
    for (x0, x1), frac, cor in [(hp_t, hpf, cor_hp), (mana_t, manaf, (0,57,126))]:
        img[5:17, x0:x1+1] = 38
        img[5:17, x0:x0+int(round((x1-x0+1)*frac))] = cor
        meio = (x0+x1)//2
        img[8:14, meio-20:meio+20] = 240
    img[60:, :] = np.random.randint(0, 255, (30, cw, 3))
    return img

ok = total = 0
def check(nome, det, esp, esperado_frac=None):
    global ok, total
    total += 1
    bom = det == esp
    ok += bom
    print(f"{'OK   ' if bom else 'FALHA'} {nome}")
    print(f"        detectado {det}")
    if not bom:
        print(f"        esperado  {esp}")
    if det and esperado_frac:
        leit = (main.fill_ratio(main.grab(det[0])), main.fill_ratio(main.grab(det[1])))
        print(f"        leitura   hp={leit[0]:.1%} (esp {esperado_frac[0]:.0%})  "
              f"mana={leit[1]:.1%} (esp {esperado_frac[1]:.0%})")

# O caso REAL depende de uma captura da sua tela, que nao vai para o
# repositorio. Sem ela o teste estourava inteiro e levava junto os casos
# sinteticos, que nao dependem de nada. Agora so este caso e pulado.
_REAL = AQUI + "obs3.png"
if os.path.exists(_REAL):
    sys.path.insert(0, AQUI)
    import png as _png
    usar(_png.le(_REAL)[23:])
    check("REAL 1920x1009 (155/155 e 60/60)", main.detect_bars(None),
          ((12,5,769,12), (788,5,768,12)), (1.0, 1.0))
else:
    print(f"PULADO o caso real: falta {_REAL}")
    print("  (captura da sua tela; os casos sinteticos abaixo rodam do mesmo jeito)")

casos = [(1280,(8,470),(478,940),0.55,0.60,(0,190,0)),
         (2560,(16,1040),(1048,2072),0.85,0.35,(0,190,0)),
         (1366,(10,500),(508,998),0.20,0.90,(0,190,0)),
         (1024,(6,380),(388,762),1.00,1.00,(0,190,0)),
         (1600,(10,620),(628,1238),0.30,0.45,(200,30,30)),   # hp vermelho (vida baixa)
         (1920,(12,780),(788,1556),0.08,0.50,(200,150,0))]   # hp 8% (limite)
for cw, hp_t, mana_t, hpf, manaf, cor in casos:
    usar(sintetica(cw, hp_t, mana_t, hpf, manaf, cor))
    check(f"SINTETICA {cw} hp={hpf:.0%} {'(vermelho)' if cor==(200,30,30) else '(amarelo)' if cor==(200,150,0) else ''} mana={manaf:.0%}",
          main.detect_bars(None),
          ((hp_t[0],5,hp_t[1]-hp_t[0]+1,12), (mana_t[0],5,mana_t[1]-mana_t[0]+1,12)),
          (hpf, manaf))

# --- casos que DEVEM ser rejeitados ---
np.random.seed(7)
login = np.random.randint(60, 255, (90, 1920, 3)).astype(np.uint8)   # arte saturada
usar(login)
total += 1
det = main.detect_bars(None)
if det is None:
    ok += 1
    print("OK    TELA DE LOGIN (faixa grossa saturada) -> None, como deve")
else:
    print(f"FALHA TELA DE LOGIN aceitou {det}")

cheio = np.full((90, 1920, 3), (0, 190, 0), np.uint8)
usar(cheio)
total += 1
det = main.detect_bars(None)
if det is None:
    ok += 1
    print("OK    TELA TODA VERDE -> None, como deve")
else:
    print(f"FALHA TELA TODA VERDE aceitou {det}")

print(f"\n{ok}/{total} casos exatos")

print("VEREDITO:", "OK - acha as barras em todas as larguras testadas"
      if ok == total else f"FALHOU: {total - ok} caso(s) errados")
