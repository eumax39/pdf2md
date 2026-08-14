import customtkinter as ctk
import tkinter as tk
from tkinterdnd2 import DND_FILES
import fitz
from PIL import Image, ImageTk
import pathlib

from core.configuracao import config_app
from core.utils import get_resource_path

MODO_HIBRIDO = "Híbrido (Texto Nativo + OCR em Imagem Relevante)"
MODO_HIBRIDO_ANTIGO = "Híbrido (Automático)"
MODO_FORCAR_OCR = "Forçar OCR (Ignora Texto Nativo)"
MODO_FORCAR_OCR_ANTIGO = "Forçar OCR em Todas as Páginas"
MODO_REFERENCIA_IMAGEM = "Texto Nativo + Referência de Imagem (Sem OCR)"
FORMATO_MD = "Markdown (.md)"
FORMATO_PDF_OCR = "PDF com OCR (.pdf)"

BG = "#0b1118"
PANEL = "#111923"
PANEL_2 = "#151e29"
CARD = "#101822"
BORDER = "#263444"
MUTED = "#8d99a8"
TEXT = "#eef3f8"
BLUE = "#2088ff"
BLUE_HOVER = "#0f73e6"
GREEN = "#0aa86b"
GREEN_HOVER = "#078856"
RED = "#ef4444"


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
    """Tela principal com preview integrado ao bloco do scanner e MD separado."""

    def __init__(self, master, comando_selecionar_pdf, comando_soltar_pdf, comando_pasta,
                 comando_converter, comando_cancelar, comando_importar_pasta):
        super().__init__(master, fg_color="transparent")

        self.modo_visualizacao = False
        self._scanner_ctk_image = None
        self._preview_ctk_image = None
        self._preview_pil_image = None
        # O preview usa PhotoImage nativo do Tk em um Canvas dedicado.
        # Isso evita o estado preto observado ao reutilizar CTkImage/CTkLabel
        # após voltar à galeria e abrir outro PDF.
        self._preview_photo_image = None
        self._preview_canvas_item = None
        self._preview_render_job = None
        self._preview_generation = 0
        self._ui_icons = {}
        self.doc_preview = None
        self.caminho_pdf_atual = None
        self.pagina_atual = 0
        self.total_paginas = 0
        self.animando = False
        self.pos_y = 0.02
        self.direcao = 1

        self.grid_columnconfigure(0, weight=10, uniform="main")
        self.grid_columnconfigure(1, weight=11, uniform="main")
        self.grid_rowconfigure(1, weight=1)

        # ==============================
        # ESQUERDA: seleção / scanner
        # ==============================
        self.frame_upload = ctk.CTkFrame(
            self, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER
        )
        self.frame_upload.grid(row=0, column=0, rowspan=2, padx=(0, 8), pady=(0, 8), sticky="nsew")
        self.frame_upload.grid_columnconfigure(0, weight=1)
        self.frame_upload.grid_rowconfigure(1, weight=1)

        self.lbl_upload_titulo = ctk.CTkLabel(
            self.frame_upload, text="Conversor de Processos PDF para Markdown",
            font=ctk.CTkFont(size=17, weight="bold"), text_color=TEXT
        )
        self.lbl_upload_titulo.grid(row=0, column=0, padx=18, pady=(18, 10), sticky="w")

        # Galeria: 4 colunas compactas, sem linhas expansíveis que criem vazios.
        self.frame_galeria = ctk.CTkFrame(
            self.frame_upload, fg_color="#0d141d", corner_radius=10,
            border_width=1, border_color=BORDER
        )
        self.frame_galeria.grid(row=1, column=0, padx=18, pady=4, sticky="nsew")
        for c in range(4):
            self.frame_galeria.grid_columnconfigure(c, weight=1, uniform="gallery")
        self._drop_area = None

        # Preview e scanner usam EXATAMENTE o mesmo bloco, dentro da coluna esquerda.
        self.frame_scanner = ctk.CTkFrame(
            self.frame_upload, fg_color="#0d141d", corner_radius=10,
            border_width=1, border_color=BORDER
        )
        self.frame_scanner.grid(row=1, column=0, padx=18, pady=4, sticky="nsew")
        self.frame_scanner.grid_columnconfigure(0, weight=1)
        self.frame_scanner.grid_rowconfigure(1, weight=1)
        self.frame_scanner.grid_remove()

        self.frame_scanner_top = ctk.CTkFrame(self.frame_scanner, fg_color="transparent")
        self.frame_scanner_top.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        self.frame_scanner_top.grid_columnconfigure(1, weight=1)

        self.btn_voltar_preview = ctk.CTkButton(
            self.frame_scanner_top, text="Voltar", image=self._icone("back.png", (16, 16)),
            compound="left", width=82, height=30, fg_color=PANEL_2, hover_color="#1d2a39",
            border_width=1, border_color=BORDER, command=self.voltar_para_selecao
        )
        self.btn_voltar_preview.grid(row=0, column=0, sticky="w")
        self.lbl_preview_scanner = ctk.CTkLabel(
            self.frame_scanner_top, text="Pré-visualização do PDF",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT, anchor="w"
        )
        self.lbl_preview_scanner.grid(row=0, column=1, padx=10, sticky="w")
        self.btn_abrir_externo = ctk.CTkButton(
            self.frame_scanner_top, text="Abrir Original", image=self._icone("open.png", (16, 16)),
            compound="left", width=122, height=30, fg_color=PANEL_2, hover_color="#1d2a39",
            border_width=1, border_color=BORDER, command=self._abrir_pdf_externo_compat
        )
        self.btn_abrir_externo.grid(row=0, column=2, sticky="e")

        # Fundo escuro: elimina o retângulo branco ao selecionar.
        # O branco visível vem apenas da própria página renderizada.
        self.folha_scanner = ctk.CTkFrame(
            self.frame_scanner, fg_color="#0a1017", corner_radius=8,
            border_width=1, border_color="#1e2a38"
        )
        self.folha_scanner.grid(row=1, column=0, padx=12, pady=4, sticky="nsew")
        self.folha_scanner.grid_rowconfigure(0, weight=1)
        self.folha_scanner.grid_columnconfigure(0, weight=1)
        # Canvas exclusivo do preview. O Tk PhotoImage é mais previsível para
        # troca repetida de documentos do que CTkImage em um mesmo label.
        self.canvas_preview = tk.Canvas(
            self.folha_scanner, bg="#0a1017", highlightthickness=0, bd=0, relief="flat"
        )
        self.canvas_preview.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # O label continua existindo apenas para o scanner de conversão.
        self.lbl_img_scanner = ctk.CTkLabel(
            self.folha_scanner, text="", fg_color="transparent", anchor="center"
        )
        self.lbl_img_scanner.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.lbl_img_scanner.grid_remove()

        self.frame_scanner_bottom = ctk.CTkFrame(self.frame_scanner, fg_color="transparent")
        self.frame_scanner_bottom.grid(row=2, column=0, padx=12, pady=(4, 10), sticky="ew")
        self.frame_scanner_bottom.grid_columnconfigure(1, weight=1)
        self.btn_prev_scanner = ctk.CTkButton(
            self.frame_scanner_bottom, text="‹", width=34, height=28,
            fg_color=PANEL_2, hover_color="#1d2a39", state="disabled",
            command=self.pagina_scanner_anterior
        )
        self.btn_prev_scanner.grid(row=0, column=0, sticky="w")
        self.lbl_nome_scanner = ctk.CTkLabel(
            self.frame_scanner_bottom, text="", text_color=MUTED,
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.lbl_nome_scanner.grid(row=0, column=1, padx=10)
        self.btn_next_scanner = ctk.CTkButton(
            self.frame_scanner_bottom, text="›", width=34, height=28,
            fg_color=PANEL_2, hover_color="#1d2a39", state="disabled",
            command=self.pagina_scanner_proxima
        )
        self.btn_next_scanner.grid(row=0, column=2, sticky="e")

        self.linha_scanner = ctk.CTkFrame(self.folha_scanner, height=3, fg_color=BLUE, corner_radius=2)

        # Botões inferiores com ícones azuis reais (PNG), não glifos/emoji do Windows.
        self.frame_botoes_upload = ctk.CTkFrame(self.frame_upload, fg_color="transparent")
        self.frame_botoes_upload.grid(row=2, column=0, padx=18, pady=(10, 5), sticky="ew")
        self.frame_botoes_upload.grid_columnconfigure((0, 1), weight=1)
        self.btn_arquivos = ctk.CTkButton(
            self.frame_botoes_upload, text="Adicionar Arquivos", image=self._icone("add.png", (18, 18)),
            compound="left", height=38, fg_color=PANEL_2, hover_color="#1d2a39",
            border_width=1, border_color=BORDER, command=comando_selecionar_pdf
        )
        self.btn_arquivos.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self.btn_pasta = ctk.CTkButton(
            self.frame_botoes_upload, text="Importar Pasta", image=self._icone("folder.png", (18, 18)),
            compound="left", height=38, fg_color=PANEL_2, hover_color="#1d2a39",
            border_width=1, border_color=BORDER, command=comando_importar_pasta
        )
        self.btn_pasta.grid(row=0, column=1, padx=(5, 0), sticky="ew")
        self.lbl_arquivo_selecionado = ctk.CTkLabel(
            self.frame_upload, text="Total: 0 arquivo(s) na fila de conversão",
            text_color=MUTED, font=ctk.CTkFont(size=12)
        )
        self.lbl_arquivo_selecionado.grid(row=3, column=0, padx=18, pady=(0, 14), sticky="w")

        # ==============================
        # DIREITA: parâmetros + MD
        # ==============================
        self.frame_opcoes = ctk.CTkFrame(
            self, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER
        )
        self.frame_opcoes.grid(row=0, column=1, padx=(8, 0), pady=(0, 8), sticky="nsew")
        self.frame_opcoes.grid_columnconfigure(1, weight=1)
        self.lbl_opcoes_titulo = ctk.CTkLabel(
            self.frame_opcoes, text="Parâmetros de Leitura",
            font=ctk.CTkFont(size=17, weight="bold"), text_color=TEXT
        )
        self.lbl_opcoes_titulo.grid(row=0, column=0, columnspan=2, padx=18, pady=(16, 6), sticky="w")
        self.lbl_modo = ctk.CTkLabel(self.frame_opcoes, text="Modo de Processamento:", text_color=TEXT)
        self.lbl_modo.grid(row=1, column=0, padx=18, pady=5, sticky="w")
        self.opt_modo = ctk.CTkOptionMenu(
            self.frame_opcoes, values=[MODO_HIBRIDO, MODO_FORCAR_OCR, MODO_REFERENCIA_IMAGEM],
            command=self._ao_mudar_modo, width=310, height=34,
            fg_color="#0878d9", button_color="#0866b7", button_hover_color="#075da7"
        )
        self.opt_modo.grid(row=1, column=1, padx=18, pady=5, sticky="e")
        self.opt_modo.set(normalizar_modo_conversao(config_app.get("modo_conversao")))
        self.lbl_formato = ctk.CTkLabel(self.frame_opcoes, text="Formato de Saída:", text_color=TEXT)
        self.lbl_formato.grid(row=2, column=0, padx=18, pady=5, sticky="w")
        self.opt_formato_saida = ctk.CTkOptionMenu(
            self.frame_opcoes, values=[FORMATO_MD, FORMATO_PDF_OCR], width=190, height=34,
            fg_color="#0878d9", button_color="#0866b7", button_hover_color="#075da7"
        )
        self.opt_formato_saida.grid(row=2, column=1, padx=18, pady=5, sticky="e")
        self.opt_formato_saida.set(FORMATO_MD)
        self._atualizar_opcao_formato_saida(normalizar_modo_conversao(config_app.get("modo_conversao")))
        self.btn_destino = ctk.CTkButton(
            self.frame_opcoes, text="Escolher Pasta Destino", height=34,
            fg_color=PANEL_2, hover_color="#1d2a39", border_width=1, border_color=BORDER,
            command=comando_pasta
        )
        self.btn_destino.grid(row=3, column=0, columnspan=2, padx=18, pady=(8, 0), sticky="ew")
        self.lbl_caminho_destino = ctk.CTkLabel(
            self.frame_opcoes, text="Padrão: Mesma pasta do PDF", text_color=MUTED,
            font=ctk.CTkFont(size=11)
        )
        self.lbl_caminho_destino.grid(row=4, column=0, columnspan=2, padx=18, pady=(2, 12), sticky="w")

        # MD fica sozinho no bloco direito, como na versão anterior.
        self.frame_preview = ctk.CTkFrame(
            self, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER
        )
        self.frame_preview.grid(row=1, column=1, padx=(8, 0), pady=(8, 8), sticky="nsew")
        self.frame_preview.grid_columnconfigure(0, weight=1)
        self.frame_preview.grid_rowconfigure(1, weight=1)

        self.frame_md_header = ctk.CTkFrame(self.frame_preview, fg_color="transparent")
        self.frame_md_header.grid(row=0, column=0, padx=12, pady=(10, 2), sticky="ew")
        self._md_icon = self._icone("pdf.png", (17, 17))
        ctk.CTkLabel(
            self.frame_md_header, text="Texto capturado / Markdown", image=self._md_icon,
            compound="left", text_color=TEXT, font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left")

        self.textbox_preview = ctk.CTkTextbox(
            self.frame_preview, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0a0f15", border_width=1, border_color=BORDER,
            text_color="#dce6ef", corner_radius=8
        )
        self.textbox_preview.grid(row=1, column=0, padx=10, pady=(4, 10), sticky="nsew")
        self.textbox_preview.insert("0.0", "O texto capturado aparecerá aqui durante a conversão...")
        self.textbox_preview.configure(state="disabled")

        # Compatibilidade com referências antigas.
        self.frame_preview_lado = self.frame_preview
        self.lbl_preview_img = self.lbl_img_scanner
        self.txt_preview_texto = self.textbox_preview
        self.btn_prev = self.btn_prev_scanner
        self.btn_next = self.btn_next_scanner
        self.lbl_pagina = self.lbl_nome_scanner
        self.frame_preview_stage = self.folha_scanner

        # ==============================
        # Rodapé
        # ==============================
        self.frame_rodape = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_rodape.grid(row=2, column=0, columnspan=2, pady=(2, 0), sticky="ew")
        self.frame_rodape.grid_columnconfigure(0, weight=1)
        self.lbl_status = ctk.CTkLabel(self.frame_rodape, text="Pronto para iniciar.", text_color=MUTED)
        self.lbl_status.grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.progressbar = ctk.CTkProgressBar(
            self.frame_rodape, height=6, progress_color=BLUE, fg_color="#1c2733"
        )
        self.progressbar.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(5, 0))
        self.progressbar.set(0)
        self.btn_cancelar = ctk.CTkButton(
            self.frame_rodape, text="Cancelar", fg_color="#b91c1c", hover_color="#991b1b",
            width=105, height=38, command=comando_cancelar
        )
        self.btn_cancelar.grid(row=0, column=1, rowspan=2, padx=(8, 8), sticky="e")
        self.btn_cancelar.grid_remove()
        self.btn_converter = ctk.CTkButton(
            self.frame_rodape, text="CONVERTER PDF A MD",
            font=ctk.CTkFont(weight="bold"), height=40, width=190,
            state="disabled", fg_color=GREEN, hover_color=GREEN_HOVER,
            command=comando_converter
        )
        self.btn_converter.grid(row=0, column=2, rowspan=2, sticky="e")

        self.canvas_preview.bind("<Configure>", lambda e: self._agendar_render_preview(90) if self.modo_visualizacao else None)

    def _icone(self, nome, size):
        chave = (nome, size)
        if chave in self._ui_icons:
            return self._ui_icons[chave]
        try:
            img = Image.open(get_resource_path("assets", "ui", nome)).convert("RGBA")
            icon = ctk.CTkImage(light_image=img, dark_image=img, size=size)
            self._ui_icons[chave] = icon
            return icon
        except Exception:
            return None

    def _ao_mudar_modo(self, modo):
        modo = normalizar_modo_conversao(modo)
        try:
            config_app.set("modo_conversao", modo)
        except Exception:
            pass
        self._atualizar_opcao_formato_saida(modo)

    def _atualizar_opcao_formato_saida(self, modo):
        if modo == MODO_REFERENCIA_IMAGEM:
            self.opt_formato_saida.set(FORMATO_MD)
            self.opt_formato_saida.configure(state="disabled")
        else:
            self.opt_formato_saida.configure(state="normal")

    def _abrir_pdf_externo_compat(self):
        if not self.caminho_pdf_atual:
            return
        try:
            import os
            os.startfile(self.caminho_pdf_atual)
        except Exception:
            pass

    def _recriar_label_scanner(self, exibir=False):
        """Recria o label do scanner caso o objeto Tk de imagem tenha ficado inválido."""
        try:
            self.lbl_img_scanner.destroy()
        except Exception:
            pass
        self.lbl_img_scanner = ctk.CTkLabel(
            self.folha_scanner, text="", fg_color="transparent", anchor="center"
        )
        self.lbl_preview_img = self.lbl_img_scanner
        if exibir:
            self.lbl_img_scanner.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        else:
            self.lbl_img_scanner.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
            self.lbl_img_scanner.grid_remove()

    def _definir_imagem_scanner(self, imagem_grande):
        """Anexa uma nova CTkImage mantendo referência forte antes de tocar no Tk."""
        self._scanner_ctk_image = imagem_grande
        try:
            self.lbl_img_scanner.configure(image=imagem_grande, text="")
        except tk.TclError:
            # Se o Tcl perdeu o pyimage anterior, recriamos somente o label visual.
            self._recriar_label_scanner(exibir=True)
            self.lbl_img_scanner.configure(image=imagem_grande, text="")

    def _limpar_imagem_scanner(self, ocultar=True):
        """Desanexa a imagem antes de liberar a referência Python.

        Essa ordem é importante: liberar CTkImage primeiro pode destruir o pyimage
        enquanto o label Tcl ainda aponta para ele, gerando 'image pyimageX doesn't exist'.
        """
        imagem_anterior = self._scanner_ctk_image
        try:
            self.lbl_img_scanner.configure(image=None, text="")
        except tk.TclError:
            # Recuperação defensiva para labels que já ficaram com referência Tcl inválida.
            self._recriar_label_scanner(exibir=not ocultar)
        finally:
            # Mantemos imagem_anterior viva até depois do detach/recreate.
            self._scanner_ctk_image = None
            try:
                self.lbl_img_scanner._preview_image_ref = None
            except Exception:
                pass
        if ocultar:
            try:
                self.lbl_img_scanner.grid_remove()
            except Exception:
                pass

    def abrir_visualizacao_pdf(self, caminho_pdf):
        """Troca apenas a galeria pelo preview; o bloco MD permanece independente."""
        self.modo_visualizacao = True
        self.animando = False
        self.linha_scanner.place_forget()
        self.frame_galeria.grid_remove()
        self.frame_scanner.grid()
        self.lbl_img_scanner.grid_remove()
        self.canvas_preview.grid()
        self.btn_voltar_preview.grid()
        self.btn_abrir_externo.grid()
        self.lbl_preview_scanner.configure(text="Pré-visualização do PDF")
        self._abrir_doc_visualizacao(caminho_pdf)

    def _cancelar_render_preview(self):
        if self._preview_render_job is not None:
            try:
                self.after_cancel(self._preview_render_job)
            except Exception:
                pass
            self._preview_render_job = None

    def _agendar_render_preview(self, atraso=60):
        """Debounce do preview para evitar renderizações antigas sobre o novo PDF."""
        if not self.modo_visualizacao or not self.caminho_pdf_atual:
            return
        self._cancelar_render_preview()
        geracao = self._preview_generation
        self._preview_render_job = self.after(
            atraso, lambda g=geracao: self._renderizar_pagina_scanner(g)
        )

    def _fechar_doc_preview(self):
        if self.doc_preview is not None:
            try:
                self.doc_preview.close()
            except Exception:
                pass
        self.doc_preview = None

    def _abrir_doc_visualizacao(self, caminho_pdf):
        """Prepara um novo PDF para preview em estado totalmente limpo.

        O documento não fica aberto entre trocas. Mantemos somente caminho,
        página e contagem. Cada render abre o arquivo por poucos milissegundos,
        eliminando qualquer estado residual do PDF anterior.
        """
        self._cancelar_render_preview()
        self._preview_generation += 1
        self._fechar_doc_preview()
        self._preview_ctk_image = None
        self._preview_pil_image = None
        self._preview_photo_image = None
        self._preview_canvas_item = None
        self.canvas_preview.delete("all")
        self._limpar_imagem_scanner(ocultar=True)

        try:
            with fitz.open(caminho_pdf) as doc:
                total = len(doc)
            if total <= 0:
                raise RuntimeError("O PDF não possui páginas.")
            self.caminho_pdf_atual = caminho_pdf
            self.total_paginas = total
            self.pagina_atual = 0
            # Espera o grid terminar a troca galeria -> preview.
            self.after_idle(lambda g=self._preview_generation: self._agendar_render_preview(10) if g == self._preview_generation else None)
        except Exception as e:
            self.caminho_pdf_atual = None
            self.total_paginas = 0
            self.pagina_atual = 0
            self.canvas_preview.delete("all")
            self.canvas_preview.create_text(
                max(self.canvas_preview.winfo_width() // 2, 120),
                max(self.canvas_preview.winfo_height() // 2, 100),
                text=f"Erro ao abrir PDF:\n{e}", fill="#ef4444", justify="center"
            )

    @staticmethod
    def _renderizar_pagina_completa_por_caminho(caminho_pdf, indice, dpi=180):
        """Renderiza uma página em um documento recém-aberto, incluindo a MediaBox completa."""
        with fitz.open(caminho_pdf) as doc:
            if len(doc) == 0:
                return None
            indice = max(0, min(int(indice), len(doc) - 1))
            pagina = doc.load_page(indice)
            crop_original = fitz.Rect(pagina.cropbox)
            try:
                try:
                    pagina.set_cropbox(pagina.mediabox)
                except Exception:
                    pass
                pix = pagina.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
            finally:
                try:
                    pagina.set_cropbox(crop_original)
                except Exception:
                    pass
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    def _renderizar_pagina_scanner(self, geracao=None):
        """Renderiza o preview no Canvas com ImageTk.PhotoImage.

        O Canvas é limpo a cada render e a referência do PhotoImage fica presa
        à instância enquanto a página estiver visível. Isso elimina o quadro
        preto que podia surgir ao reutilizar CTkImage/CTkLabel entre PDFs.
        """
        self._preview_render_job = None
        if geracao is not None and geracao != self._preview_generation:
            return
        if not self.modo_visualizacao or not self.caminho_pdf_atual or self.total_paginas <= 0:
            return

        caminho = self.caminho_pdf_atual
        pagina_idx = self.pagina_atual

        try:
            img = self._renderizar_pagina_completa_por_caminho(caminho, pagina_idx, dpi=180)
            if img is None:
                raise RuntimeError("Não foi possível renderizar esta página.")

            # Não deixa um resultado antigo substituir o PDF/página atual.
            if geracao is not None and geracao != self._preview_generation:
                return
            if caminho != self.caminho_pdf_atual or pagina_idx != self.pagina_atual:
                return

            self.canvas_preview.update_idletasks()
            area_w = max(int(self.canvas_preview.winfo_width()), 240)
            area_h = max(int(self.canvas_preview.winfo_height()), 300)

            # Margem visual segura. Nunca amplia acima do raster original.
            max_w = max(area_w - 24, 1)
            max_h = max(area_h - 24, 1)
            escala = min(max_w / img.width, max_h / img.height, 1.0)
            alvo = (max(1, int(img.width * escala)), max(1, int(img.height * escala)))
            if alvo != img.size:
                img = img.resize(alvo, Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img)

            # Limpa integralmente o conteúdo da renderização anterior.
            self.canvas_preview.delete("all")
            cx = max(area_w // 2, 1)
            cy = max(area_h // 2, 1)
            item = self.canvas_preview.create_image(cx, cy, image=photo, anchor="center")

            self._preview_pil_image = img
            self._preview_photo_image = photo
            self._preview_canvas_item = item
            # Referência redundante no próprio widget: protege contra coleta do Tk.
            self.canvas_preview._preview_photo_ref = photo

            nome = pathlib.Path(caminho).name
            self.lbl_nome_scanner.configure(
                text=f"Página {pagina_idx + 1} de {self.total_paginas}  •  {nome}"
            )
            self.btn_prev_scanner.configure(state="normal" if pagina_idx > 0 else "disabled")
            self.btn_next_scanner.configure(
                state="normal" if pagina_idx < self.total_paginas - 1 else "disabled"
            )
        except Exception as e:
            if geracao is not None and geracao != self._preview_generation:
                return
            self._preview_pil_image = None
            self._preview_photo_image = None
            self._preview_canvas_item = None
            self.canvas_preview.delete("all")
            self.canvas_preview.create_text(
                max(self.canvas_preview.winfo_width() // 2, 120),
                max(self.canvas_preview.winfo_height() // 2, 100),
                text=f"Erro ao renderizar página:\n{e}", fill="#ef4444", justify="center"
            )

    def pagina_scanner_anterior(self):
        if self.modo_visualizacao and self.caminho_pdf_atual and self.pagina_atual > 0:
            self.pagina_atual -= 1
            self._agendar_render_preview(10)

    def pagina_scanner_proxima(self):
        if self.modo_visualizacao and self.caminho_pdf_atual and self.pagina_atual < self.total_paginas - 1:
            self.pagina_atual += 1
            self._agendar_render_preview(10)

    def pagina_anterior(self):
        self.pagina_scanner_anterior()

    def proxima_pagina(self):
        self.pagina_scanner_proxima()

    def voltar_para_selecao(self):
        self._cancelar_render_preview()
        self._preview_generation += 1
        self.modo_visualizacao = False
        self.animando = False
        self.linha_scanner.place_forget()
        self.frame_scanner.grid_remove()
        self.frame_galeria.grid()
        self._preview_ctk_image = None
        self._preview_pil_image = None
        self._preview_photo_image = None
        self._preview_canvas_item = None
        self.canvas_preview.delete("all")
        self.canvas_preview._preview_photo_ref = None
        self._limpar_imagem_scanner(ocultar=True)
        self.lbl_nome_scanner.configure(text="")
        self._fechar_doc_preview()
        self.caminho_pdf_atual = None
        self.total_paginas = 0
        self.pagina_atual = 0

    def iniciar_scanner(self, imagem_grande, texto_nome):
        self.modo_visualizacao = False
        self._cancelar_render_preview()
        self.frame_galeria.grid_remove()
        self.frame_scanner.grid()
        self.canvas_preview.grid_remove()
        self.lbl_img_scanner.grid()
        self.btn_voltar_preview.grid_remove()
        self.btn_abrir_externo.grid_remove()
        self.lbl_preview_scanner.configure(text="Scanner / processamento")
        self._definir_imagem_scanner(imagem_grande)
        self.lbl_nome_scanner.configure(text=f"Escaneando: {texto_nome}")
        self.animando = True
        self.pos_y = 0.02
        self.direcao = 1
        self.linha_scanner.place(relx=0.02, rely=0.02, relwidth=0.96)
        self.linha_scanner.lift()
        self.animar_scanner()

    def atualizar_imagem_scanner(self, imagem_grande, texto_nome):
        self._definir_imagem_scanner(imagem_grande)
        self.lbl_nome_scanner.configure(text=f"Escaneando: {texto_nome}")

    def parar_scanner(self):
        self.animando = False
        self.linha_scanner.place_forget()
        self.frame_scanner.grid_remove()
        self.frame_galeria.grid()
        self._limpar_imagem_scanner(ocultar=True)
        self.canvas_preview.grid()

    def animar_scanner(self):
        if not self.animando:
            return
        self.pos_y += 0.02 * self.direcao
        if self.pos_y >= 0.98:
            self.direcao = -1
        elif self.pos_y <= 0.02:
            self.direcao = 1
        self.linha_scanner.place(rely=self.pos_y)
        self.linha_scanner.lift()
        self.after(30, self.animar_scanner)

    def carregar_preview(self, caminho_pdf):
        self.abrir_visualizacao_pdf(caminho_pdf)

    def limpar_preview(self):
        self._cancelar_render_preview()
        self._preview_generation += 1
        self.modo_visualizacao = False
        self.animando = False
        self.frame_scanner.grid_remove()
        self.frame_galeria.grid()
        self._preview_ctk_image = None
        self._preview_pil_image = None
        self._preview_photo_image = None
        self._preview_canvas_item = None
        self.canvas_preview.delete("all")
        self.canvas_preview._preview_photo_ref = None
        self._limpar_imagem_scanner(ocultar=True)
        self.lbl_nome_scanner.configure(text="")
        self._fechar_doc_preview()
        self.caminho_pdf_atual = None
        self.total_paginas = 0
        self.pagina_atual = 0

    def selecionar_pdf_para_preview(self, caminho_pdf):
        self.abrir_visualizacao_pdf(caminho_pdf)

    def _set_text_preview(self, texto):
        self.textbox_preview.configure(state="normal")
        self.textbox_preview.delete("0.0", "end")
        self.textbox_preview.insert("0.0", texto)
        self.textbox_preview.configure(state="disabled")

# --- As classes TelaProjetos, TelaDetalhes e TelaConfigs permanecem inalteradas ---
# (mantenha exatamente como você já tem)
class TelaProjetos(ctk.CTkFrame):
    def __init__(self, master, comando_abrir_detalhes):
        super().__init__(master, fg_color="transparent")
        self.comando_abrir_detalhes = comando_abrir_detalhes
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="Meus Projetos", font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT).grid(row=0, column=0, padx=4, pady=(4, 16), sticky="w")
        self.scroll_projetos = ctk.CTkScrollableFrame(self, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER)
        self.scroll_projetos.grid(row=1, column=0, sticky="nsew")

    def carregar_lista(self):
        for widget in self.scroll_projetos.winfo_children():
            widget.destroy()
        from core.historico import historico_app
        projetos = historico_app.obter_todos()
        if not projetos:
            ctk.CTkLabel(self.scroll_projetos, text="Nenhum projeto convertido ainda.", text_color=MUTED).pack(pady=30)
            return
        for proj in projetos:
            card = ctk.CTkFrame(self.scroll_projetos, fg_color="#101923", corner_radius=10, border_width=1, border_color=BORDER)
            card.pack(fill="x", padx=10, pady=6)
            card.grid_columnconfigure(0, weight=1)
            data_proj = proj.get("data", "") if isinstance(proj, dict) else proj[2]
            origem = proj.get("pdf_original", "") if isinstance(proj, dict) else proj[1]
            destino = proj.get("md_gerado", "") if isinstance(proj, dict) else proj[3]
            box = ctk.CTkFrame(card, fg_color="transparent")
            box.grid(row=0, column=0, sticky="ew", padx=14, pady=12)
            ctk.CTkLabel(box, text=data_proj, font=ctk.CTkFont(size=10, weight="bold"), text_color=BLUE).pack(anchor="w")
            ctk.CTkLabel(box, text=f"De: {origem}", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT).pack(anchor="w", pady=(3, 0))
            ctk.CTkLabel(box, text=f"Para: {destino}", text_color=MUTED, font=ctk.CTkFont(size=11)).pack(anchor="w", pady=(2, 0))
            ctk.CTkButton(card, text="Abrir / Ver", width=105, height=34, fg_color=BLUE, hover_color=BLUE_HOVER, command=lambda p=proj: self.comando_abrir_detalhes(p)).grid(row=0, column=1, padx=14, pady=12)


class TelaDetalhes(ctk.CTkFrame):
    def __init__(self, master, comando_voltar, comando_copiar, comando_salvar):
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(4, 12))
        self.btn_voltar = ctk.CTkButton(header, text="← Voltar", width=88, height=34, fg_color=PANEL_2, hover_color="#1d2a39", command=comando_voltar)
        self.btn_voltar.pack(side="left")
        self.lbl_nome_projeto = ctk.CTkLabel(header, text="Visualizando...", font=ctk.CTkFont(size=18, weight="bold"), text_color=TEXT)
        self.lbl_nome_projeto.pack(side="left", padx=16)
        self.textbox_detalhes = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12), fg_color="#0a0f15", border_width=1, border_color=BORDER)
        self.textbox_detalhes.grid(row=1, column=0, pady=(0, 10), sticky="nsew")
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        ctk.CTkButton(footer, text="▣  Copiar Tudo", height=36, fg_color=BLUE, hover_color=BLUE_HOVER, font=ctk.CTkFont(weight="bold"), command=comando_copiar).pack(side="left", padx=(0, 8))
        ctk.CTkButton(footer, text="Salvar Como...", height=36, fg_color=PANEL_2, hover_color="#1d2a39", font=ctk.CTkFont(weight="bold"), command=comando_salvar).pack(side="left")

    def carregar_texto(self, titulo, texto):
        self.lbl_nome_projeto.configure(text=f"Visualizando: {titulo}")
        self.textbox_detalhes.configure(state="normal")
        self.textbox_detalhes.delete("0.0", "end")
        self.textbox_detalhes.insert("0.0", texto)
        self.textbox_detalhes.configure(state="disabled")


class TelaConfigs(ctk.CTkFrame):
    def __init__(self, master, comando_mudar_tema, comando_limpar_historico, comando_modo_compatibilidade=None):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="Configurações", font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT).grid(row=0, column=0, pady=(4, 16), sticky="w")
        frame_aparencia = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER)
        frame_aparencia.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        frame_aparencia.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame_aparencia, text="Aparência", font=ctk.CTkFont(size=15, weight="bold"), text_color=TEXT).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")
        ctk.CTkLabel(frame_aparencia, text="Tema do Aplicativo:", text_color=MUTED).grid(row=1, column=0, padx=16, pady=(5, 16), sticky="w")
        self.opt_tema = ctk.CTkOptionMenu(frame_aparencia, values=["Dark", "Light", "System"], command=comando_mudar_tema, width=150, fg_color="#0878d9", button_color="#0866b7", button_hover_color="#075da7")
        self.opt_tema.grid(row=1, column=1, padx=16, pady=(5, 16), sticky="e")
        from core.configuracao import config_app
        self.opt_tema.set(config_app.get("tema") or "Dark")
        frame_dados = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER)
        frame_dados.grid(row=2, column=0, sticky="ew", pady=10)
        ctk.CTkLabel(frame_dados, text="Dados do Aplicativo", font=ctk.CTkFont(size=15, weight="bold"), text_color=TEXT).grid(row=0, column=0, padx=16, pady=(16, 6), sticky="w")
        ctk.CTkLabel(frame_dados, text="Isso apagará o histórico de 'Meus Projetos', mas não excluirá os arquivos reais.", text_color=MUTED).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")
        ctk.CTkButton(frame_dados, text="Apagar Todo o Histórico", fg_color="#b91c1c", hover_color="#991b1b", height=36, font=ctk.CTkFont(weight="bold"), command=comando_limpar_historico).grid(row=2, column=0, padx=16, pady=(0, 16), sticky="w")

        frame_avancado = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER)
        frame_avancado.grid(row=3, column=0, sticky="ew", pady=10)
        frame_avancado.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame_avancado, text="Compatibilidade", font=ctk.CTkFont(size=15, weight="bold"), text_color=TEXT).grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        ctk.CTkLabel(frame_avancado, text="Reduz a pressão de memória e torna as retentativas de OCR mais conservadoras em computadores mais antigos.", text_color=MUTED, wraplength=720, justify="left").grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")
        self.sw_compat = ctk.CTkSwitch(frame_avancado, text="Modo de compatibilidade", command=lambda: comando_modo_compatibilidade(bool(self.sw_compat.get())) if comando_modo_compatibilidade else None)
        self.sw_compat.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="w")
        if bool(config_app.get("modo_compatibilidade")):
            self.sw_compat.select()

class TelaDiagnostico(ctk.CTkFrame):
    def __init__(self, master, comando_atualizar, comando_copiar, comando_abrir_logs):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self, text="Sobre / Diagnóstico", font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT
        ).grid(row=0, column=0, pady=(4, 12), sticky="w")

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkButton(toolbar, text="Atualizar diagnóstico", height=34, fg_color=BLUE, hover_color=BLUE_HOVER, command=comando_atualizar).pack(side="left")
        ctk.CTkButton(toolbar, text="Copiar", height=34, fg_color=PANEL_2, hover_color="#1d2a39", command=comando_copiar).pack(side="left", padx=8)
        ctk.CTkButton(toolbar, text="Abrir pasta de logs", height=34, fg_color=PANEL_2, hover_color="#1d2a39", command=comando_abrir_logs).pack(side="left")

        self.texto = ctk.CTkTextbox(
            self, font=ctk.CTkFont(family="Consolas", size=11), fg_color="#0a0f15",
            border_width=1, border_color=BORDER, corner_radius=8
        )
        self.texto.grid(row=2, column=0, sticky="nsew")
        self.definir_texto("Clique em 'Atualizar diagnóstico' para executar as verificações.")

    def definir_texto(self, texto):
        self.texto.configure(state="normal")
        self.texto.delete("0.0", "end")
        self.texto.insert("0.0", texto)
        self.texto.configure(state="disabled")
