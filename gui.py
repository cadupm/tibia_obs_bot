"""
gui.py - Painel de controle do bot.

Organizacao:
  - cabecalho fixo com status e os botoes Iniciar/Parar: o que voce mais usa nao
    fica escondido dentro de aba;
  - abas por atividade: Healing, Combate, Rota, Loot, Autocast, Setup;
  - cada bloco tem um interruptor proprio; desligado, os campos ficam
    acinzentados, para o painel mostrar o que esta valendo;
  - log embaixo, sempre visivel, espelhando a saida do bot.

A rota tem dois modos, na aba Rota:
  - ORDEM GRAVADA: voce clica nas marcas do mapa na sequencia que quer e o bot
    segue essa ordem, recomecando no fim. Da conta de percurso que nao e
    circulo. A lista mostra o desenho de cada marca para reordenar na mao;
  - sem rota gravada, vale a REGRA DE OURO: ele vai para a marca mais proxima
    que ainda nao visitou.
A visita so conta quando a cruz do personagem passa por baixo da marca,
conferido por pixel.

Detalhe importante: o jogo fica "sempre visivel" (topmost) enquanto o bot roda e
o bot so envia teclas com o jogo em FOCO. Clicar neste painel tira o foco do
jogo e o bot pausa sozinho - e proposital, serve de freio de mao. O painel
tambem e topmost, entao deixe-o num canto que nao cubra o minimapa nem a battle
list, senao a leitura pega o painel em vez do jogo.
"""

import json
import os
import queue
import sys
import threading
import traceback
import tkinter as tk
from tkinter import simpledialog
from tkinter import ttk

import main

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
PONTOS = "pontos (<=1 = fracao da barra)"

# aba -> blocos; bloco = (titulo, interruptor, campos)
# campo = (atributo no main, rotulo, tipo, dica)
ABAS = [
    ("Healing", [
        ("Personagem", None, [
            ("HP_MAX", "Vida maxima", int, "atualize ao subir de level"),
            ("MANA_MAX", "Mana maxima", int, ""),
        ]),
        ("Cura", "ENABLE_HEAL", [
            ("HEAL_HOTKEY", "Hotkey da cura", str, "magia ou pocao"),
            ("HEAL_THRESHOLD", "Curar com vida <=", float, PONTOS),
            ("HEAL_COOLDOWN", "Cooldown", float, "segundos"),
            ("HEAL_STRONG_HOTKEY", "Hotkey de emergencia", str, "vazio = desligado"),
            ("HEAL_STRONG_THRESHOLD", "Emergencia com vida <=", float, PONTOS),
        ]),
        ("Pocao de mana", "ENABLE_MANA", [
            ("MANA_HOTKEY", "Hotkey da pocao", str, ""),
            ("MANA_THRESHOLD", "Beber com mana <=", float, PONTOS),
            ("MANA_COOLDOWN", "Cooldown", float, "segundos"),
        ]),
    ]),
    ("Combate", [
        ("Ataque", "ENABLE_ATTACK", [
            ("ATTACK_MODE", "Como lutar", str, "stand, chase ou kite"),
            ("ATTACK_HOTKEY", "Tecla de atacar", str, "atacar proxima criatura"),
            ("ATTACK_COOLDOWN", "Cooldown", float, "segundos"),
            ("ATTACK_CONFIRM", "Leituras sem alvo p/ trocar", int,
             "evita trocar de bicho por leitura ruim"),
            ("TARGET_LOST_MAX", "Segurar o alvo por", float,
             "segundos; so troca quando ele sumir da battle list"),
            ("TARGET_GONE_READS", "Leituras sem o bicho p/ dar por morto", int,
             "uma leitura ruim nao conta como morte"),
        ]),
        ("Kite (so no modo kite)", None, [
            ("KITE_DIST", "Manter distancia de", int,
             "SQM de todo bicho na tela, inclusive o alvo"),
            ("KITE_COOLDOWN", "Intervalo entre passos", float,
             "segundos; a velocidade de andar do personagem"),
            ("KITE_CLIQUE", "Clicar no mapa a partir de", int,
             "SQM alem da distancia: seta e lenta para longe"),
            ("KITE_BLOQUEIO", "Evitar lado que nao andou por", float,
             "segundos; e assim que ele desencalha de parede"),
            ("KITE_DIAGONAIS", "Usar diagonais", bool,
             "confira com --teclas antes de ligar"),
            ("KITE_DIAGONAIS_TECLAS", "Teclas das diagonais", str,
             "cima-esq, cima-dir, baixo-esq, baixo-dir"),
            ("PARAR_SE_MUDAR_ANDAR", "Parar se mudar de andar", bool,
             "caiu em escada ou buraco: para tudo"),
        ]),
        ("Combo de magia", "ENABLE_SPELL", [
            ("SPELL_HOTKEY", "Magia do combo", str, "entra entre os turnos"),
            ("SPELL_COOLDOWN", "Cooldown da magia", float, "segundos"),
            ("SPELL_MANA_FLOOR", "Nao conjurar abaixo de", float, PONTOS),
            ("SPELL_DELAY_AFTER_ATTACK", "Esperar depois do ataque", float,
             "segundos, para nao comer o turno"),
        ]),
    ]),
    ("Rota", [
        ("Andar pelas marcas do mapa", "ENABLE_WALK", [
            ("MARK_COLOR", "Cor da marca", str, "azul, verde ou vermelho"),
            ("MARK_ARRIVE", "Visita quando a marca estiver a", int,
             "px da cruz (cruz sob a marca)"),
            ("STOP_WALK_KEY", "Tecla para parar de andar", str,
             "cancela o trajeto ao ver bicho; vazio = nao cancela"),
            ("STOP_ATTACK_DELAY", "Esperar antes de atacar", float,
             "segundos; a parada tem de ser processada primeiro"),
            ("WALK_RESUME_READS", "Leituras limpas p/ voltar a andar", int,
             "clique no mapa durante o ataque troca chase/stand"),
            ("WALK_CLICK_COOLDOWN", "Intervalo entre cliques", float, "segundos"),
            ("WALK_MAX_CLICKS", "Cliques sem progresso", int,
             "antes de trocar de marca"),
            ("MINIMAP_PX_SQM", "Escala do minimapa", float,
             "px por SQM; meca com --zoom"),
        ]),
    ]),
    ("Loot", [
        # Aba propria: o saque nao e parte de como lutar. Ele acontece DEPOIS
        # da briga, com a battle list limpa, e e igual em stand, chase e kite -
        # o modo de luta muda de onde se parte, nao o que se faz com o corpo.
        ("Ir no corpo e clicar nele", "ENABLE_LOOT", [
            ("LOOT_CLICA", "Clicar no corpo", bool,
             "no cliente, o botao direito no corpo saqueia"),
            ("LOOT_BOTAO", "Botao do clique", str,
             "direito ou esquerdo"),
            ("LOOT_MOD", "Segurar junto", str,
             "shift, ctrl, alt ou vazio"),
            ("LOOT_CLIQUES", "Cliques por corpo", int,
             "1 basta: clicou nele, esta saqueado"),
            ("LOOT_FECHA_MENU", "Fechar menu depois do clique", bool,
             "menu de contexto aberto engole clique e tecla"),
            ("LOOT_TECLA", "Tecla de saque, no corpo", str,
             "uma apertada no mesmo ponto; vazio = so o clique"),
            ("LOOT_TECLA_NUMPAD", "Mandar tambem o numpad", bool,
             "o - de cima e o - do numpad sao teclas diferentes"),
            ("LOOT_DIST", "Chegar a", int,
             "SQM do corpo antes de clicar"),
            ("LOOT_MAX_CORPOS", "Corpos na fila", int,
             "numa caverna se mata em grupo"),
            ("LOOT_PRAZO", "Desistir de um corpo depois de", float,
             "segundos tentando chegar nele"),
            ("LOOT_VALIDADE", "Largar corpo mais velho que", float,
             "segundos: o de tras na rota nao vale a viagem"),
        ]),
        ("Achar o corpo na tela", "LOOT_ACHA_CORPO", [
            ("LOOT_SO_SE_ACHOU", "Largar se nao achar", bool,
             "desligado: clica no palpite, que e melhor que nao agir"),
            ("LOOT_DIFF_MIN", "Mudanca minima do quadrado", float,
             "por pixel; o log de cada morte diz o valor real"),
            ("LOOT_DIFF_MARGEM", "Vantagem sobre o segundo", float,
             "vezes; sem isso animacao de chao ganharia por pouco"),
            ("LOOT_BUSCA_RAIO", "Procurar num raio de", int,
             "SQM em volta do palpite (1 = os 9 quadrados)"),
        ]),
    ]),
    ("Autocast", [
        ("Autocast", "ENABLE_AUTOCAST", [
            ("AUTOCAST_MANA_FLOOR", "Nao conjurar abaixo de", float, PONTOS),
        ]),
        # Aqui e nao no Combate: e magia que o bot conjura sozinho, como o
        # resto desta aba. O gatilho e que difere - as de baixo saem por tempo,
        # esta sai quando TODO lado parece parede, que e o que a paralisia faz
        # o personagem sentir.
        ("Curar paralisia", "ENABLE_PARALISIA", [
            ("PARALISIA_HOTKEY", "Magia que cura", str,
             "exura ou utani hur: as duas tiram paralisia"),
            ("PARALISIA_LADOS", "Lados travados p/ suspeitar", int,
             "pedra e de um lado; paralisia e de todos"),
            ("PARALISIA_FALHAS", "Passos seguidos sem sair do lugar", int,
             "o sinal rapido, em vez de esperar cada lado"),
            ("PARALISIA_COOLDOWN", "Intervalo entre tentativas", float,
             "segundos"),
        ]),
    ]),
    ("Setup", [
        ("Leitura da tela", "OBS_MODE", [
            ("OBS_TITLE", "Titulo do projetor", str, "a janela do jogo sai preta"),
        ]),
        ("Geral", None, [
            ("KILL_KEY", "Tecla de parada", str, "funciona mesmo sem foco"),
            ("LOOP_DELAY", "Intervalo do loop", float, "segundos"),
        ]),
    ]),
]


class FilaDeSaida:
    """
    Captura o print do bot para o log do painel.

    SEM CONSOLE, `original` e None. Aberto por atalho ou com pythonw - que e o
    jeito natural de rodar um painel, sem janela preta atras - o Python deixa
    sys.stdout e sys.stderr em None, e o `original.write` estourava
    AttributeError no PRIMEIRO print do bot: a cacada morria no arranque com
    "'NoneType' object has no attribute 'write'". Console ausente nao e erro, e
    so nao ter para onde ecoar - o log do painel continua recebendo tudo.
    """

    def __init__(self, fila, original):
        self.fila = fila
        self.original = original

    def write(self, texto):
        if self.original is not None:
            self.original.write(texto)
        limpo = texto.replace("\r", "").strip()
        if limpo:
            self.fila.put(limpo)
        return len(texto)

    def flush(self):
        if self.original is not None:
            self.original.flush()

    # o traceback.print_exc() do laco do bot pergunta isto antes de escrever
    def isatty(self):
        return False

    def writable(self):
        return True


MARK_ICON_ZOOM = 3              # o desenho da marca tem 13px; 3x fica legivel
ALTURA_BARRAS = 20              # px do topo da tela ocupados pelas barras
MARGEM_TELA = 110               # px reservados para barra de titulo, barra de
                                # tarefas e as folgas do grid. A janela nao pode
                                # passar da tela: a aba Combate cresceu com
                                # Kite, Paralisia e Loot, e a lista "Monstros
                                # para atacar" caia abaixo do corte - sem rolar,
                                # nao havia como chegar nela.
ROLA_PASSO = 3                  # linhas por clique da roda do mouse


class Painel:
    def __init__(self, raiz):
        self.raiz = raiz
        self.fila_log = queue.Queue()
        self.fila_status = queue.Queue()
        self.vars = {}          # attr -> (var, tipo)
        self.widgets = {}       # attr -> [widgets]
        self.blocos = []        # (interruptor, [attrs])
        self.thread_bot = None
        self.parar_status = threading.Event()
        self.monstros = main.load_monsters()

        raiz.title("Cave bot")
        raiz.attributes("-topmost", True)
        raiz.resizable(False, False)
        # Canto de baixo a esquerda, nunca encostado no topo: as barras de vida e
        # mana ocupam a tela INTEIRA em y=5..17, e esta janela e topmost - se ela
        # cobrir essa faixa o bot le vida 0% e para achando que morreu.
        raiz.geometry(f"+0+{ALTURA_BARRAS + 40}")

        self._monta_cabecalho()
        self._monta_abas()
        self._monta_log()

        self.carregar()
        self._atualiza_habilitacao()
        self.raiz.after(200, self._bombeia_log)
        self.raiz.after(500, self._bombeia_status)
        self._inicia_status()
        raiz.protocol("WM_DELETE_WINDOW", self.fechar)

    # ------------------------------------------------------------- cabecalho
    def _monta_cabecalho(self):
        topo = self.cabecalho = ttk.Frame(self.raiz)
        topo.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="ew")
        topo.columnconfigure(0, weight=1)
        topo.columnconfigure(1, weight=0)

        estado = ttk.Frame(topo)
        estado.grid(row=0, column=0, sticky="w")
        self.lbl_vida = ttk.Label(estado, text="vida  -", font=("Segoe UI", 10, "bold"))
        self.lbl_mana = ttk.Label(estado, text="mana  -", font=("Segoe UI", 10, "bold"))
        self.lbl_battle = ttk.Label(estado, text="battle list  -")
        self.lbl_marcas = ttk.Label(estado, text="marcas  -")
        self.lbl_bot = ttk.Label(estado, text="bot parado", foreground="#a33")
        self.lbl_vida.grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.lbl_mana.grid(row=0, column=1, sticky="w", padx=(0, 16))
        self.lbl_battle.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.lbl_marcas.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.lbl_bot.grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 0))

        acoes = ttk.Frame(topo)
        acoes.grid(row=0, column=1, sticky="ne", padx=(30, 0))
        self.btn_iniciar = ttk.Button(acoes, text="Iniciar", width=14,
                                      command=self.iniciar)
        self.btn_parar = ttk.Button(acoes, text="Parar", width=14,
                                    command=self.parar, state="disabled")
        self.btn_iniciar.grid(row=0, column=0, pady=1, sticky="e")
        self.btn_parar.grid(row=1, column=0, pady=1, sticky="e")
        ttk.Button(acoes, text="Salvar config", width=14,
                   command=self.salvar).grid(row=2, column=0, pady=1, sticky="e")

    # ------------------------------------------------------------- abas
    def _monta_abas(self):
        notas = self.notas = ttk.Notebook(self.raiz)
        notas.grid(row=1, column=0, padx=10, pady=4, sticky="ew")
        self.telas = []            # os canvas das abas, para limitar a altura
        for nome, blocos in ABAS:
            aba = self._aba_rolavel(notas, nome)
            linha = 0
            for titulo, interruptor, campos in blocos:
                linha = self._monta_bloco(aba, linha, titulo, interruptor, campos)
            if nome == "Autocast":
                self._monta_autocast(aba, linha)
            if nome == "Combate":
                self._monta_monstros(aba, linha)
            if nome == "Rota":
                self._monta_rota(aba, linha)
        self.raiz.after_idle(self._ajusta_altura)

    def _aba_rolavel(self, notas, nome):
        """
        Uma aba que ROLA. Devolve o frame onde os blocos entram.

        As abas eram frames direto no notebook e a janela crescia com o
        conteudo: a Combate ganhou Kite, Paralisia e Loot e passou da altura da
        tela, deixando "Monstros para atacar" abaixo do corte, sem jeito de
        chegar nele. Agora cada aba e um canvas com barra de rolagem.
        """
        fora = ttk.Frame(notas)
        notas.add(fora, text=nome)
        fora.rowconfigure(0, weight=1)
        fora.columnconfigure(0, weight=1)

        tela = tk.Canvas(fora, highlightthickness=0, borderwidth=0)
        tela.grid(row=0, column=0, sticky="nsew")
        barra = ttk.Scrollbar(fora, orient="vertical", command=tela.yview)
        barra.grid(row=0, column=1, sticky="ns")
        tela.configure(yscrollcommand=barra.set)

        dentro = ttk.Frame(tela)
        janela = tela.create_window((0, 0), window=dentro, anchor="nw")

        def redimensiona(_evento=None):
            tela.configure(scrollregion=tela.bbox("all"))
            # o conteudo acompanha a largura do canvas, senao os blocos com
            # sticky="ew" ficam com a largura minima
            tela.itemconfigure(janela, width=tela.winfo_width())

        dentro.bind("<Configure>", redimensiona)
        tela.bind("<Configure>", redimensiona)
        tela.bind("<Enter>", lambda _e: self._liga_roda(tela))
        tela.bind("<Leave>", lambda _e: self._desliga_roda())
        self.telas.append((tela, dentro, barra))
        return dentro

    # ---------------------------------------------------- roda do mouse
    def _liga_roda(self, tela):
        self._tela_da_roda = tela
        # bind_all porque o ponteiro fica sobre os filhos (labels, entries), e
        # binding no canvas nao pega evento de filho
        self.raiz.bind_all("<MouseWheel>", self._roda)

    def _desliga_roda(self):
        self._tela_da_roda = None
        self.raiz.unbind_all("<MouseWheel>")

    def _roda(self, evento):
        tela = getattr(self, "_tela_da_roda", None)
        if tela is None:
            return
        # quem rola sozinho fica com a roda: a lista de monstros e a arvore da
        # rota tem rolagem propria, e rolar a aba junto embaralhava as duas
        alvo = self.raiz.winfo_containing(evento.x_root, evento.y_root)
        while alvo is not None and alvo is not tela:
            if alvo.winfo_class() in ("Treeview", "Text", "Listbox"):
                return
            alvo = getattr(alvo, "master", None)
        tela.yview_scroll(-ROLA_PASSO if evento.delta > 0 else ROLA_PASSO,
                          "units")

    def _ajusta_altura(self):
        """
        Corta a altura das abas no que cabe na tela.

        Todas ficam com a MESMA altura - a do maior conteudo, limitada pela
        tela - para a janela nao pular de tamanho ao trocar de aba. A barra de
        rolagem so aparece na aba que precisa dela.
        """
        self.raiz.update_idletasks()
        sobra = (self.raiz.winfo_screenheight() - ALTURA_BARRAS - 40
                 - self.cabecalho.winfo_reqheight()
                 - self.log.master.winfo_reqheight() - MARGEM_TELA)
        maior = max(d.winfo_reqheight() for _t, d, _b in self.telas)
        altura = max(min(maior, sobra), 200)
        for tela, dentro, barra in self.telas:
            tela.configure(height=altura)
            if dentro.winfo_reqheight() <= altura:
                barra.grid_remove()       # aba que cabe nao mostra barra
            else:
                barra.grid()
        self.raiz.update_idletasks()

    def _monta_bloco(self, aba, linha, titulo, interruptor, campos):
        quadro = ttk.LabelFrame(aba, text=titulo)
        quadro.grid(row=linha, column=0, sticky="ew", padx=8, pady=4)
        attrs = []

        inicio = 0
        if interruptor:
            var = tk.BooleanVar()
            ttk.Checkbutton(quadro, text="ativado", variable=var,
                            command=self._atualiza_habilitacao).grid(
                row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(2, 4))
            self.vars[interruptor] = (var, bool)
            inicio = 1

        for i, (attr, rotulo, tipo, dica) in enumerate(campos):
            r = inicio + i
            lbl = ttk.Label(quadro, text=rotulo)
            lbl.grid(row=r, column=0, sticky="w", padx=(6, 4), pady=2)
            var = tk.StringVar()
            ent = ttk.Entry(quadro, textvariable=var, width=14)
            ent.grid(row=r, column=1, sticky="w", pady=2)
            widgets = [lbl, ent]
            if dica:
                hint = ttk.Label(quadro, text=dica, foreground="#777")
                hint.grid(row=r, column=2, sticky="w", padx=6)
                widgets.append(hint)
            self.vars[attr] = (var, tipo)
            self.widgets[attr] = widgets
            attrs.append(attr)

        if interruptor:
            self.blocos.append((interruptor, attrs))
        return linha + 1

    def _monta_rota(self, aba, linha):
        """
        A rota: a ORDEM em que as marcas do mapa devem ser seguidas.

        Grava-se clicando em cada marca na sequencia desejada, e a lista aqui
        mostra o DESENHO de cada uma - bandeira azul, cifrao, cadeado - para dar
        para reordenar na mao sabendo o que se esta movendo. Sem rota gravada, o
        bot cai na regra de ouro: vai sempre para a marca mais proxima que ainda
        nao visitou.
        """
        self.rota_pontos = []
        self.rota_icones = []
        self.rota_imagens = []          # o Tk descarta imagem sem referencia
        self.thread_gravacao = None
        self.parar_gravacao = None

        quadro = ttk.LabelFrame(aba, text="Rota gravada (ordem das marcas)")
        quadro.grid(row=linha, column=0, sticky="ew", padx=8, pady=4)

        var_arquivo = tk.StringVar(value=main.WAYPOINTS_FILE)
        self.vars["WAYPOINTS_FILE"] = (var_arquivo, str)
        self.var_rota_arquivo = var_arquivo
        self.vars["USE_ROUTE_ORDER"] = (tk.BooleanVar(value=True), bool)

        topo = ttk.Frame(quadro)
        topo.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 2))
        ttk.Label(topo, text="arquivo").grid(row=0, column=0, padx=(0, 4))
        self.combo_rota = ttk.Combobox(topo, width=16, state="readonly")
        self.combo_rota.grid(row=0, column=1)
        self.combo_rota.bind("<<ComboboxSelected>>", self._troca_rota)
        ttk.Button(topo, text="Recarregar", width=11,
                   command=self.carregar_rota).grid(row=0, column=2, padx=3)
        ttk.Button(topo, text="Nova...", width=8,
                   command=self.nova_rota).grid(row=0, column=3)
        ttk.Button(topo, text="Salvar rota", width=11,
                   command=self.salvar_rota).grid(row=0, column=4, padx=3)

        ttk.Checkbutton(quadro, text="seguir a ordem gravada (sem rota, vale a "
                        "regra de ouro)",
                        variable=self.vars["USE_ROUTE_ORDER"][0]).grid(
            row=1, column=0, sticky="w", padx=6)

        corpo = ttk.Frame(quadro)
        corpo.grid(row=2, column=0, sticky="ew", padx=6, pady=4)
        # linha alta o bastante para o desenho da marca aparecer inteiro
        ttk.Style().configure("Rota.Treeview", rowheight=MARK_ICON_ZOOM * 13 + 4)
        self.lista_rota = ttk.Treeview(corpo, columns=("onde",), height=5,
                                       selectmode="browse",
                                       style="Rota.Treeview")
        self.lista_rota.heading("#0", text="  ordem")
        self.lista_rota.heading("onde", text="posicao (SQM)")
        self.lista_rota.column("#0", width=110, stretch=False)
        self.lista_rota.column("onde", width=140, stretch=False)
        self.lista_rota.grid(row=0, column=0, rowspan=5, sticky="nsew")
        barra = ttk.Scrollbar(corpo, orient="vertical",
                              command=self.lista_rota.yview)
        barra.grid(row=0, column=1, rowspan=5, sticky="ns")
        self.lista_rota.config(yscrollcommand=barra.set)

        for i, (texto, acao) in enumerate((
                ("Subir", lambda: self._move_ponto(-1)),
                ("Descer", lambda: self._move_ponto(1)),
                ("Remover", self._remove_ponto),
                ("Limpar", self.limpar_rota))):
            ttk.Button(corpo, text=texto, width=9, command=acao).grid(
                row=i, column=2, padx=(6, 0), pady=1, sticky="w")

        acoes = ttk.Frame(quadro)
        acoes.grid(row=3, column=0, sticky="w", padx=6, pady=(0, 6))
        self.btn_gravar = ttk.Button(acoes, text="Gravar clicando nas marcas",
                                     command=self.gravar_rota)
        self.btn_gravar.grid(row=0, column=0)
        self.btn_parar_gravar = ttk.Button(acoes, text="Parar gravacao",
                                           command=self.parar_de_gravar,
                                           state="disabled")
        self.btn_parar_gravar.grid(row=0, column=1, padx=6)

        ttk.Label(quadro, foreground="#555", justify="left",
                  text="Clique nas marcas na ordem da rota. A gravacao poe o "
                       "PROJETOR na\nfrente: clicando nele o personagem fica "
                       "parado, entao da para gravar\ntudo do lugar. Clicando na "
                       "janela do JOGO ele anda ate a marca -\nutil quando a rota "
                       "nao cabe inteira no minimapa.\n\nO clique e encaixado na "
                       "marca mais proxima. O desenho ao lado do\nnumero e so "
                       "para voce reconhecer o ponto; a navegacao nao usa."
                  ).grid(row=4, column=0, sticky="w", padx=8, pady=(0, 6))
        self.raiz.after(0, self.atualiza_rotas)

    # ------------------------------------------------------------ rota: dados
    def arquivo_rota(self):
        return self.var_rota_arquivo.get() or main.WAYPOINTS_FILE

    def atualiza_rotas(self):
        """Lista os arquivos de rota e seleciona o que esta em uso."""
        nomes = main.rotas_disponiveis()
        atual = os.path.splitext(os.path.basename(self.arquivo_rota()))[0]
        if atual and atual not in nomes:
            nomes = sorted(nomes + [atual])
        self.combo_rota["values"] = nomes
        if atual:
            self.combo_rota.set(atual)
        self.carregar_rota()

    def _troca_rota(self, _evento=None):
        nome = self.combo_rota.get()
        if nome:
            self.var_rota_arquivo.set(os.path.join(main.ROUTES_DIR,
                                                   nome + ".json"))
            self.carregar_rota()

    def carregar_rota(self):
        caminho = self.arquivo_rota()
        main.WAYPOINTS_FILE = caminho
        self.rota_pontos = main.load_waypoints(caminho)
        self.rota_icones = main.load_icones(caminho)
        while len(self.rota_icones) < len(self.rota_pontos):
            self.rota_icones.append(None)
        self._pinta_rota()
        self.escreve_log(f"[rota] {len(self.rota_pontos)} ponto(s) de "
                         f"{os.path.basename(caminho)}")

    def salvar_rota(self):
        caminho = self.arquivo_rota()
        main.save_waypoints(self.rota_pontos, caminho, self.rota_icones)
        self.atualiza_rotas()

    def nova_rota(self):
        nome = simpledialog.askstring("Nova rota", "Nome do arquivo:",
                                      parent=self.raiz)
        if not nome:
            return
        nome = "".join(c for c in nome if c.isalnum() or c in "-_ ").strip()
        if not nome:
            return
        self.var_rota_arquivo.set(os.path.join(main.ROUTES_DIR, nome + ".json"))
        self.rota_pontos, self.rota_icones = [], []
        self.salvar_rota()

    def limpar_rota(self):
        self.rota_pontos, self.rota_icones = [], []
        self._pinta_rota()

    def _selecionado(self):
        escolha = self.lista_rota.selection()
        if not escolha:
            return None
        return int(escolha[0])

    def _move_ponto(self, passo):
        i = self._selecionado()
        if i is None:
            return
        j = i + passo
        if not 0 <= j < len(self.rota_pontos):
            return
        for lista in (self.rota_pontos, self.rota_icones):
            lista[i], lista[j] = lista[j], lista[i]
        self._pinta_rota(seleciona=j)

    def _remove_ponto(self):
        i = self._selecionado()
        if i is None:
            return
        self.rota_pontos.pop(i)
        if i < len(self.rota_icones):
            self.rota_icones.pop(i)
        self._pinta_rota(seleciona=min(i, len(self.rota_pontos) - 1))

    def _imagem_do_icone(self, arr, zoom=MARK_ICON_ZOOM):
        """Converte o recorte do minimapa numa imagem que o Tk mostra na lista."""
        if arr is None:
            return None
        linhas = []
        for y in range(arr.shape[0]):
            px = " ".join("#%02x%02x%02x" % tuple(int(c) for c in arr[y, x])
                          for x in range(arr.shape[1]))
            linhas.append("{" + px + "}")
        img = tk.PhotoImage(width=arr.shape[1], height=arr.shape[0])
        img.put(" ".join(linhas))
        return img.zoom(zoom)

    def _pinta_rota(self, seleciona=None):
        self.lista_rota.delete(*self.lista_rota.get_children())
        self.rota_imagens = []
        escala = main.MINIMAP_PX_SQM or 1
        for i, (x, y) in enumerate(self.rota_pontos):
            icone = self.rota_icones[i] if i < len(self.rota_icones) else None
            img = self._imagem_do_icone(icone)
            self.rota_imagens.append(img)
            valores = (f"({x / escala:.0f}, {y / escala:.0f})",)
            if img is not None:
                self.lista_rota.insert("", "end", iid=str(i), image=img,
                                       text=f" {i + 1}", values=valores)
            else:
                self.lista_rota.insert("", "end", iid=str(i),
                                       text=f" {i + 1}", values=valores)
        if seleciona is not None and 0 <= seleciona < len(self.rota_pontos):
            self.lista_rota.selection_set(str(seleciona))
            self.lista_rota.see(str(seleciona))

    # --------------------------------------------------------- rota: gravacao
    def gravar_rota(self):
        if self.thread_bot and self.thread_bot.is_alive():
            self.escreve_log("[rota] pare o bot antes de gravar")
            return
        if self.thread_gravacao and self.thread_gravacao.is_alive():
            return
        self.aplicar()
        self.limpar_rota()
        self.parar_gravacao = threading.Event()
        self.btn_gravar.config(state="disabled")
        self.btn_parar_gravar.config(state="normal")
        self.escreve_log("[rota] gravando: clique nas marcas na ordem da rota")

        def tarefa():
            try:
                main.record_marks(caminho=self.arquivo_rota(),
                                  parar=self.parar_gravacao,
                                  ao_gravar=self._ponto_gravado)
            except Exception as erro:                      # nao derrubar a GUI
                self.fila_log.put(f"[rota] erro na gravacao: {erro}")
            finally:
                self.raiz.after(0, self._fim_da_gravacao)

        self.thread_gravacao = threading.Thread(target=tarefa, daemon=True)
        self.thread_gravacao.start()

    def _ponto_gravado(self, indice, ponto, icone):
        """Chamado pela thread de gravacao a cada marca clicada."""
        def anota():
            self.rota_pontos.append(ponto)
            self.rota_icones.append(icone)
            self._pinta_rota(seleciona=len(self.rota_pontos) - 1)
        self.raiz.after(0, anota)

    def parar_de_gravar(self):
        if self.parar_gravacao:
            self.parar_gravacao.set()

    def _fim_da_gravacao(self):
        self.btn_gravar.config(state="normal")
        self.btn_parar_gravar.config(state="disabled")
        self.escreve_log(f"[rota] gravacao encerrada com "
                         f"{len(self.rota_pontos)} ponto(s)")

    def _monta_monstros(self, aba, linha):
        """
        Lista de monstros para atacar.

        Duas formas de entrar na lista: cadastrar o NOME agora (fica pendente,
        sem sprite) ou capturar o SPRITE de uma linha da battle list. So o sprite
        reconhece o bicho - nome sozinho nao filtra nada, porque a leitura e de
        pixel e ler o nome exigiria OCR.
        """
        quadro = ttk.LabelFrame(aba, text="Monstros para atacar")
        quadro.grid(row=linha, column=0, sticky="ew", padx=8, pady=4)

        var = tk.BooleanVar()
        ttk.Checkbutton(quadro, text="atacar so os desta lista", variable=var,
                        command=self._atualiza_habilitacao).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(2, 2))
        self.vars["ONLY_KNOWN_MONSTERS"] = (var, bool)

        auto = tk.BooleanVar()
        ttk.Checkbutton(quadro, text="aprender sozinho o bicho que engajar",
                        variable=auto, command=self._atualiza_habilitacao).grid(
            row=1, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 4))
        self.vars["AUTO_LEARN"] = (auto, bool)

        self.lista_monstros = tk.Listbox(quadro, height=4, width=26,
                                         exportselection=False)
        self.lista_monstros.grid(row=2, column=0, rowspan=3, padx=6, pady=2)
        self._recarrega_monstros()

        col = ttk.Frame(quadro)
        col.grid(row=2, column=1, rowspan=3, sticky="nw", padx=4, pady=2)
        ttk.Label(col, text="Nome do monstro").grid(row=0, column=0, sticky="w")
        self.nome_monstro = tk.StringVar()
        ttk.Entry(col, textvariable=self.nome_monstro, width=22).grid(
            row=1, column=0, sticky="w", pady=(1, 4))

        acoes = ttk.Frame(col)
        acoes.grid(row=2, column=0, sticky="w")
        # ROTULOS QUE NAO PROMETEM O QUE NAO ENTREGAM. "Adicionar nome"
        # cadastra o nome e nada mais - quem reconhece o bicho e o sprite, e sem
        # ele o monstro nao e atacado. Lido como "adicionar monstro", o botao
        # parecia nao funcionar: fazia o que dizia, e nao o que se esperava.
        ttk.Button(acoes, text="1. So o nome", width=16,
                   command=self.adicionar_monstro).grid(row=0, column=0, pady=1)
        ttk.Button(acoes, text="Renomear", width=11,
                   command=self.renomear_monstro).grid(row=0, column=1,
                                                       padx=(4, 0), pady=1)
        ttk.Button(acoes, text="2. Pegar o sprite", width=16,
                   command=self.aprender_monstro).grid(row=1, column=0, pady=1)
        canto = ttk.Frame(acoes)
        canto.grid(row=1, column=1, padx=(4, 0), pady=1, sticky="w")
        self.linha_battle = tk.StringVar(value="1")
        ttk.Spinbox(canto, from_=1, to=8, width=3,
                    textvariable=self.linha_battle).grid(row=0, column=0)
        ttk.Button(canto, text="Remover", width=8,
                   command=self.remover_monstro).grid(row=0, column=1, padx=(3, 0))

        # O RECADO FICA AQUI, e nao so no log: o log e de poucas linhas e a
        # explicacao rolava para fora antes de ser lida.
        self.lbl_monstro = ttk.Label(quadro, text="", foreground="#a70",
                                     wraplength=430, justify="left")
        self.lbl_monstro.grid(row=5, column=0, columnspan=3, sticky="w",
                              padx=6, pady=(4, 0))
        self.lbl_filtro = ttk.Label(quadro, text="", foreground="#777")
        self.lbl_filtro.grid(row=6, column=0, columnspan=3, sticky="w",
                             padx=6, pady=(2, 0))
        ttk.Label(quadro, wraplength=430, justify="left", foreground="#777",
                  text="Duas etapas: (1) cadastra o nome, (2) com o bicho "
                       "ENGAJADO no jogo, pega o sprite da linha escolhida da "
                       "battle list. So o sprite reconhece - nome sozinho nao "
                       "filtra nada, porque a leitura e de pixel."
                  ).grid(row=7, column=0, columnspan=3, sticky="w", padx=6,
                         pady=(2, 4))
        self._dica_monstro()

    def _monta_autocast(self, aba, linha):
        """
        Um slot por linha: ligar, tecla e intervalo em segundos.

        Para o que se repete no tempo e nao depende de vida, mana ou monstro:
        haste, comida, buff, anel. Roda depois da cura na ordem do loop, e o
        piso de mana evita que buff coma a mana reservada para curar.
        """
        quadro = ttk.LabelFrame(aba, text="Teclas em intervalo fixo")
        quadro.grid(row=linha, column=0, sticky="ew", padx=8, pady=4)

        for col, titulo in enumerate(("", "Tecla", "Intervalo (s)")):
            ttk.Label(quadro, text=titulo, foreground="#777").grid(
                row=0, column=col, sticky="w", padx=6, pady=(2, 0))

        self.autocast_vars = []
        for i, slot in enumerate(main.AUTOCAST):
            ativo = tk.BooleanVar(value=bool(slot.get("ativo")))
            tecla = tk.StringVar(value=str(slot.get("tecla") or ""))
            intervalo = tk.StringVar(value=str(slot.get("intervalo") or ""))
            ttk.Checkbutton(quadro, variable=ativo).grid(
                row=i + 1, column=0, padx=6, pady=2)
            ttk.Entry(quadro, textvariable=tecla, width=10).grid(
                row=i + 1, column=1, sticky="w", pady=2)
            ttk.Entry(quadro, textvariable=intervalo, width=10).grid(
                row=i + 1, column=2, sticky="w", padx=6, pady=2)
            self.autocast_vars.append((ativo, tecla, intervalo))

        ttk.Label(quadro, text="mudanca de slot vale no proximo Iniciar",
                  foreground="#777").grid(row=len(main.AUTOCAST) + 1, column=0,
                                          columnspan=3, sticky="w", padx=6,
                                          pady=(2, 4))

    def _monta_log(self):
        """
        O log, com barra de rolagem.

        Era um Text de 6 linhas sem barra: mensagem que passava estava perdida
        para sempre, e as explicacoes do bot sao longas (a de cadastrar monstro
        sem sprite ocupa tres linhas sozinha). Sem poder rolar para tras, o
        painel escondia a resposta a pergunta que o usuario acabara de fazer.
        """
        quadro = ttk.LabelFrame(self.raiz, text="Log")
        quadro.grid(row=2, column=0, padx=10, pady=(4, 10), sticky="ew")
        quadro.columnconfigure(0, weight=1)
        self.log = tk.Text(quadro, height=8, width=74, state="disabled",
                           wrap="word", font=("Consolas", 9),
                           background="#1e1e1e", foreground="#d4d4d4",
                           relief="flat")
        self.log.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        barra = ttk.Scrollbar(quadro, orient="vertical", command=self.log.yview)
        barra.grid(row=0, column=1, sticky="ns", pady=2)
        self.log.configure(yscrollcommand=barra.set)

    # ------------------------------------------------------------- estado UI
    def _atualiza_habilitacao(self):
        for interruptor, attrs in self.blocos:
            ligado = bool(self.vars[interruptor][0].get())
            for attr in attrs:
                for w in self.widgets.get(attr, []):
                    try:
                        w.config(state="normal" if ligado else "disabled")
                    except tk.TclError:
                        pass
        so_lista = bool(self.vars["ONLY_KNOWN_MONSTERS"][0].get())
        com_sprite = sum(1 for a in self.monstros.values() if a is not None)
        if so_lista:
            texto = (f"filtrando por {com_sprite} sprite(s): bicho fora da lista "
                     f"nao e atacado" if com_sprite
                     else "filtro ligado, mas nenhum sprite aprendido: "
                          "nada sera atacado")
            cor = "#284" if com_sprite else "#a33"
        else:
            texto, cor = "sem filtro: ataca qualquer bicho da battle list", "#777"
        self.lbl_filtro.config(text=texto, foreground=cor)

    def _recarrega_monstros(self):
        self.lista_monstros.delete(0, "end")
        for nome in sorted(self.monstros):
            marca = "" if self.monstros[nome] is not None else "  (sem sprite)"
            self.lista_monstros.insert("end", nome + marca)
        # o recado sai daqui para valer em TODA acao (aprender, renomear,
        # remover) e nao so ao cadastrar. Na montagem do painel o rotulo ainda
        # nao existe.
        if hasattr(self, "lbl_monstro"):
            self._dica_monstro()

    def _dica_monstro(self, recado=None):
        """
        Diz, no proprio bloco, qual e o proximo passo.

        Cadastrar o nome nao faz o bicho ser atacado, e essa frase vivia so no
        log - onde some. Aqui ela fica na tela ate deixar de ser verdade.
        """
        if recado is None:
            pendentes = [n for n, sp in self.monstros.items() if sp is None]
            if not self.monstros:
                recado = ("lista vazia: cadastre o nome e depois pegue o sprite "
                          "com o bicho engajado")
            elif pendentes:
                recado = (f"{len(pendentes)} sem sprite ({', '.join(pendentes[:3])}"
                          f"{'...' if len(pendentes) > 3 else ''}): esses NAO sao "
                          f"atacados. Engaje o bicho e use '2. Pegar o sprite'")
            else:
                recado = ""
        self.lbl_monstro.config(text=recado)

    def _nome_selecionado(self):
        sel = self.lista_monstros.curselection()
        if not sel:
            return None
        return self.lista_monstros.get(sel[0]).split("  (sem sprite)")[0]

    # ------------------------------------------------------------- config
    def coletar(self):
        cfg = {}
        for attr, (var, tipo) in self.vars.items():
            bruto = var.get()
            if tipo is bool:
                cfg[attr] = bool(bruto)
            elif tipo is str:
                cfg[attr] = str(bruto).strip() or None
            else:
                try:
                    valor = float(bruto)
                except (TypeError, ValueError):
                    continue
                cfg[attr] = int(valor) if tipo is int else valor
        return cfg

    def coletar_autocast(self):
        slots = []
        for ativo, tecla, intervalo in getattr(self, "autocast_vars", []):
            try:
                segundos = float(intervalo.get())
            except (TypeError, ValueError):
                segundos = 0.0
            slots.append({"ativo": bool(ativo.get()),
                          "tecla": tecla.get().strip(),
                          "intervalo": segundos})
        return slots

    def aplicar(self):
        for attr, valor in self.coletar().items():
            setattr(main, attr, valor)
        slots = self.coletar_autocast()
        if slots:
            main.AUTOCAST = slots
        # as teclas de andar sao montadas a partir da configuracao: sem refazer
        # aqui, mudar as diagonais no painel deixava o bot decidindo por uma
        # tecla nova e consultando a tabela velha - KeyError no meio da cacada
        main.atualiza_passos()
        # AVISO NAO SE REPETE. O aplicar() roda em Salvar, Iniciar, Aprender e
        # ao carregar a config, e cada chamada reimprimia a lista inteira de
        # avisos. Num log de poucas linhas, oito copias do mesmo aviso empurram
        # para fora justamente a mensagem que explica o que acabou de
        # acontecer - foi assim que "cadastrei o nome, e agora?" virou "nao
        # consigo adicionar monstro". Condicao que continua igual nao merece
        # linha nova.
        agora = tuple(self.avisos())
        if agora != getattr(self, "_avisos_ditos", None):
            for aviso in agora:
                self.escreve_log("[aviso] " + aviso)
            self._avisos_ditos = agora

    def avisos(self):
        """
        Combinacoes que compilam mas se sabotam na pratica.

        Erros faceis de cometer e dificeis de notar rodando: a emergencia
        disparando antes da cura normal, magia sem reserva de mana para curar,
        limite em pontos acima do maximo, filtro sem sprite nenhum.
        """
        fora = []
        cura = main.como_fracao(main.HEAL_THRESHOLD, main.HP_MAX)
        forte = (main.como_fracao(main.HEAL_STRONG_THRESHOLD, main.HP_MAX)
                 if main.HEAL_STRONG_HOTKEY else None)
        piso = main.como_fracao(main.SPELL_MANA_FLOOR, main.MANA_MAX)

        if forte is not None and cura is not None and forte >= cura:
            fora.append(f"emergencia ({main.HEAL_STRONG_THRESHOLD}) dispara antes "
                        f"da cura normal ({main.HEAL_THRESHOLD}); a emergencia "
                        f"deve ser o limite MAIS BAIXO")
        if piso is not None and piso < 0.10:
            fora.append(f"piso da magia muito baixo ({main.SPELL_MANA_FLOOR}): "
                        f"conjurando ate ai nao sobra mana para a cura")
        if main.ONLY_KNOWN_MONSTERS:
            com_sprite = sum(1 for a in self.monstros.values() if a is not None)
            if not com_sprite and not main.AUTO_LEARN:
                fora.append("filtro de monstros ligado e nenhum sprite aprendido: "
                            "nada sera atacado (ligue o aprendizado automatico)")
        for rotulo, valor, maximo in (("vida", main.HEAL_THRESHOLD, main.HP_MAX),
                                      ("mana", main.MANA_THRESHOLD, main.MANA_MAX)):
            if valor and valor > 1 and maximo and valor > maximo:
                fora.append(f"limite de {rotulo} ({valor}) acima do maximo "
                            f"do personagem ({maximo})")
        return fora

    def preencher(self, cfg):
        slots = cfg.get("AUTOCAST")
        if slots:
            main.AUTOCAST = slots
            for (ativo, tecla, intervalo), slot in zip(
                    getattr(self, "autocast_vars", []), slots):
                ativo.set(bool(slot.get("ativo")))
                tecla.set(str(slot.get("tecla") or ""))
                intervalo.set(str(slot.get("intervalo") or ""))
        for attr, (var, tipo) in self.vars.items():
            valor = cfg.get(attr, getattr(main, attr, None))
            var.set(bool(valor) if tipo is bool else
                    ("" if valor is None else str(valor)))

    def carregar(self):
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    cfg = json.load(f)
                self.escreve_log(f"[gui] config carregada de {CONFIG_FILE}")
            except (OSError, ValueError) as erro:
                self.escreve_log(f"[gui] config invalida ({erro}); usando o main.py")
        self.preencher(cfg)
        self.aplicar()

    def salvar(self):
        self.aplicar()
        dados = self.coletar()
        dados["AUTOCAST"] = self.coletar_autocast()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        self.escreve_log(f"[gui] config salva em {CONFIG_FILE}")

    # ------------------------------------------------------------- acoes
    def iniciar(self):
        if self.thread_bot and self.thread_bot.is_alive():
            return
        self.aplicar()
        main.STOP = False
        self.escreve_log("[gui] iniciando; o foco vai para o jogo")
        self.thread_bot = threading.Thread(target=self._roda_bot, daemon=True)
        self.thread_bot.start()
        self.btn_iniciar.config(state="disabled")
        self.btn_parar.config(state="normal")
        self.lbl_bot.config(text="bot rodando", foreground="#284")

    def _roda_bot(self):
        # o stderr tambem: sem console ele e None, e o que for escrito nele se
        # perde em silencio - inclusive erro de callback do Tk
        antigo, antigo_err = sys.stdout, sys.stderr
        sys.stdout = FilaDeSaida(self.fila_log, antigo)
        sys.stderr = FilaDeSaida(self.fila_log, antigo_err)
        try:
            main.run_bot()
        except Exception as erro:
            self.fila_log.put(f"[erro] {type(erro).__name__}: {erro}")
            self.fila_log.put(traceback.format_exc())
        finally:
            sys.stdout, sys.stderr = antigo, antigo_err
            main.restore_windows()
            self.fila_log.put("[gui] bot encerrado")

    def parar(self):
        main.STOP = True
        self.btn_parar.config(state="disabled")
        self.btn_iniciar.config(state="normal")
        self.lbl_bot.config(text="bot parado", foreground="#a33")

    def adicionar_monstro(self):
        """Cadastra o nome sem sprite: entra na lista como pendente."""
        nome = self.nome_monstro.get().strip()
        if not nome:
            self.escreve_log("[gui] digite o nome do monstro")
            return
        antigo = sys.stdout
        sys.stdout = FilaDeSaida(self.fila_log, antigo)
        try:
            self.monstros = main.add_monster_name(nome, self.monstros)
        finally:
            sys.stdout = antigo
        self.nome_monstro.set("")
        self._recarrega_monstros()
        self._atualiza_habilitacao()
        self._dica_monstro(f"'{nome}' cadastrado SEM SPRITE, e por isso ainda "
                           f"nao sera atacado. Agora engaje esse bicho no jogo, "
                           f"escolha a linha dele na battle list e clique "
                           f"'2. Pegar o sprite'.")

    def aprender_monstro(self):
        """Liga o sprite da linha escolhida da battle list a um nome."""
        nome = self.nome_monstro.get().strip() or self._nome_selecionado()
        if not nome:
            self.escreve_log("[gui] digite um nome ou escolha um da lista")
            return
        self.aplicar()
        win = main.find_projector() if main.OBS_MODE else main.find_tibia()
        if not win or not main.is_usable(win):
            self.escreve_log("[gui] janela de leitura indisponivel")
            return
        try:
            linha = max(int(self.linha_battle.get()) - 1, 0)
        except (TypeError, ValueError):
            linha = 0
        antigo = sys.stdout
        sys.stdout = FilaDeSaida(self.fila_log, antigo)
        try:
            self.monstros = main.learn_monster(win, nome, self.monstros, linha)
        finally:
            sys.stdout = antigo
        self.nome_monstro.set("")
        self._recarrega_monstros()
        self._atualiza_habilitacao()

    def renomear_monstro(self):
        """Batiza o selecionado com o nome digitado (bicho 1 -> Bonelord)."""
        antigo_nome = self._nome_selecionado()
        novo = self.nome_monstro.get().strip()
        if not antigo_nome or not novo:
            self.escreve_log("[gui] escolha um da lista e digite o nome novo")
            return
        saida = sys.stdout
        sys.stdout = FilaDeSaida(self.fila_log, saida)
        try:
            self.monstros = main.rename_monster(antigo_nome, novo, self.monstros)
        finally:
            sys.stdout = saida
        self.nome_monstro.set("")
        self._recarrega_monstros()

    def remover_monstro(self):
        nome = self._nome_selecionado()
        if not nome:
            return
        self.monstros.pop(nome, None)
        main.save_monsters(self.monstros)
        self.escreve_log(f"[gui] '{nome}' removido da lista")
        self._recarrega_monstros()
        self._atualiza_habilitacao()

    # ------------------------------------------------------------- status
    def _inicia_status(self):
        def tarefa():
            while not self.parar_status.wait(0.7):
                try:
                    win = (main.find_projector() if main.OBS_MODE
                           else main.find_tibia())
                    if not win or not main.is_usable(win):
                        self.fila_status.put(None)
                        continue
                    hp, mana = main.read_bars(win)
                    entradas, alvo, alvo_hp, sprites, _ = main.battle_state(win)
                    self.fila_status.put({
                        "hp": hp, "mana": mana, "entradas": entradas,
                        "alvo": alvo, "alvo_hp": alvo_hp,
                        "conhecido": main.monstro_conhecido(sprites, self.monstros),
                        "marcas": len(main.detect_marks(win)),
                    })
                except Exception:
                    self.fila_status.put(None)

        threading.Thread(target=tarefa, daemon=True).start()

    def _bombeia_status(self):
        ultimo, tem = None, False
        while True:
            try:
                ultimo, tem = self.fila_status.get_nowait(), True
            except queue.Empty:
                break
        if tem:
            if ultimo is None:
                self.lbl_vida.config(text="vida  -")
                self.lbl_mana.config(text="mana  -")
                self.lbl_battle.config(text="battle list  janela indisponivel")
                self.lbl_marcas.config(text="marcas  -")
            else:
                self.lbl_vida.config(
                    text=f"vida  {main.formata(ultimo['hp'], main.HP_MAX)}")
                self.lbl_mana.config(
                    text=f"mana  {main.formata(ultimo['mana'], main.MANA_MAX)}")
                if ultimo["alvo"]:
                    vida = ("" if ultimo["alvo_hp"] is None
                            else f" com {ultimo['alvo_hp']:.0%} de vida")
                    situacao = f"alvo engajado{vida}"
                elif ultimo["entradas"]:
                    situacao = "sem alvo, atacaria"
                else:
                    situacao = "vazia"
                extra = (f" | reconhecido: {ultimo['conhecido']}"
                         if ultimo["conhecido"] else "")
                self.lbl_battle.config(
                    text=f"battle list  {ultimo['entradas']} - {situacao}{extra}")
                self.lbl_marcas.config(
                    text=f"marcas  {ultimo['marcas']} visiveis no minimapa "
                         f"({main.MARK_COLOR})")
        self.raiz.after(500, self._bombeia_status)

    # ------------------------------------------------------------- log
    def escreve_log(self, linha):
        if not hasattr(self, "log"):        # ainda montando a janela
            self.fila_log.put(linha)
            return
        self.log.config(state="normal")
        self.log.insert("end", linha + "\n")
        self.log.see("end")
        if int(self.log.index("end-1c").split(".")[0]) > 400:
            self.log.delete("1.0", "100.0")
        self.log.config(state="disabled")

    def _bombeia_log(self):
        for _ in range(40):
            try:
                self.escreve_log(self.fila_log.get_nowait())
            except queue.Empty:
                break
        if self.thread_bot and self.thread_bot.is_alive():
            atual = main.load_monsters()
            if set(atual) != set(self.monstros):
                self.monstros = atual
                self._recarrega_monstros()
        if self.thread_bot and not self.thread_bot.is_alive():
            self.btn_iniciar.config(state="normal")
            self.btn_parar.config(state="disabled")
            self.lbl_bot.config(text="bot parado", foreground="#a33")
        self.raiz.after(200, self._bombeia_log)

    def fechar(self):
        main.STOP = True
        self.parar_status.set()
        try:
            main.restore_windows()
        except Exception:
            pass
        self.raiz.destroy()


if __name__ == "__main__":
    raiz = tk.Tk()
    Painel(raiz)
    raiz.mainloop()
