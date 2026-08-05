import customtkinter as ctk
from tkinterdnd2 import DND_FILES

from core.configuracao import config_app

MODO_HIBRIDO = "Híbrido (Texto Nativo + OCR em Imagem Relevante)"
MODO_HIBRIDO_ANTIGO = "Híbrido (Automático)"
MODO_FORCAR_OCR = "Forçar OCR (Ignora Texto Nativo)"
MODO_FORCAR_OCR_ANTIGO = "Forçar OCR em Todas as Páginas"
MODO_REFERENCIA_IMAGEM = "Texto Nativo + Referência de Imagem (Sem OCR)"


def normalizar_modo_conversao(valor):
    aliases = {
        MODO_HIBRIDO_ANTIGO: MODO_HIBRIDO,
        MODO_FORCAR_OCR_ANTIGO: MODO_FORCAR_OCR,
        MODO_REFERENCIA_IMAGEM: MODO_REFERENCIA_IMAGEM,
        MODO_HIBRIDO: MODO_HIBRIDO,
        MODO_FORCAR_OCR: MODO_FORCAR_OCR,
    }
    return aliases.get(valor, MODO_HIBRIDO)

class TelaInicio(ctk.CTkFrame):
    def __init__(self, master, comando_selecionar_pdf, comando_soltar_pdf, comando_pasta, comando_converter, comando_cancelar, comando_importar_pasta):
        super().__init__(master, fg_color="transparent")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ==========================================
        # COLUNA ESQUERDA: Galeria e Scanner
        # ==========================================
        self.frame_upload = ctk.CTkFrame(self)
        self.frame_upload.grid(row=0, column=0, rowspan=2, padx=(0, 10), pady=(0, 10), sticky="nsew")
        self.frame_upload.grid_rowconfigure(1, weight=1)
        self.frame_upload.grid_columnconfigure(0, weight=1)
        
        self.lbl_upload_titulo = ctk.CTkLabel(self.frame_upload, text="Conversor de Processos PDF para Markdown", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_upload_titulo.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # --- A) GRADE DE GALERIA (Visível na seleção) ---
        self.frame_galeria = ctk.CTkFrame(self.frame_upload, fg_color="#1c1c1e", corner_radius=10)
        self.frame_galeria.grid(row=1, column=0, padx=20, pady=5, sticky="nsew")
        self.frame_galeria.grid_columnconfigure((0, 1), weight=1, uniform="col")
        self.frame_galeria.grid_rowconfigure((0, 1), weight=1, uniform="row")

        # --- B) MODO SCANNER (Visível durante a conversão) ---
        self.frame_scanner = ctk.CTkFrame(self.frame_upload, fg_color="#1c1c1e", corner_radius=10)
        self.frame_scanner.grid(row=1, column=0, padx=20, pady=5, sticky="nsew")
        self.frame_scanner.grid_columnconfigure(0, weight=1)
        self.frame_scanner.grid_rowconfigure(0, weight=1)
        self.frame_scanner.grid_remove() # Fica escondido até iniciar

        # A "Folha" do scanner central
        self.folha_scanner = ctk.CTkFrame(self.frame_scanner, fg_color="white", corner_radius=0, border_width=1, border_color="#555555")
        self.folha_scanner.grid(row=0, column=0, pady=(20, 5))
        
        self.lbl_img_scanner = ctk.CTkLabel(self.folha_scanner, text="")
        self.lbl_img_scanner.pack(padx=5, pady=5) # Padding da folha branca
        
        self.lbl_nome_scanner = ctk.CTkLabel(self.frame_scanner, text="", text_color="#a1a1aa", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_nome_scanner.grid(row=1, column=0, pady=(0, 20))

        # A linha azul fica DENTRO da folha branca agora!
        self.linha_scanner = ctk.CTkFrame(self.folha_scanner, height=4, fg_color="#3b82f6", corner_radius=2)
        self.animando = False
        self.pos_y = 0.02
        self.direcao = 1

        # --- BOTÕES INFERIORES ---
        self.frame_botoes_upload = ctk.CTkFrame(self.frame_upload, fg_color="transparent")
        self.frame_botoes_upload.grid(row=2, column=0, padx=20, pady=(10, 5), sticky="ew")
        self.frame_botoes_upload.grid_columnconfigure((0, 1), weight=1)

        self.btn_arquivos = ctk.CTkButton(self.frame_botoes_upload, text="📄 Adicionar Arquivos", fg_color="#3f3f46", hover_color="#52525b", command=comando_selecionar_pdf)
        self.btn_arquivos.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.btn_pasta = ctk.CTkButton(self.frame_botoes_upload, text="📁 Importar Pasta", fg_color="#3f3f46", hover_color="#52525b", command=comando_importar_pasta)
        self.btn_pasta.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        self.lbl_arquivo_selecionado = ctk.CTkLabel(self.frame_upload, text="0 arquivos prontos", text_color="gray", font=ctk.CTkFont(size=12))
        self.lbl_arquivo_selecionado.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="w")

        # ==========================================
        # COLUNA DIREITA: Opções e Preview
        # ==========================================
        self.frame_opcoes = ctk.CTkFrame(self)
        self.frame_opcoes.grid(row=0, column=1, padx=(10, 0), pady=(0, 10), sticky="nsew")
        
        self.lbl_opcoes_titulo = ctk.CTkLabel(self.frame_opcoes, text="Parâmetros de Leitura", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_opcoes_titulo.grid(row=0, column=0, columnspan=2, padx=20, pady=(15, 5), sticky="w")

        self.lbl_modo = ctk.CTkLabel(self.frame_opcoes, text="Modo de Processamento:")
        self.lbl_modo.grid(row=1, column=0, padx=20, pady=5, sticky="w")
        self.opt_modo = ctk.CTkOptionMenu(
            self.frame_opcoes,
            values=[
                MODO_HIBRIDO,
                MODO_FORCAR_OCR,
                MODO_REFERENCIA_IMAGEM,
            ],
        )
        self.opt_modo.grid(row=1, column=1, padx=20, pady=5, sticky="e")
        self.opt_modo.set(normalizar_modo_conversao(config_app.get("modo_conversao")))

        self.btn_destino = ctk.CTkButton(self.frame_opcoes, text="Escolher Pasta Destino", fg_color="#444444", hover_color="#555555", command=comando_pasta)
        self.btn_destino.grid(row=3, column=0, columnspan=2, padx=20, pady=(10, 0), sticky="ew")
        self.lbl_caminho_destino = ctk.CTkLabel(self.frame_opcoes, text="Padrão: Mesma pasta do PDF", text_color="gray", font=ctk.CTkFont(size=11))
        self.lbl_caminho_destino.grid(row=4, column=0, columnspan=2, padx=20, pady=(2, 10), sticky="w")

        self.frame_preview = ctk.CTkFrame(self)
        self.frame_preview.grid(row=1, column=1, padx=(10, 0), pady=(10, 10), sticky="nsew")
        self.frame_preview.grid_rowconfigure(0, weight=1)
        self.frame_preview.grid_columnconfigure(0, weight=1)

        self.textbox_preview = ctk.CTkTextbox(self.frame_preview, font=ctk.CTkFont(family="Consolas", size=12))
        self.textbox_preview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.textbox_preview.insert("0.0", "O texto convertido aparecerá aqui à medida que as páginas forem processadas...")
        self.textbox_preview.configure(state="disabled")

        # ==========================================
        # RODAPÉ: Barra de Progresso
        # ==========================================
        self.frame_rodape = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_rodape.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky="ew")
        self.frame_rodape.grid_columnconfigure(0, weight=1) 

        self.lbl_status = ctk.CTkLabel(self.frame_rodape, text="Aguardando arquivos...", text_color="gray")
        self.lbl_status.grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.progressbar = ctk.CTkProgressBar(self.frame_rodape)
        self.progressbar.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(5, 0))
        self.progressbar.set(0)

        self.btn_cancelar = ctk.CTkButton(self.frame_rodape, text="❌ Cancelar", fg_color="#dc2626", hover_color="#991b1b", font=ctk.CTkFont(weight="bold"), width=100, command=comando_cancelar)
        self.btn_cancelar.grid(row=0, column=1, rowspan=2, padx=(10, 10), sticky="e")
        self.btn_cancelar.grid_remove()

        self.btn_converter = ctk.CTkButton(self.frame_rodape, text="CONVERTER PDF A MD", font=ctk.CTkFont(weight="bold"), height=40, state="disabled", fg_color="#16a34a", hover_color="#15803d", command=comando_converter)
        self.btn_converter.grid(row=0, column=2, rowspan=2, sticky="e")

    # ==========================================
    # LÓGICA DO SCANNER ANIMADO (FOCO INDIVIDUAL)
    # ==========================================
    def iniciar_scanner(self, imagem_grande, texto_nome):
        # Oculta a galeria e mostra o palco do scanner
        self.frame_galeria.grid_remove()
        self.frame_scanner.grid()
        self.lbl_img_scanner.configure(image=imagem_grande)
        self.lbl_nome_scanner.configure(text=f"⏳ Escaneando: {texto_nome}")

        self.animando = True
        self.pos_y = 0.02
        self.direcao = 1
        self.linha_scanner.place(relx=0.02, rely=0.02, relwidth=0.96)
        self.linha_scanner.lift()
        self.animar_scanner()

    def atualizar_imagem_scanner(self, imagem_grande, texto_nome):
        """Muda a folha central quando o OCR avança para o próximo PDF"""
        self.lbl_img_scanner.configure(image=imagem_grande)
        self.lbl_nome_scanner.configure(text=f"⏳ Escaneando: {texto_nome}")

    def parar_scanner(self):
        self.animando = False
        self.linha_scanner.place_forget()
        self.frame_scanner.grid_remove()
        self.frame_galeria.grid()

    def animar_scanner(self):
        if not self.animando: return
        
        self.pos_y += 0.02 * self.direcao
        if self.pos_y >= 0.98: self.direcao = -1
        elif self.pos_y <= 0.02: self.direcao = 1
            
        self.linha_scanner.place(rely=self.pos_y)
        self.linha_scanner.lift() 
        self.after(30, self.animar_scanner) 


# --- (Restante das telas: Projetos, Detalhes e Configs ficam inalteradas) ---
class TelaProjetos(ctk.CTkFrame):
    def __init__(self, master, comando_abrir_detalhes):
        super().__init__(master, fg_color="transparent")
        self.comando_abrir_detalhes = comando_abrir_detalhes
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.lbl_proj_titulo = ctk.CTkLabel(self, text="Meus Projetos (Histórico)", font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_proj_titulo.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        self.scroll_projetos = ctk.CTkScrollableFrame(self, fg_color="#2b2b2b")
        self.scroll_projetos.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")

    def carregar_lista(self):
        for widget in self.scroll_projetos.winfo_children(): widget.destroy()
        from core.historico import historico_app
        projetos = historico_app.obter_todos()
        if not projetos:
            ctk.CTkLabel(self.scroll_projetos, text="Nenhum projeto convertido ainda.", text_color="gray").pack(pady=20)
            return
        for proj in projetos:
            card = ctk.CTkFrame(self.scroll_projetos, fg_color="#333333", corner_radius=8)
            card.pack(fill="x", padx=10, pady=5)
            card.grid_columnconfigure(0, weight=1)
            
            data_proj = proj.get("data", "") if isinstance(proj, dict) else proj[2]
            origem = proj.get("pdf_original", "") if isinstance(proj, dict) else proj[1]
            destino = proj.get("md_gerado", "") if isinstance(proj, dict) else proj[3]
            
            frame_texto = ctk.CTkFrame(card, fg_color="transparent")
            frame_texto.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
            ctk.CTkLabel(frame_texto, text=data_proj, font=ctk.CTkFont(size=10, weight="bold"), text_color="#3b82f6").pack(anchor="w", pady=(0, 2))
            ctk.CTkLabel(frame_texto, text=f"De: {origem}", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(frame_texto, text=f"Para: {destino}", text_color="gray", font=ctk.CTkFont(size=11)).pack(anchor="w")
            
            btn_abrir = ctk.CTkButton(card, text="Abrir / Ver", width=100, fg_color="#3b82f6", hover_color="#2563eb", command=lambda p=proj: self.comando_abrir_detalhes(p))
            btn_abrir.grid(row=0, column=1, padx=10, pady=10)

class TelaDetalhes(ctk.CTkFrame):
    def __init__(self, master, comando_voltar, comando_copiar, comando_salvar):
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.header_detalhes = ctk.CTkFrame(self, fg_color="transparent")
        self.header_detalhes.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        self.btn_voltar = ctk.CTkButton(self.header_detalhes, text="⬅ Voltar", width=80, fg_color="#3f3f46", hover_color="#52525b", command=comando_voltar)
        self.btn_voltar.pack(side="left")
        self.lbl_nome_projeto = ctk.CTkLabel(self.header_detalhes, text="Visualizando...", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_nome_projeto.pack(side="left", padx=20)
        self.textbox_detalhes = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12))
        self.textbox_detalhes.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="nsew")
        self.footer_detalhes = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_detalhes.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        self.btn_copiar = ctk.CTkButton(self.footer_detalhes, text="📋 Copiar Tudo", font=ctk.CTkFont(weight="bold"), fg_color="#3b82f6", hover_color="#2563eb", command=comando_copiar)
        self.btn_copiar.pack(side="left", padx=(0, 10))
        self.btn_salvar_novo = ctk.CTkButton(self.footer_detalhes, text="💾 Salvar Como...", fg_color="#3f3f46", hover_color="#52525b", font=ctk.CTkFont(weight="bold"), command=comando_salvar)
        self.btn_salvar_novo.pack(side="left")
        
    def carregar_texto(self, titulo, texto):
        self.lbl_nome_projeto.configure(text=f"Visualizando: {titulo}")
        self.textbox_detalhes.configure(state="normal")
        self.textbox_detalhes.delete("0.0", "end")
        self.textbox_detalhes.insert("0.0", texto)
        self.textbox_detalhes.configure(state="disabled")

class TelaConfigs(ctk.CTkFrame):
    def __init__(self, master, comando_mudar_tema, comando_limpar_historico):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="Configurações do Sistema", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        frame_aparencia = ctk.CTkFrame(self)
        frame_aparencia.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkLabel(frame_aparencia, text="🎨 Aparência", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        ctk.CTkLabel(frame_aparencia, text="Tema do Aplicativo:").grid(row=1, column=0, padx=15, pady=(5, 15), sticky="w")
        self.opt_tema = ctk.CTkOptionMenu(frame_aparencia, values=["Dark", "Light", "System"], command=comando_mudar_tema)
        self.opt_tema.grid(row=1, column=1, padx=15, pady=(5, 15), sticky="e")
        from core.configuracao import config_app
        self.opt_tema.set(config_app.get("tema") or "Dark") 
        frame_dados = ctk.CTkFrame(self)
        frame_dados.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkLabel(frame_dados, text="🧹 Dados do Aplicativo", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        ctk.CTkLabel(frame_dados, text="Isso apagará o histórico de 'Meus Projetos', mas NÃO excluirá seus arquivos reais.", text_color="gray").grid(row=1, column=0, padx=15, pady=(0, 10), sticky="w")
        btn_limpar = ctk.CTkButton(frame_dados, text="Apagar Todo o Histórico", fg_color="#b91c1c", hover_color="#991b1b", font=ctk.CTkFont(weight="bold"), command=comando_limpar_historico)
        btn_limpar.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="w")