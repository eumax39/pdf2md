import shutil
import subprocess
import sys
from multiprocessing import freeze_support

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
        "paddle": "paddlepaddle"
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

    print("Não foi possível instalar todas as dependências automaticamente. Instale manualmente com: uv pip install customtkinter pymupdf pymupdf4llm pillow tkinterdnd2 numpy paddleocr paddlepaddle")

# Executa a verificação antes de importar o restante da aplicação
checar_dependencias()

import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
import pathlib
import os
import fitz 
from PIL import Image
import re

from app.telas import TelaInicio, TelaProjetos, TelaDetalhes, TelaConfigs
from core.conversor import MotorConversao
from core.configuracao import config_app
from core.historico import historico_app
from core.utils import get_resource_path

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
        self.geometry("1050x720")
        
        ctk.set_appearance_mode(config_app.get("tema") or "Dark")
        ctk.set_default_color_theme("blue")

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
        
        self.indice_arquivo_atual = -1
        self.indice_pagina_atual = -1

        self.criar_barra_lateral()
        self.criar_telas()
        self.mostrar_tela("inicio")
        self.atualizar_interface_arquivos()

    def criar_barra_lateral(self):
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(5, weight=1) 

        try:
            caminho_logo = get_resource_path("logo.png")
            img_logo = ctk.CTkImage(light_image=Image.open(caminho_logo), dark_image=Image.open(caminho_logo), size=(35, 35)) 
            self.logo_label = ctk.CTkLabel(self.sidebar, text=" PDF a MD\nConverter", image=img_logo, compound="left", font=ctk.CTkFont(size=20, weight="bold"))
        except Exception:
            self.logo_label = ctk.CTkLabel(self.sidebar, text="📄 PDF a MD\nConverter", font=ctk.CTkFont(size=20, weight="bold"))
        
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 30))

        self.btn_inicio = ctk.CTkButton(self.sidebar, text="🏠 Início", anchor="w", fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), command=lambda: self.mostrar_tela("inicio"))
        self.btn_inicio.grid(row=1, column=0, padx=20, pady=5, sticky="ew")

        self.btn_projetos = ctk.CTkButton(self.sidebar, text="📁 Meus Projetos", anchor="w", fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), command=lambda: self.mostrar_tela("projetos"))
        self.btn_projetos.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.btn_configs = ctk.CTkButton(self.sidebar, text="⚙️ Configurações", anchor="w", fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), command=lambda: self.mostrar_tela("configs"))
        self.btn_configs.grid(row=3, column=0, padx=20, pady=5, sticky="ew")

        texto_creditos = "Desenvolvedor:\nMaxwell Barros Veras de Araujo\n\nSuporte:\nmaxwellbvras@gmail.com"
        self.lbl_creditos_sidebar = ctk.CTkLabel(self.sidebar, text=texto_creditos, font=ctk.CTkFont(size=11), text_color="gray50", justify="center")
        self.lbl_creditos_sidebar.grid(row=6, column=0, padx=10, pady=(20, 20), sticky="s")

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

    def remover_arquivo(self, caminho):
        if caminho in self.arquivos_selecionados:
            self.arquivos_selecionados.remove(caminho)
            self.atualizar_interface_arquivos()

    def gerar_preview_imagem(self, caminho_pdf, num_pagina=0):
        """Gera e reutiliza previews de páginas para reduzir o custo de renderização."""
        chave_cache = (str(pathlib.Path(caminho_pdf)), int(num_pagina))
        if chave_cache in self._preview_cache:
            return self._preview_cache[chave_cache]

        try:
            doc = fitz.open(caminho_pdf)
            num_pagina = min(num_pagina, len(doc) - 1)
            pagina = doc.load_page(num_pagina)
            pix = pagina.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()
            self._preview_cache[chave_cache] = img
            return img
        except Exception:
            return None

    def atualizar_interface_arquivos(self):
        for widget in self.tela_inicio.frame_galeria.winfo_children():
            if widget != self.tela_inicio.linha_scanner:
                widget.destroy()
        
        self.raw_thumbnails.clear()
        qtd = len(self.arquivos_selecionados)

        if qtd == 0:
            self.tela_inicio.lbl_arquivo_selecionado.configure(text="0 arquivos prontos")
            self.tela_inicio.btn_converter.configure(state="disabled")

            area_drop = ctk.CTkButton(
                self.tela_inicio.frame_galeria,
                text="\n\n📂\n\nArraste e solte seus PDFs aqui\nou use os botões abaixo\n\n",
                fg_color="transparent", hover_color="#27272a", border_width=2,
                border_color="#3f3f46", text_color="gray", command=self.selecionar_pdf
            )
            area_drop.grid(row=0, column=0, columnspan=2, rowspan=2, sticky="nsew", padx=20, pady=20)
            try:
                area_drop.drop_target_register(DND_FILES)
                area_drop.dnd_bind('<<Drop>>', self.ao_soltar_arquivos)
            except: pass
            return

        self.tela_inicio.lbl_arquivo_selecionado.configure(text=f"Total: {qtd} arquivo(s) na fila de conversão")
        self.tela_inicio.btn_converter.configure(state="normal")
        self.tela_inicio.lbl_status.configure(text="Pronto para iniciar.", text_color="gray")

        max_previews = min(4, qtd)
        posicoes = [(0, 0), (0, 1), (1, 0), (1, 1)]

        for i in range(max_previews):
            caminho = self.arquivos_selecionados[i]
            img_pil = self.gerar_preview_imagem(caminho)
            
            if img_pil:
                self.raw_thumbnails.append(img_pil)
                ctk_img = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(140, 198))

                card = ctk.CTkFrame(self.tela_inicio.frame_galeria, fg_color="transparent")
                row, col = posicoes[i]
                card.grid(row=row, column=col, padx=10, pady=10, sticky="n")

                folha = ctk.CTkFrame(card, fg_color="white", corner_radius=0, border_width=1, border_color="#cccccc")
                folha.pack(pady=(15, 5), padx=10)
                
                lbl_img = ctk.CTkLabel(folha, text="", image=ctk_img)
                lbl_img.pack(padx=4, pady=4) 

                nome_curto = pathlib.Path(caminho).name
                if len(nome_curto) > 18: nome_curto = nome_curto[:15] + "..."
                
                lbl_txt = ctk.CTkLabel(card, text=nome_curto, text_color="#a1a1aa", font=ctk.CTkFont(size=11, weight="bold"))
                lbl_txt.pack()

                btn_remover = ctk.CTkButton(folha, text="✕", width=22, height=22, corner_radius=11,
                                            fg_color="#ef4444", hover_color="#b91c1c", text_color="white",
                                            bg_color="white", 
                                            font=ctk.CTkFont(size=11, weight="bold"),
                                            command=lambda c=caminho: self.remover_arquivo(c))
                btn_remover.place(relx=1.0, rely=0.0, x=-2, y=2, anchor="ne")

        if qtd > 4:
            frame_aviso = ctk.CTkFrame(self.tela_inicio.frame_galeria, fg_color="#3b82f6", corner_radius=15, height=30)
            frame_aviso.place(relx=0.5, rely=0.96, anchor="center")
            lbl_extra = ctk.CTkLabel(frame_aviso, text=f"+ {qtd - 4} arquivo(s) na fila", text_color="white", font=ctk.CTkFont(size=12, weight="bold"))
            lbl_extra.pack(padx=15, pady=2)

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

        # Scanner agora é renderizado em TAMANHO GIGANTE (340x480)
        if self.raw_thumbnails:
            img_grande = ctk.CTkImage(light_image=self.raw_thumbnails[0], dark_image=self.raw_thumbnails[0], size=(340, 480))
            nome_arq = pathlib.Path(self.arquivos_selecionados[0]).name
            self.tela_inicio.iniciar_scanner(img_grande, f"{nome_arq}")

        modo_selecionado = self.tela_inicio.opt_modo.get()
        modo_selecionado = normalizar_modo_conversao(modo_selecionado)
        config_app.set("modo_conversao", modo_selecionado)

        # OCR é desativado no modo de referência de imagem para acelerar processos grandes.
        usar_ocr = modo_selecionado != MODO_REFERENCIA_IMAGEM

        self.motor_conversao = MotorConversao(
            arquivos=self.arquivos_selecionados,
            pasta_destino=self.pasta_destino,
            usar_ocr=usar_ocr,
            cb_progresso=self.atualizar_progresso,
            cb_concluido=self.conversao_concluida,
            cb_erro=self.conversao_erro
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
                        # Scanner gera a imagem 70% maior que antes (340x480)
                        img_grande = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(340, 480))
                        nome_arq = pathlib.Path(caminho_atual).name
                        self.tela_inicio.atualizar_imagem_scanner(img_grande, f"{nome_arq} (Pág {idx_pagina+1})")

        if texto_novo:
            self.tela_inicio.textbox_preview.configure(state="normal")
            self.tela_inicio.textbox_preview.insert("end", texto_novo + "\n")
            self.tela_inicio.textbox_preview.see("end")
            self.tela_inicio.textbox_preview.configure(state="disabled")

    def conversao_concluida(self):
        self.tela_inicio.parar_scanner() 
        
        for arquivo in self.arquivos_selecionados:
            nome_original = pathlib.Path(arquivo).stem
            pasta_base = pathlib.Path(self.pasta_destino) if self.pasta_destino else pathlib.Path(arquivo).parent
            caminho_saida = str(pasta_base / (nome_original + ".md"))
            historico_app.adicionar_projeto(pathlib.Path(arquivo).name, caminho_saida)

        self.tela_inicio.progressbar.set(1) 
        self.tela_inicio.lbl_status.configure(text="✅ Concluído com Sucesso!", text_color="#16a34a")
        self.tela_inicio.btn_converter.configure(state="normal")
        self.tela_inicio.btn_cancelar.grid_remove() 
        self.tela_inicio.btn_cancelar.configure(state="normal", text="❌ Cancelar") 
        messagebox.showinfo("Sucesso", "A conversão foi finalizada perfeitamente!")

    def conversao_erro(self, erro, cancelado=False):
        self.tela_inicio.parar_scanner()
        self.tela_inicio.btn_converter.configure(state="normal")
        self.tela_inicio.btn_cancelar.grid_remove()
        self.tela_inicio.btn_cancelar.configure(state="normal", text="❌ Cancelar") 
        
        if cancelado:
            self.tela_inicio.lbl_status.configure(text="⚠️ Conversão Interrompida", text_color="#ca8a04")
            messagebox.showwarning("Cancelado", "A conversão foi cancelada pelo usuário.\nO que já havia sido lido foi salvo.")
        else:
            self.tela_inicio.lbl_status.configure(text="❌ Erro na conversão", text_color="red")
            messagebox.showerror("Erro Crítico", f"Falha ao processar:\n\n{erro}")

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

if __name__ == "__main__":
    # Necessário no Windows (especialmente em executáveis PyInstaller) para
    # que subprocessos de multiprocessing não executem a GUI novamente.
    freeze_support()
    app = App()
    app.mainloop()