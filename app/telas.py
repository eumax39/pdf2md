import customtkinter as ctk
from tkinterdnd2 import DND_FILES
import fitz
from PIL import Image
import pathlib

from core.configuracao import config_app

MODO_HIBRIDO = "Híbrido (Texto Nativo + OCR em Imagem Relevante)"
MODO_HIBRIDO_ANTIGO = "Híbrido (Automático)"
MODO_FORCAR_OCR = "Forçar OCR (Ignora Texto Nativo)"
MODO_FORCAR_OCR_ANTIGO = "Forçar OCR em Todas as Páginas"
MODO_REFERENCIA_IMAGEM = "Texto Nativo + Referência de Imagem (Sem OCR)"
FORMATO_MD = "Markdown (.md)"
FORMATO_PDF_OCR = "PDF com OCR (.pdf)"


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
        self.frame_scanner.grid_remove()

        self.folha_scanner = ctk.CTkFrame(self.frame_scanner, fg_color="white", corner_radius=0, border_width=1, border_color="#555555")
        self.folha_scanner.grid(row=0, column=0, pady=(20, 5))
        self.lbl_img_scanner = ctk.CTkLabel(self.folha_scanner, text="")
        self.lbl_img_scanner.pack(padx=5, pady=5)
        self.lbl_nome_scanner = ctk.CTkLabel(self.frame_scanner, text="", text_color="#a1a1aa", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_nome_scanner.grid(row=1, column=0, pady=(0, 20))

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
            values=[MODO_HIBRIDO, MODO_FORCAR_OCR, MODO_REFERENCIA_IMAGEM],
            command=self._ao_mudar_modo,
        )
        self.opt_modo.grid(row=1, column=1, padx=20, pady=5, sticky="e")
        self.opt_modo.set(normalizar_modo_conversao(config_app.get("modo_conversao")))

        self.lbl_formato = ctk.CTkLabel(self.frame_opcoes, text="Formato de Saída:")
        self.lbl_formato.grid(row=2, column=0, padx=20, pady=5, sticky="w")
        self.opt_formato_saida = ctk.CTkOptionMenu(
            self.frame_opcoes,
            values=[FORMATO_MD, FORMATO_PDF_OCR],
        )
        self.opt_formato_saida.grid(row=2, column=1, padx=20, pady=5, sticky="e")
        self.opt_formato_saida.set(FORMATO_MD)
        self._atualizar_opcao_formato_saida(normalizar_modo_conversao(config_app.get("modo_conversao")))

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
        # PRÉ-VISUALIZAÇÃO LADO A LADO (REFINADA)
        # ==========================================
        self.frame_preview_lado = ctk.CTkFrame(self, fg_color="#1a1a1c", corner_radius=10)
        self.frame_preview_lado.grid(row=1, column=1, padx=(10, 0), pady=(10, 10), sticky="nsew")
        self.frame_preview_lado.grid_columnconfigure(0, weight=1)
        self.frame_preview_lado.grid_rowconfigure(0, weight=0)  # título
        self.frame_preview_lado.grid_rowconfigure(1, weight=4)  # imagem
        self.frame_preview_lado.grid_rowconfigure(2, weight=1)  # texto
        self.frame_preview_lado.grid_rowconfigure(3, weight=0)  # navegação
        self.frame_preview_lado.grid_remove()

        # Título do preview (nome do arquivo)
        self.lbl_preview_titulo = ctk.CTkLabel(
            self.frame_preview_lado,
            text="Pré-visualização",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#a1a1aa",
            anchor="w"
        )
        self.lbl_preview_titulo.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="ew")

        # Imagem da página (sem cortes)
        self.lbl_preview_img = ctk.CTkLabel(
            self.frame_preview_lado,
            text="Nenhum PDF selecionado",
            font=ctk.CTkFont(size=14),
            anchor="center"
        )
        self.lbl_preview_img.grid(row=1, column=0, padx=15, pady=(0, 5), sticky="nsew")

        # Texto nativo (com borda suave)
        self.txt_preview_texto = ctk.CTkTextbox(
            self.frame_preview_lado,
            font=ctk.CTkFont(family="Consolas", size=11),
            border_width=1,
            border_color="#3f3f46"
        )
        self.txt_preview_texto.grid(row=2, column=0, padx=15, pady=5, sticky="nsew")
        self.txt_preview_texto.insert("0.0", "Selecione um PDF para visualizar o texto nativo.")
        self.txt_preview_texto.configure(state="disabled")

        # Controles de navegação (com estilo mais clean)
        self.frame_nav = ctk.CTkFrame(self.frame_preview_lado, fg_color="transparent")
        self.frame_nav.grid(row=3, column=0, padx=15, pady=(5, 15), sticky="ew")
        self.frame_nav.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Botões criados COM command direto e depois configurados
        self.btn_prev = ctk.CTkButton(
            self.frame_nav, text="◄", width=35, height=30,
            fg_color="#3f3f46", hover_color="#52525b", state="disabled",
            command=self.pagina_anterior  # command direto
        )
        self.btn_prev.grid(row=0, column=0, padx=3)

        self.lbl_pagina = ctk.CTkLabel(
            self.frame_nav, text="Página 0 de 0",
            font=ctk.CTkFont(size=12), text_color="#a1a1aa"
        )
        self.lbl_pagina.grid(row=0, column=1, padx=10)

        self.btn_next = ctk.CTkButton(
            self.frame_nav, text="►", width=35, height=30,
            fg_color="#3f3f46", hover_color="#52525b", state="disabled",
            command=self.proxima_pagina  # command direto
        )
        self.btn_next.grid(row=0, column=2, padx=3)

        self.btn_abrir_externo = ctk.CTkButton(
            self.frame_nav, text="🔍 Abrir", width=60, height=30,
            fg_color="#3f3f46", hover_color="#52525b", state="disabled",
            command=self._abrir_pdf_externo  # command direto
        )
        self.btn_abrir_externo.grid(row=0, column=3, padx=3)

        # Atributos de estado
        self.doc_preview = None
        self.caminho_pdf_atual = None
        self.pagina_atual = 0
        self.total_paginas = 0

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
    # LÓGICA DO SCANNER
    # ==========================================
    def iniciar_scanner(self, imagem_grande, texto_nome):
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

    def _ao_mudar_modo(self, valor):
        self._atualizar_opcao_formato_saida(normalizar_modo_conversao(valor))

    def _atualizar_opcao_formato_saida(self, modo_atual):
        habilitar_formato = (modo_atual == MODO_FORCAR_OCR)
        if habilitar_formato:
            self.lbl_formato.grid()
            self.opt_formato_saida.grid()
        else:
            self.opt_formato_saida.set(FORMATO_MD)
            self.lbl_formato.grid_remove()
            self.opt_formato_saida.grid_remove()

    def atualizar_imagem_scanner(self, imagem_grande, texto_nome):
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

    # ==========================================
    # PRÉ-VISUALIZAÇÃO LADO A LADO (REFINADA)
    # ==========================================
    def carregar_preview(self, caminho_pdf):
        """Carrega um PDF e exibe a primeira página."""
        if self.doc_preview:
            try:
                self.doc_preview.close()
            except:
                pass
            self.doc_preview = None

        self.caminho_pdf_atual = caminho_pdf
        try:
            self.doc_preview = fitz.open(caminho_pdf)
            self.total_paginas = len(self.doc_preview)
            self.pagina_atual = 0
            self.frame_preview_lado.grid()
            # Atualiza título com o nome do arquivo
            nome_arquivo = pathlib.Path(caminho_pdf).name
            self.lbl_preview_titulo.configure(text=f"📄 Pré-visualização: {nome_arquivo}")
            self._atualizar_preview()
            # Habilita os botões conforme a página
            self.btn_prev.configure(state="normal" if self.pagina_atual > 0 else "disabled")
            self.btn_next.configure(state="normal" if self.pagina_atual < self.total_paginas - 1 else "disabled")
            self.btn_abrir_externo.configure(state="normal")
            print(f"[Preview] Carregado: {nome_arquivo}, total páginas: {self.total_paginas}")
        except Exception as e:
            print(f"Erro ao carregar preview: {e}")

    def _atualizar_preview(self):
        """Atualiza a imagem e o texto da página atual."""
        if not self.doc_preview:
            print(">>> _atualizar_preview: doc_preview é None")
            return
        try:
            pagina = self.doc_preview.load_page(self.pagina_atual)
        except Exception as e:
            print(f"Erro ao carregar página {self.pagina_atual}: {e}")
            return

        # Atualiza imagem
        try:
            pix = pagina.get_pixmap(dpi=100)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            max_w, max_h = 380, 400
            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.lbl_preview_img.configure(image=ctk_img, text="")
        except Exception as e:
            self.lbl_preview_img.configure(text="Erro ao renderizar página", image=None)
            print(f"Erro ao renderizar imagem: {e}")

        # Atualiza texto
        try:
            texto = pagina.get_text("text") or "Nenhum texto nativo encontrado."
            self.txt_preview_texto.configure(state="normal")
            self.txt_preview_texto.delete("0.0", "end")
            self.txt_preview_texto.insert("0.0", texto)
            self.txt_preview_texto.configure(state="disabled")
        except Exception as e:
            print(f"Erro ao extrair texto: {e}")

        self.lbl_pagina.configure(text=f"Página {self.pagina_atual+1} de {self.total_paginas}")
        # Garante que os botões estejam no estado correto
        self.btn_prev.configure(state="normal" if self.pagina_atual > 0 else "disabled")
        self.btn_next.configure(state="normal" if self.pagina_atual < self.total_paginas - 1 else "disabled")
        print(f"[Preview] Atualizado: página {self.pagina_atual+1} de {self.total_paginas}")

    def pagina_anterior(self):
        print(">>> pagina_anterior chamado")
        if self.pagina_atual > 0:
            self.pagina_atual -= 1
            self._atualizar_preview()
        else:
            print(">>> pagina_anterior: já está na primeira página")

    def proxima_pagina(self):
        print(">>> proxima_pagina chamado")
        if self.pagina_atual < self.total_paginas - 1:
            self.pagina_atual += 1
            self._atualizar_preview()
        else:
            print(">>> proxima_pagina: já está na última página")

    def limpar_preview(self):
        if self.doc_preview:
            try:
                self.doc_preview.close()
            except:
                pass
            self.doc_preview = None
        self.caminho_pdf_atual = None
        self.frame_preview_lado.grid_remove()
        self.lbl_preview_titulo.configure(text="Pré-visualização")
        self.lbl_preview_img.configure(text="Nenhum PDF selecionado", image=None)
        self.txt_preview_texto.configure(state="normal")
        self.txt_preview_texto.delete("0.0", "end")
        self.txt_preview_texto.insert("0.0", "Selecione um PDF para visualizar o texto nativo.")
        self.txt_preview_texto.configure(state="disabled")
        self.lbl_pagina.configure(text="Página 0 de 0")
        self.btn_prev.configure(state="disabled")
        self.btn_next.configure(state="disabled")
        self.btn_abrir_externo.configure(state="disabled")

    def _abrir_pdf_externo(self):
        if self.caminho_pdf_atual:
            import os
            try:
                os.startfile(self.caminho_pdf_atual)
                print(f"[Abrir] Abrindo {self.caminho_pdf_atual}")
            except Exception as e:
                print(f"Erro ao abrir PDF: {e}")

    def selecionar_pdf_para_preview(self, caminho_pdf):
        """Método público para trocar o preview de PDF (chamado ao clicar na miniatura)."""
        self.carregar_preview(caminho_pdf)


# --- As classes TelaProjetos, TelaDetalhes e TelaConfigs permanecem inalteradas ---
# (mantenha exatamente como você já tem)
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