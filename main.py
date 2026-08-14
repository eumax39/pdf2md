import shutil
import subprocess
import sys
from multiprocessing import freeze_support

Atualizador = None
APP_VERSION = "2.0.0"

def checar_dependencias():
    """Verifica dependências e tenta instalá-las de forma compatível com ambientes uv."""
    if getattr(sys, "frozen", False):
        return

    pacotes = {
        "customtkinter": "customtkinter",
        "fitz": "pymupdf",
        "pymupdf4llm": "pymupdf4llm",
        "PIL": "pillow",
        "tkinterdnd2": "tkinterdnd2",
        "numpy": "numpy",
        "paddleocr": "paddleocr",
        "paddle": "paddlepaddle",
        "requests": "requests",
        "packaging": "packaging",
    }

    faltando = []
    for modulo, pacote in pacotes.items():
        try:
            __import__(modulo)
        except ImportError:
            faltando.append(pacote)

    if not faltando:
        return

    print(f"Dependências ausentes: {', '.join(faltando)}. Tentando instalar...")

    comandos = []
    if shutil.which("uv"):
        comandos.append(["uv", "pip", "install", *faltando, "--python", sys.executable, "--quiet"])

    comandos.append([sys.executable, "-m", "pip", "install", *faltando, "--quiet", "--break-system-packages"])

    for comando in comandos:
        try:
            subprocess.check_call(comando)
            print("Instalação concluída com sucesso.")
            return
        except Exception as e:
            print(f"Falha ao instalar dependências com {comando[0]}: {e}")

    print("Não foi possível instalar todas as dependências automaticamente. Instale manualmente com: uv pip install customtkinter pymupdf pymupdf4llm pillow tkinterdnd2 numpy paddleocr paddlepaddle requests packaging")

# Executa a verificação antes de importar o restante da aplicação
checar_dependencias()

try:
    from core.updater import Atualizador
    from core.version import APP_VERSION
except ImportError:
    # A aplicação continua funcionando mesmo que o módulo de atualização falhe
    # em ambiente de desenvolvimento. No executável, requests/packaging são
    # empacotados pelo fluxo já existente.
    Atualizador = None

import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
import pathlib
import os
import fitz 
from PIL import Image
import re

from app.telas import (
    TelaInicio,
    TelaProjetos,
    TelaDetalhes,
    TelaConfigs,
    FORMATO_MD,
    FORMATO_PDF_OCR,
)
from core.conversor import MotorConversao
from core.configuracao import config_app
from core.historico import historico_app
from core.utils import get_resource_path
from ocr.manager import ocr_engine

DIRETORIO_SCRIPT = get_resource_path()

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

class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self) 

        self.title("PDF a MD Converter Pro")
        self.geometry("1450x900")
        self.minsize(1180, 760)
        
        ctk.set_appearance_mode(config_app.get("tema") or "Dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color="#0b1118")

        try: self.iconbitmap(str(get_resource_path("icone.ico")))
        except: pass

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.arquivos_selecionados = [] 
        self.pasta_destino = None 
        self.texto_projeto_aberto = "" 
        self.motor_conversao = None
        self.raw_thumbnails = [] 
        self._preview_cache = {}
        self._ui_icons_main = {}
        self._atualizacao_em_andamento = False
        self._update_info_pendente = None
        
        self.indice_arquivo_atual = -1
        self.indice_pagina_atual = -1

        self.criar_barra_lateral()
        self.criar_telas()
        self.mostrar_tela("inicio")
        self.atualizar_interface_arquivos()
        self.after(800, self.verificar_saude_ocr_inicial)

        # Verificar atualizações (apenas no executável)
        if getattr(sys, 'frozen', False) and Atualizador is not None:
            self.after(3000, self._verificar_atualizacao_background)

    def verificar_saude_ocr_inicial(self):
        modo = normalizar_modo_conversao(config_app.get("modo_conversao"))
        if modo == MODO_REFERENCIA_IMAGEM:
            return

        def _worker():
            try:
                ocr_engine.inicializar_se_necessario()
                indisponivel = (ocr_engine.motor == "ERRO") or bool(getattr(ocr_engine, "_desabilitado", False))
                detalhe = str(getattr(ocr_engine, "_ultimo_erro_init", "") or "")
            except Exception as e:
                indisponivel = True
                detalhe = str(e)

            def _atualizar_ui():
                if indisponivel:
                    self.tela_inicio.lbl_status.configure(
                        text="⚠️ OCR indisponível neste ambiente (modo digital ainda funciona)",
                        text_color="#ca8a04",
                    )
                    if detalhe:
                        self.tela_inicio.textbox_preview.configure(state="normal")
                        self.tela_inicio.textbox_preview.insert(
                            "end",
                            f"> [Diagnóstico OCR na inicialização] {detalhe}\n\n",
                        )
                        self.tela_inicio.textbox_preview.see("end")
                        self.tela_inicio.textbox_preview.configure(state="disabled")

            self.after(0, _atualizar_ui)

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def criar_barra_lateral(self):
        self.sidebar = ctk.CTkFrame(self, width=190, corner_radius=0, fg_color="#0b1118", border_width=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(5, weight=1)

        try:
            caminho_logo = get_resource_path("logo.png")
            img_logo = ctk.CTkImage(
                light_image=Image.open(caminho_logo), dark_image=Image.open(caminho_logo), size=(34, 34)
            )
            self.logo_label = ctk.CTkLabel(
                self.sidebar, text="PDF a MD\nConverter", image=img_logo, compound="left",
                font=ctk.CTkFont(size=19, weight="bold"), text_color="#f3f7fb", justify="left"
            )
        except Exception:
            self.logo_label = ctk.CTkLabel(
                self.sidebar, text="PDF a MD\nConverter", font=ctk.CTkFont(size=19, weight="bold"), text_color="#f3f7fb"
            )
        self.logo_label.grid(row=0, column=0, padx=16, pady=(28, 34), sticky="w")

        btn_cfg = dict(
            anchor="w", height=36, corner_radius=8, fg_color="transparent",
            text_color="#d6dee7", hover_color="#172230", font=ctk.CTkFont(size=13)
        )
        self.btn_inicio = ctk.CTkButton(self.sidebar, text="⌂  Início", command=lambda: self.mostrar_tela("inicio"), **btn_cfg)
        self.btn_inicio.grid(row=1, column=0, padx=14, pady=4, sticky="ew")
        self.btn_projetos = ctk.CTkButton(self.sidebar, text="▤  Meus Projetos", command=lambda: self.mostrar_tela("projetos"), **btn_cfg)
        self.btn_projetos.grid(row=2, column=0, padx=14, pady=4, sticky="ew")
        self.btn_configs = ctk.CTkButton(self.sidebar, text="⚙  Configurações", command=lambda: self.mostrar_tela("configs"), **btn_cfg)
        self.btn_configs.grid(row=3, column=0, padx=14, pady=4, sticky="ew")

        self.lbl_creditos_sidebar = ctk.CTkLabel(
            self.sidebar,
            text="Desenvolvedor:\nMaxwell Barros Veras de Araujo\n\nSuporte:\nmaxwellbvras@gmail.com",
            font=ctk.CTkFont(size=10), text_color="#667384", justify="center"
        )
        self.lbl_creditos_sidebar.grid(row=6, column=0, padx=8, pady=(20, 22), sticky="s")

    def criar_telas(self):
        self.tela_inicio = TelaInicio(
            self, 
            comando_selecionar_pdf=self.selecionar_pdf, 
            comando_soltar_pdf=self.ao_soltar_arquivos, 
            comando_pasta=self.selecionar_pasta_destino, 
            comando_converter=self.iniciar_conversao, 
            comando_cancelar=self.cancelar_conversao,
            comando_importar_pasta=self.importar_pasta_origem
        )
        self.tela_projetos = TelaProjetos(self, comando_abrir_detalhes=self.abrir_projeto)
        self.tela_detalhes = TelaDetalhes(self, comando_voltar=lambda: self.mostrar_tela("projetos"), comando_copiar=self.copiar_texto_projeto, comando_salvar=self.salvar_projeto_como)
        self.tela_configs = TelaConfigs(self, comando_mudar_tema=self.mudar_tema_app, comando_limpar_historico=self.limpar_historico)

        for frame in (self.tela_inicio, self.tela_projetos, self.tela_detalhes, self.tela_configs):
            frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

    def mostrar_tela(self, nome_tela):
        self.tela_inicio.grid_remove()
        self.tela_projetos.grid_remove()
        self.tela_detalhes.grid_remove()
        self.tela_configs.grid_remove()
        
        self.btn_inicio.configure(fg_color="transparent")
        self.btn_projetos.configure(fg_color="transparent")
        self.btn_configs.configure(fg_color="transparent")
        
        if nome_tela == "inicio":
            self.tela_inicio.grid()
            self.btn_inicio.configure(fg_color="#3b82f6") 
        elif nome_tela == "projetos":
            self.tela_projetos.grid()
            self.tela_projetos.carregar_lista() 
            self.btn_projetos.configure(fg_color="#3b82f6") 
        elif nome_tela == "detalhes":
            self.tela_detalhes.grid()
            self.btn_projetos.configure(fg_color="#3b82f6") 
        elif nome_tela == "configs":
            self.tela_configs.grid()
            self.btn_configs.configure(fg_color="#3b82f6")

    # ==========================================
    # SELEÇÃO DE ARQUIVOS E GALERIA
    # ==========================================
    def ao_soltar_arquivos(self, event):
        arquivos = self.tk.splitlist(event.data)
        pdfs = [f for f in arquivos if f.lower().endswith('.pdf')]
        self.adicionar_arquivos(pdfs)

    def selecionar_pdf(self):
        arquivos = filedialog.askopenfilenames(filetypes=[("Arquivos PDF", "*.pdf")])
        if arquivos: self.adicionar_arquivos(list(arquivos))

    def importar_pasta_origem(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta contendo os PDFs")
        if pasta:
            pdfs = [os.path.join(pasta, f) for f in os.listdir(pasta) if f.lower().endswith('.pdf')]
            if pdfs:
                self.adicionar_arquivos(pdfs)
            else:
                messagebox.showinfo("Aviso", "Nenhum arquivo PDF encontrado nesta pasta.")

    def adicionar_arquivos(self, novos_pdfs):
        para_adicionar = [p for p in novos_pdfs if p not in self.arquivos_selecionados]
        self.arquivos_selecionados.extend(para_adicionar)
        self.atualizar_interface_arquivos()
        # O preview visual só é aberto quando o usuário clica em um PDF.
        # A grade permanece como tela de seleção.
        self.tela_inicio.limpar_preview()

    def remover_arquivo(self, caminho):
        if caminho in self.arquivos_selecionados:
            self.arquivos_selecionados.remove(caminho)
            self.atualizar_interface_arquivos()
            # O preview não é aberto automaticamente.
            self.tela_inicio.limpar_preview()

    def gerar_preview_imagem(self, caminho_pdf, num_pagina=0):
        """Renderiza a página física completa (MediaBox), sem respeitar um CropBox reduzido."""
        chave_cache = (str(pathlib.Path(caminho_pdf)), int(num_pagina), "full-media")
        if chave_cache in self._preview_cache:
            return self._preview_cache[chave_cache]
        try:
            doc = fitz.open(caminho_pdf)
            if len(doc) == 0:
                doc.close()
                return None
            num_pagina = max(0, min(num_pagina, len(doc) - 1))
            pagina = doc.load_page(num_pagina)
            crop_original = fitz.Rect(pagina.cropbox)
            try:
                pagina.set_cropbox(pagina.mediabox)
                pix = pagina.get_pixmap(dpi=180, colorspace=fitz.csRGB, alpha=False)
            finally:
                try:
                    pagina.set_cropbox(crop_original)
                except Exception:
                    pass
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            doc.close()
            self._preview_cache[chave_cache] = img
            return img
        except Exception:
            return None

    def _ui_icon(self, nome, size=(16, 16)):
        chave = (nome, tuple(size))
        if chave in self._ui_icons_main:
            return self._ui_icons_main[chave]
        try:
            img = Image.open(get_resource_path("assets", "ui", nome)).convert("RGBA")
            icon = ctk.CTkImage(light_image=img, dark_image=img, size=size)
            self._ui_icons_main[chave] = icon
            return icon
        except Exception:
            return None

    def _selecionar_card_preview(self, caminho, card):
        for child in self.tela_inicio.frame_galeria.winfo_children():
            if hasattr(child, "caminho"):
                try:
                    child.configure(border_width=1, border_color="#263444")
                except Exception:
                    pass
        try:
            card.configure(border_width=2, border_color="#2088ff")
        except Exception:
            pass
        self.tela_inicio.abrir_visualizacao_pdf(caminho)

    def _mostrar_lista_completa(self):
        """Abre uma janela com a lista completa de arquivos."""
        if not self.arquivos_selecionados:
            return

        janela = ctk.CTkToplevel(self)
        janela.title("Todos os arquivos na fila")
        janela.geometry("400x300")
        janela.resizable(True, True)
        janela.transient(self)
        janela.grab_set()

        scroll = ctk.CTkScrollableFrame(janela, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        for caminho in self.arquivos_selecionados:
            nome = pathlib.Path(caminho).name
            frame = ctk.CTkFrame(scroll, fg_color="#2b2b2b", corner_radius=8)
            frame.pack(fill="x", pady=3)

            label = ctk.CTkLabel(frame, text=nome, anchor="w")
            label.pack(side="left", padx=10, pady=5)

            # Ao clicar no frame ou label, seleciona esse arquivo
            def _on_click(c=caminho, janela=janela):
                janela.destroy()
                # Carrega o preview
                self.tela_inicio.carregar_preview(c)
                # Tenta destacar o card correspondente (se estiver visível)
                for child in self.tela_inicio.frame_galeria.winfo_children():
                    if isinstance(child, ctk.CTkFrame) and child != self.tela_inicio._drop_area:
                        if hasattr(child, 'caminho') and child.caminho == c:
                            # Remove destaque de todos
                            for ch in self.tela_inicio.frame_galeria.winfo_children():
                                if isinstance(ch, ctk.CTkFrame) and ch != self.tela_inicio._drop_area:
                                    try:
                                        ch.configure(border_width=2, border_color="#3f3f46")
                                    except:
                                        pass
                            child.configure(border_width=2, border_color="#3b82f6")
                            break

            # Usamos lambda para ignorar o evento e passar o caminho
            frame.bind("<Button-1>", lambda e, c=caminho: _on_click(c))
            label.bind("<Button-1>", lambda e, c=caminho: _on_click(c))

    def atualizar_interface_arquivos(self):
        """Atualiza a galeria compacta de PDFs sem deformar/cortar as miniaturas."""
        galeria = self.tela_inicio.frame_galeria
        for widget in galeria.winfo_children():
            widget.destroy()
        self.raw_thumbnails.clear()
        qtd = len(self.arquivos_selecionados)

        # Remove qualquer configuração de linha expansível deixada por versões antigas.
        for r in range(10):
            try:
                galeria.grid_rowconfigure(r, weight=0, minsize=0)
            except Exception:
                pass
        for c in range(4):
            galeria.grid_columnconfigure(c, weight=1, uniform="gallery")

        # Drop zone compacto com ícone azul real.
        area_drop = ctk.CTkFrame(
            galeria, fg_color="#101923", border_width=1, border_color="#304154",
            corner_radius=8, cursor="hand2", height=82
        )
        area_drop.grid(row=0, column=0, columnspan=4, sticky="ew", padx=10, pady=(10, 7))
        area_drop.grid_propagate(False)
        area_drop.grid_columnconfigure(0, weight=1)
        area_drop.grid_rowconfigure(0, weight=1)
        drop_inner = ctk.CTkFrame(area_drop, fg_color="transparent")
        drop_inner.grid(row=0, column=0)
        cloud_icon = self._ui_icon("cloud_upload.png", (28, 28))
        lbl_cloud = ctk.CTkLabel(drop_inner, text="", image=cloud_icon, width=30, height=30)
        lbl_cloud.pack(pady=(2, 0))
        lbl_cloud._ui_image_ref = cloud_icon
        lbl_drop = ctk.CTkLabel(
            drop_inner, text="Arraste mais PDFs aqui  (ou clique para selecionar)",
            text_color="#9aa7b6", font=ctk.CTkFont(size=11), justify="center"
        )
        lbl_drop.pack(pady=(0, 2))
        self.tela_inicio._drop_area = area_drop

        def _on_clique(event=None):
            self.selecionar_pdf()
        for w in (area_drop, drop_inner, lbl_cloud, lbl_drop):
            w.bind("<Button-1>", _on_clique)
        try:
            area_drop.drop_target_register(DND_FILES)
            area_drop.dnd_bind("<<Drop>>", self.ao_soltar_arquivos)
        except Exception:
            pass

        if qtd == 0:
            self.tela_inicio.lbl_arquivo_selecionado.configure(
                text="Total: 0 arquivo(s) na fila de conversão"
            )
            self.tela_inicio.btn_converter.configure(state="disabled")
            self.tela_inicio.lbl_status.configure(text="Pronto para iniciar.", text_color="#8d99a8")
            return

        self.tela_inicio.lbl_arquivo_selecionado.configure(
            text=f"Total: {qtd} arquivo(s) na fila de conversão"
        )
        self.tela_inicio.btn_converter.configure(state="normal")
        self.tela_inicio.lbl_status.configure(text="Pronto para iniciar.", text_color="#8d99a8")

        # Até 8 arquivos aparecem de forma explícita. Se houver mais, 7 + resumo.
        capacidade = 8
        mostrar_resumo = qtd > capacidade
        max_previews = 7 if mostrar_resumo else qtd

        pdf_icon = self._ui_icon("pdf.png", (14, 14))
        trash_icon = self._ui_icon("trash.png", (16, 16))

        for i in range(max_previews):
            caminho = self.arquivos_selecionados[i]

            # O card SEMPRE é criado, mesmo se uma miniatura específica falhar.
            card = ctk.CTkFrame(
                galeria, fg_color="#111923", corner_radius=9,
                border_width=1, border_color="#263444", cursor="hand2"
            )
            card.caminho = caminho
            row = 1 + (i // 4)
            col = i % 4
            card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

            # Stage fixo, mas a página é FIT dentro dele: sem corte e sem deformação.
            page_stage = ctk.CTkFrame(card, fg_color="#0a1017", corner_radius=6, height=158)
            page_stage.pack(fill="x", padx=7, pady=(7, 5))
            page_stage.pack_propagate(False)

            img_pil = self.gerar_preview_imagem(caminho)
            if img_pil is not None:
                self.raw_thumbnails.append(img_pil)
                thumb = img_pil.copy()
                # Margem segura em todos os lados; nunca excede a área do stage.
                thumb.thumbnail((108, 144), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)
                page = ctk.CTkLabel(page_stage, text="", image=ctk_img, fg_color="transparent")
                page._pdf_image_ref = ctk_img
            else:
                page = ctk.CTkLabel(
                    page_stage, text="PDF", image=pdf_icon, compound="top",
                    text_color="#718095", font=ctk.CTkFont(size=10)
                )
                page._pdf_image_ref = pdf_icon
            page.place(relx=0.5, rely=0.5, anchor="center")

            nome = pathlib.Path(caminho).name
            nome_curto = nome if len(nome) <= 19 else nome[:16] + "..."

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(fill="x", padx=7, pady=(0, 6))
            info.grid_columnconfigure(1, weight=1)
            lbl_pdf_icon = ctk.CTkLabel(info, text="", image=pdf_icon, width=16, height=16)
            lbl_pdf_icon.grid(row=0, column=0, padx=(0, 4), sticky="w")
            lbl_pdf_icon._ui_image_ref = pdf_icon
            lbl_nome = ctk.CTkLabel(
                info, text=nome_curto, text_color="#dce5ee", anchor="w",
                font=ctk.CTkFont(size=9, weight="bold")
            )
            lbl_nome.grid(row=0, column=1, sticky="ew")

            try:
                with fitz.open(caminho) as _doc_info:
                    total_paginas = len(_doc_info)
            except Exception:
                total_paginas = 0
            txt_pag = f"{total_paginas} página" if total_paginas == 1 else f"{total_paginas} páginas"
            lbl_paginas = ctk.CTkLabel(
                info, text=txt_pag, text_color="#718095", anchor="w",
                font=ctk.CTkFont(size=9)
            )
            lbl_paginas.grid(row=1, column=1, sticky="w", pady=(0, 1))

            btn_remover = ctk.CTkButton(
                card, text="", image=trash_icon, width=26, height=26, corner_radius=8,
                fg_color="#2a1a20", hover_color="#492129", border_width=0,
                command=lambda c=caminho: self.remover_arquivo(c)
            )
            btn_remover._ui_image_ref = trash_icon
            btn_remover.place(relx=0.965, rely=0.018, anchor="ne")

            # Todo o card, exceto lixeira, abre o preview integrado ao scanner.
            callback = lambda e, c=caminho, card=card: self._selecionar_card_preview(c, card)
            for w in (card, page_stage, page, info, lbl_pdf_icon, lbl_nome, lbl_paginas):
                w.bind("<Button-1>", callback)

        if mostrar_resumo:
            restante = qtd - max_previews
            i = 7
            row = 1 + (i // 4)
            col = i % 4
            extra = ctk.CTkFrame(
                galeria, fg_color="#101923", corner_radius=9,
                border_width=1, border_color="#304154", cursor="hand2"
            )
            extra.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            extra_inner = ctk.CTkFrame(extra, fg_color="transparent")
            extra_inner.pack(expand=True, fill="both", padx=8, pady=18)
            ctk.CTkLabel(
                extra_inner, text="+", text_color="#6aaeff",
                font=ctk.CTkFont(size=28, weight="bold")
            ).pack()
            ctk.CTkLabel(
                extra_inner, text=f"{restante} arquivo(s)\nna fila",
                text_color="#8fa0b2", font=ctk.CTkFont(size=10, weight="bold"),
                justify="center"
            ).pack()
            extra.bind("<Button-1>", lambda e: self._mostrar_lista_completa())
            extra_inner.bind("<Button-1>", lambda e: self._mostrar_lista_completa())

    def selecionar_pasta_destino(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.pasta_destino = pasta
            texto_exibicao = pasta if len(pasta) < 35 else "..." + pasta[-32:]
            self.tela_inicio.lbl_caminho_destino.configure(text=f"Salvar em: {texto_exibicao}")

    # ==========================================
    # LÓGICA DE CONVERSÃO E SCANNER GIGANTE
    # ==========================================
    def iniciar_conversao(self):
        self.tela_inicio.btn_converter.configure(state="disabled")
        self.tela_inicio.btn_cancelar.grid() 
        self.tela_inicio.progressbar.set(0)
        
        self.tela_inicio.textbox_preview.configure(state="normal")
        self.tela_inicio.textbox_preview.delete("0.0", "end")
        self.tela_inicio.textbox_preview.configure(state="disabled")

        self.indice_arquivo_atual = -1
        self.indice_pagina_atual = -1

        # Scanner começa com a página física completa, sem CropBox reduzido.
        if self.arquivos_selecionados:
            img_pil = self.gerar_preview_imagem(self.arquivos_selecionados[0], num_pagina=0)
            if img_pil:
                img_scan = img_pil.copy()
                img_scan.thumbnail((700, 820), Image.Resampling.LANCZOS)
                img_grande = ctk.CTkImage(light_image=img_scan, dark_image=img_scan, size=img_scan.size)
                nome_arq = pathlib.Path(self.arquivos_selecionados[0]).name
                self.tela_inicio.iniciar_scanner(img_grande, f"{nome_arq}")

        modo_selecionado = self.tela_inicio.opt_modo.get()
        modo_selecionado = normalizar_modo_conversao(modo_selecionado)
        config_app.set("modo_conversao", modo_selecionado)
        formato_saida = self.tela_inicio.opt_formato_saida.get()

        # A opcao de formato de saida so se aplica ao modo Forcar OCR.
        if modo_selecionado != MODO_FORCAR_OCR:
            formato_saida = FORMATO_MD

        # OCR é desativado no modo de referência de imagem para acelerar processos grandes.
        usar_ocr = modo_selecionado != MODO_REFERENCIA_IMAGEM

        if usar_ocr:
            ocr_engine.inicializar_se_necessario()
            ocr_indisponivel = (ocr_engine.motor == "ERRO") or bool(getattr(ocr_engine, "_desabilitado", False))
            if ocr_indisponivel:
                if formato_saida == FORMATO_PDF_OCR:
                    self.tela_inicio.btn_converter.configure(state="normal")
                    self.tela_inicio.btn_cancelar.grid_remove()
                    self.tela_inicio.btn_cancelar.configure(state="normal", text="❌ Cancelar")
                    self.tela_inicio.lbl_status.configure(
                        text="⚠️ Conversão não iniciada: OCR indisponível para PDF OCR",
                        text_color="#ca8a04"
                    )
                    messagebox.showerror(
                        "OCR indisponível",
                        "Não é possível gerar PDF com OCR porque o motor OCR está indisponível neste ambiente."
                    )
                    return

                resposta = messagebox.askyesno(
                    "OCR indisponível",
                    "O OCR não está disponível neste ambiente.\n\n"
                    "Deseja continuar apenas com extração digital (sem OCR)?"
                )
                if not resposta:
                    self.tela_inicio.btn_converter.configure(state="normal")
                    self.tela_inicio.btn_cancelar.grid_remove()
                    self.tela_inicio.btn_cancelar.configure(state="normal", text="❌ Cancelar")
                    self.tela_inicio.lbl_status.configure(
                        text="⚠️ Conversão não iniciada: OCR indisponível",
                        text_color="#ca8a04"
                    )
                    return
                usar_ocr = False

        self.motor_conversao = MotorConversao(
            arquivos=self.arquivos_selecionados,
            pasta_destino=self.pasta_destino,
            usar_ocr=usar_ocr,
            cb_progresso=self.atualizar_progresso,
            cb_concluido=self.conversao_concluida,
            cb_erro=self.conversao_erro,
            formato_saida=formato_saida,
        )
        self.motor_conversao.iniciar()

    def cancelar_conversao(self):
        if self.motor_conversao:
            self.tela_inicio.btn_cancelar.configure(state="disabled", text="Cancelando...")
            self.motor_conversao.solicitar_cancelamento()

    def atualizar_progresso(self, status_msg, porcentagem, texto_novo):
        self.tela_inicio.lbl_status.configure(text=status_msg, text_color=("black", "white"))
        self.tela_inicio.progressbar.set(porcentagem)
        
        match = re.search(r"Arquivo (\d+)/.*?Página (\d+)", status_msg)
        if match:
            idx_arquivo = int(match.group(1)) - 1
            idx_pagina = int(match.group(2)) - 1
            
            if idx_arquivo != self.indice_arquivo_atual or idx_pagina != self.indice_pagina_atual:
                self.indice_arquivo_atual = idx_arquivo
                self.indice_pagina_atual = idx_pagina
                
                if idx_arquivo < len(self.arquivos_selecionados):
                    caminho_atual = self.arquivos_selecionados[idx_arquivo]
                    img_pil = self.gerar_preview_imagem(caminho_atual, num_pagina=idx_pagina)
                    
                    if img_pil:
                        img_scan = img_pil.copy()
                        img_scan.thumbnail((700, 820), Image.Resampling.LANCZOS)
                        img_grande = ctk.CTkImage(light_image=img_scan, dark_image=img_scan, size=img_scan.size)
                        nome_arq = pathlib.Path(caminho_atual).name
                        self.tela_inicio.atualizar_imagem_scanner(img_grande, f"{nome_arq} (Pág {idx_pagina+1})")

        if texto_novo:
            self.tela_inicio.textbox_preview.configure(state="normal")
            self.tela_inicio.textbox_preview.insert("end", texto_novo + "\n")
            self.tela_inicio.textbox_preview.see("end")
            self.tela_inicio.textbox_preview.configure(state="disabled")

    def conversao_concluida(self, resumo=None):
        self.tela_inicio.parar_scanner() 
        self.motor_conversao = None

        self.tela_inicio.progressbar.set(1)
        self.tela_inicio.btn_converter.configure(state="normal")
        self.tela_inicio.btn_cancelar.grid_remove() 
        self.tela_inicio.btn_cancelar.configure(state="normal", text="❌ Cancelar") 

        resumo = resumo or {}
        qtd_alertas_ocr = int(resumo.get("qtd_alertas_ocr", 0) or 0)
        usou_ocr = bool(resumo.get("usou_ocr", False))

        if usou_ocr and qtd_alertas_ocr > 0:
            self.tela_inicio.lbl_status.configure(text="⚠️ Concluído com alertas de OCR", text_color="#ca8a04")
            messagebox.showwarning(
                "Concluído com Alertas",
                "A conversão terminou, mas houve falhas de OCR em uma ou mais páginas.\n"
                "Verifique o markdown e o arquivo de log para detalhes."
            )
        else:
            self.tela_inicio.lbl_status.configure(text="✅ Concluído com Sucesso!", text_color="#16a34a")
            messagebox.showinfo("Sucesso", "A conversão foi finalizada perfeitamente!")

        self._oferecer_atualizacao_pendente()

    def conversao_erro(self, erro, cancelado=False):
        self.tela_inicio.parar_scanner()
        self.motor_conversao = None
        self.tela_inicio.btn_converter.configure(state="normal")
        self.tela_inicio.btn_cancelar.grid_remove()
        self.tela_inicio.btn_cancelar.configure(state="normal", text="❌ Cancelar") 
        
        if cancelado:
            self.tela_inicio.lbl_status.configure(text="⚠️ Conversão Interrompida", text_color="#ca8a04")
            messagebox.showwarning("Cancelado", "A conversão foi cancelada pelo usuário.\nO que já havia sido lido foi salvo.")
        else:
            self.tela_inicio.lbl_status.configure(text="❌ Erro na conversão", text_color="red")
            messagebox.showerror("Erro Crítico", f"Falha ao processar:\n\n{erro}")

        self._oferecer_atualizacao_pendente()

    # ==========================================
    # OUTROS MÉTODOS
    # ==========================================
    def abrir_projeto(self, projeto):
        caminho_str = projeto.get("md_gerado", "") if isinstance(projeto, dict) else projeto[3]
        caminho = pathlib.Path(caminho_str) 
        if not caminho.exists():
            messagebox.showwarning("Aviso", "O arquivo Markdown não foi encontrado.")
            return
        try:
            self.texto_projeto_aberto = caminho.read_text(encoding="utf-8")
            self.tela_detalhes.carregar_texto(caminho.name, self.texto_projeto_aberto)
            self.mostrar_tela("detalhes")
        except Exception as e: 
            messagebox.showerror("Erro", f"Não foi possível ler o arquivo:\n{str(e)}")

    def copiar_texto_projeto(self):
        self.clipboard_clear()
        self.clipboard_append(self.texto_projeto_aberto)
        messagebox.showinfo("Copiado", "Texto copiado para a área de transferência!")

    def salvar_projeto_como(self):
        novo_caminho = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown", "*.md")])
        if novo_caminho:
            try:
                pathlib.Path(novo_caminho).write_text(self.texto_projeto_aberto, encoding="utf-8")
                messagebox.showinfo("Sucesso", "Arquivo salvo com sucesso!")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar o arquivo:\n{str(e)}")

    def mudar_tema_app(self, novo_tema):
        ctk.set_appearance_mode(novo_tema)
        config_app.set("tema", novo_tema)
        
    def limpar_historico(self):
        resposta = messagebox.askyesno("Aviso", "Deseja apagar todo o histórico de conversões do sistema?")
        if resposta:
            historico_app.limpar_historico()
            messagebox.showinfo("Sucesso", "O histórico foi apagado!")
            self.tela_projetos.carregar_lista()

    # ==========================================
    # ATUALIZAÇÕES AUTOMÁTICAS
    # ==========================================
    def _verificar_atualizacao_background(self):
        """Verifica atualizações em segundo plano sem bloquear a interface."""
        if self._atualizacao_em_andamento:
            return

        def _worker():
            try:
                updater = Atualizador()
                update_info = updater.verificar()
                if update_info:
                    self.after(0, lambda info=update_info: self._mostrar_aviso_atualizacao(info))
            except Exception:
                # Falha de rede não deve incomodar o usuário nem impedir a abertura.
                pass

        import threading
        threading.Thread(target=_worker, daemon=True).start()

    def _mostrar_aviso_atualizacao(self, update_info):
        """Pergunta ao usuário se deseja instalar uma versão mais nova."""
        if self._atualizacao_em_andamento:
            return

        # Nunca interrompe uma conversão em andamento. Se a checagem terminar
        # durante a conversão, a atualização será oferecida depois dela.
        if self.motor_conversao is not None:
            self._update_info_pendente = update_info
            return

        versao = update_info.get("versao", "desconhecida")
        notas = (update_info.get("body", "") or "").strip()
        if len(notas) > 700:
            notas = notas[:700].rstrip() + "…"

        msg = f"Nova versão {versao} disponível!\n\n"
        if notas:
            msg += f"Principais mudanças:\n{notas}\n\n"
        msg += "Deseja baixar e instalar agora? O programa será fechado para concluir a atualização."

        resposta = messagebox.askyesno("Atualização disponível", msg, icon="info")
        if resposta:
            self._baixar_atualizacao(update_info)

    def _baixar_atualizacao(self, update_info):
        """Baixa o instalador em thread separada e instala pela thread principal."""
        if self._atualizacao_em_andamento:
            return

        updater = Atualizador()
        asset_exe = updater.selecionar_instalador(update_info.get("assets", []))

        if not asset_exe:
            messagebox.showerror(
                "Atualização",
                "Não foi possível identificar com segurança o instalador do release.\n\n"
                "Anexe ao GitHub Release um único instalador .exe do Inno Setup, "
                "preferencialmente chamado PDF2MD_Setup.exe.",
            )
            return

        self._atualizacao_em_andamento = True
        self.tela_inicio.btn_converter.configure(state="disabled")
        self.tela_inicio.lbl_status.configure(
            text=f"⬇ Baixando atualização {update_info.get('versao', '')}...",
            text_color="#3b82f6",
        )
        self.tela_inicio.progressbar.set(0)

        def _baixar():
            try:
                caminho_instalador = updater.baixar_instalador(
                    asset=asset_exe,
                    versao=update_info.get("versao", "latest"),
                    callback_progress=self._atualizar_progresso_download,
                )
                self.after(
                    0,
                    lambda caminho=caminho_instalador, up=updater: self._instalar_atualizacao_e_encerrar(up, caminho),
                )
            except Exception as e:
                self.after(0, lambda erro=e: self._falha_atualizacao(erro))

        import threading
        threading.Thread(target=_baixar, daemon=True).start()

    def _atualizar_progresso_download(self, progresso):
        """Atualiza a barra de progresso durante o download."""
        valor = max(0.0, min(100.0, float(progresso))) / 100.0
        try:
            self.after(0, lambda v=valor: self.tela_inicio.progressbar.set(v))
        except Exception:
            pass

    def _falha_atualizacao(self, erro):
        self._atualizacao_em_andamento = False
        try:
            self.tela_inicio.btn_converter.configure(state="normal")
            self.tela_inicio.lbl_status.configure(
                text="⚠ Falha ao baixar atualização",
                text_color="#ca8a04",
            )
        except Exception:
            pass
        messagebox.showerror(
            "Atualização",
            f"Não foi possível concluir a atualização.\n\n{erro}",
        )

    def _instalar_atualizacao_e_encerrar(self, updater, caminho_instalador):
        """Inicia o Inno Setup e encerra o PDF2MD pela thread principal."""
        try:
            self.tela_inicio.lbl_status.configure(
                text="Instalador pronto. Fechando o PDF2MD para atualizar...",
                text_color="#16a34a",
            )
            self.tela_inicio.progressbar.set(1)
            self.update_idletasks()

            updater.executar_instalador(caminho_instalador)

            # O instalador é um processo independente. O encerramento forçado
            # garante que DLLs/EXE não permaneçam bloqueados durante a troca.
            self.after(250, self._encerrar_processo_para_atualizacao)
        except Exception as e:
            self._falha_atualizacao(e)

    def _encerrar_processo_para_atualizacao(self):
        try:
            self.quit()
            self.destroy()
        finally:
            # Há bibliotecas de OCR que podem manter threads/processos auxiliares.
            # Depois que o instalador já foi criado, a saída imediata é intencional.
            os._exit(0)

    def _oferecer_atualizacao_pendente(self):
        """Exibe uma atualização que ficou aguardando o fim da conversão."""
        info = self._update_info_pendente
        self._update_info_pendente = None
        if info and not self._atualizacao_em_andamento:
            self.after(350, lambda: self._mostrar_aviso_atualizacao(info))

if __name__ == "__main__":
    # Necessário no Windows (especialmente em executáveis PyInstaller) para
    # que subprocessos de multiprocessing não executem a GUI novamente.
    freeze_support()
    app = App()
    app.mainloop()