import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import pathlib
from core.conversor import MotorConversao
from core.configuracao import config_app

class GerenciadorEventos:
    def __init__(self, app):
        self.app = app # Guarda a referência da janela principal

    # --- EVENTOS DE SELEÇÃO DE ARQUIVOS ---
    def selecionar_pdf(self):
        arquivos = filedialog.askopenfilenames(filetypes=[("Arquivos PDF", "*.pdf")])
        if arquivos:
            self.app.arquivos_selecionados = list(arquivos)
            self._atualizar_label_arquivos()

    def soltar_pdf(self, event):
        # O módulo Drag&Drop envia os arquivos em formato de lista (string)
        pdfs = [f for f in self.app.tk.splitlist(event.data) if f.lower().endswith('.pdf')]
        if pdfs:
            self.app.arquivos_selecionados = pdfs
            self._atualizar_label_arquivos()
        else:
            messagebox.showwarning("Aviso", "Arraste apenas arquivos PDF.")

    def _atualizar_label_arquivos(self):
        qtd = len(self.app.arquivos_selecionados)
        tela = self.app.tela_inicio
        
        if qtd == 0:
            tela.lbl_arquivo_selecionado.configure(text="Nenhum arquivo selecionado")
            tela.btn_converter.configure(state="disabled")
        else:
            nome = pathlib.Path(self.app.arquivos_selecionados[0]).name
            texto = f"📄 {nome}" if qtd == 1 else f"📄 {qtd} arquivos selecionados"
            tela.lbl_arquivo_selecionado.configure(text=texto)
            tela.btn_converter.configure(state="normal")
            
        tela.lbl_status.configure(text="Pronto para converter.", text_color="gray")

    def selecionar_pasta(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.app.pasta_destino = pasta
            texto_pasta = pasta if len(pasta) < 35 else '...' + pasta[-32:]
            self.app.tela_inicio.lbl_caminho_destino.configure(text=f"Salvar em: {texto_pasta}")

    # --- EVENTOS DE CONVERSÃO ---
    def iniciar_conversao(self):
        if not self.app.arquivos_selecionados: return

        tela = self.app.tela_inicio
        # 1. Prepara a tela (Desativa botões, liga barra de progresso)
        tela.btn_converter.configure(state="disabled")
        tela.btn_cancelar.grid()
        tela.btn_cancelar.configure(state="normal", text="❌ Cancelar")
        tela.progressbar.set(0)
        tela.textbox_preview.configure(state="normal")
        tela.textbox_preview.delete("0.0", "end")
        tela.textbox_preview.configure(state="disabled")

        # 2. Pega o modo de conversão selecionado na interface
        modo_selecionado = self.app.tela_inicio.opt_modo.get()
        usar_ocr = True
        if modo_selecionado != "Forçar OCR em Todas as Páginas":
            usar_ocr = True

        # 3. Liga o motor pesado enviando os telefones de contato (callbacks)
        self.app.motor_ativo = MotorConversao(
            arquivos=self.app.arquivos_selecionados,
            pasta_destino=self.app.pasta_destino,
            usar_ocr=usar_ocr,
            cb_progresso=self.cb_progresso,
            cb_concluido=self.cb_concluido,
            cb_erro=self.cb_erro
        )
        self.app.motor_ativo.iniciar() # Dispara a Thread

    def cancelar_conversao(self):
        if self.app.motor_ativo:
            self.app.tela_inicio.btn_cancelar.configure(state="disabled", text="Cancelando...")
            self.app.motor_ativo.solicitar_cancelamento()

    # =====================================================================
    # CALLBACKS (Recebem sinais da Thread do Backend e mandam para a Tela)
    # Sempre usamos self.app.after() para não explodir a interface visual
    # =====================================================================
    def cb_progresso(self, msg, porcentagem, texto_extraido):
        self.app.after(0, self._atualizar_ui_progresso, msg, porcentagem, texto_extraido)

    def _atualizar_ui_progresso(self, msg, porcentagem, texto_extraido):
        tela = self.app.tela_inicio
        tela.lbl_status.configure(text=msg, text_color=("black", "white"))
        tela.progressbar.set(porcentagem)
        
        if texto_extraido.strip():
            # Mostra no máximo os últimos pedaços para não travar a textbox
            tela.textbox_preview.configure(state="normal")
            tela.textbox_preview.insert("end", texto_extraido)
            tela.textbox_preview.see("end")
            tela.textbox_preview.configure(state="disabled")

    def cb_concluido(self):
        self.app.after(0, self._finalizar_ui, "✅ Concluído com Sucesso!", "green")
        self.app.after(0, lambda: messagebox.showinfo("Sucesso", "A conversão foi finalizada!"))

    def cb_erro(self, msg, cancelado=False):
        if cancelado:
            self.app.after(0, self._finalizar_ui, "⚠️ Conversão Cancelada", "#ca8a04")
            self.app.after(0, lambda: messagebox.showwarning("Cancelado", msg))
        else:
            self.app.after(0, self._finalizar_ui, "❌ Erro na conversão", "red")
            self.app.after(0, lambda: messagebox.showerror("Erro", msg))

    def _finalizar_ui(self, msg_status, cor):
        tela = self.app.tela_inicio
        tela.lbl_status.configure(text=msg_status, text_color=cor)
        tela.progressbar.set(1)
        tela.btn_converter.configure(state="normal")
        tela.btn_cancelar.grid_remove()