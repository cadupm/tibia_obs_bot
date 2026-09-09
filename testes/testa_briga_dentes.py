# -*- coding: utf-8 -*-
"""Os testes de rota ainda REPROVAM um bot quebrado?

O testa_briga vinha reprovando o bot certo: o mundo dele arrastava o personagem
meia bandeira por briga, mais depressa do que ele conseguia andar, e a
aprovacao era de 3 em 12 sementes com os cliques todos perfeitos. O empurrao
virou fisico e a aprovacao foi para 20 em 20.

Isso levanta a pergunta obvia, e este teste existe para responde-la: afrouxar o
mundo nao deixou o teste passar em qualquer coisa? Aqui a regra de ouro e
DELIBERADAMENTE quebrada - o bot passa a mirar sempre a bandeira visivel mais
proxima, sem olhar o que ja visitou, que e exatamente o vaivem de que o caso
reclamava. Se o cenario aprovar isso, ele nao mede nada e nao serve.

Um teste que nunca reprova e um teste que nao existe.
"""
import io, math, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))          # acha o main.py
AQUI = os.path.dirname(os.path.abspath(__file__)) + "/"

# O bot quebrado: mira sempre a bandeira mais proxima que nao seja a de baixo do
# pe. Sem memoria de visita, sem "nunca a ultima" - o vaivem em pessoa.
REMENDO = '''
import main as _m


def _mais_proxima(leitura, odo, estado, click_cd):
    marcas = _m.track_marks(leitura, estado, odo=odo)
    if not marcas:
        return False
    fora = [x for x in marcas if abs(x[0]) + abs(x[1]) > _m.MARK_ARRIVE]
    if not fora:
        return False
    alvo = min(fora, key=lambda x: abs(x[0]) + abs(x[1]))
    estado["alvo_off"] = alvo
    if odo.parado < _m.WALK_STOP_TICKS or not click_cd.ready():
        return True
    passo = _m.limita_passo(alvo, _m.MARK_REACH)
    if abs(passo[0]) + abs(passo[1]):
        _m.click_minimap(leitura, passo)
        click_cd.mark()
    return True


_m.follow_marks = _mais_proxima
'''

falhas = []
for cenario in ("testa_briga.py", "testa_briga_leve.py"):
    fonte = io.open(AQUI + cenario, encoding="utf-8").read()
    # entra depois do "import main", para poder trocar a funcao
    fonte = fonte.replace("import main\n", "import main\n" + REMENDO, 1)
    quebrado = os.path.join(tempfile.gettempdir(), "quebrado_" + cenario)
    io.open(quebrado, "w", encoding="utf-8").write(fonte)

    reprovou = 0
    for semente in range(8):
        env = dict(os.environ, SEMENTE=str(semente),
                   PYTHONPATH=os.path.dirname(AQUI.rstrip("/")))
        saida = subprocess.run([sys.executable, quebrado], capture_output=True,
                               text=True, env=env).stdout
        if "VEREDITO: OK" not in saida:
            reprovou += 1
        elif semente == 0:
            print("   passou com o bot quebrado; visitas foram:")
            print("   " + next((l for l in saida.splitlines()
                                if l.startswith("visitas")), "?")[:100])
    os.remove(quebrado)
    print(f"{cenario} com a regra de ouro quebrada: reprovou em "
          f"{reprovou}/8 sementes")
    if reprovou < 7:
        falhas.append(f"{cenario} aprovou o bot quebrado em {8 - reprovou} de 8 "
                      f"sementes: o cenario nao distingue rota boa de vaivem")

print("\nVEREDITO:", "OK - os cenarios de rota reprovam um bot quebrado"
      if not falhas else "FALHOU: " + "; ".join(falhas))
