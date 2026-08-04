import customtkinter as ctk
from tkinter import messagebox
from tkinterdnd2 import TkinterDnD

from core.configuracao import config_app
from core.historico import historico_app
from core.utils import log_erro

from app.sidebar import Sidebar
from app.telas import TelaInicio, TelaProjetos, TelaConfigs
from app.eventos import GerenciadorEventos

class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        
        try:
            self.TkdndVersion = TkinterDnD._require(self)
        except Exception as e:
            log_erro("Falha ao iniciar o TkinterDnD", e)
            
        self.title("PDF ➡️ MD Converter Pro - V2.0")
        self.geometry("980x680")
        
        ctk.set_appearance_mode(config_app.get("tema"))
        ctk.set_default_color_theme("blue")
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 🌟 VARIÁVEIS DE ESTADO DA APLICAÇÃO
        self.arquivos_selecionados = []
        self.pasta_destino = None
        self.motor_ativo = None
        
        # 🌟 CÉREBRO DOS EVENTOS (Conecta os cliques ao Backend)
        self.eventos = GerenciadorEventos(self)
        
        # 1. Instancia a Barra Lateral
        self.sidebar = Sidebar(self, comando_navegacao=self.mudar_tela)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        # 2. Instancia as Telas Reais PLUGADAS AOS EVENTOS
        self.tela_inicio = TelaInicio(
            self,
            comando_selecionar_pdf=self.eventos.selecionar_pdf,
            comando_soltar_pdf=self.eventos.soltar_pdf,
            comando_pasta=self.eventos.selecionar_pasta,
            comando_converter=self.eventos.iniciar_conversao,
            comando_cancelar=self.eventos.cancelar_conversao
        )
        
        self.tela_projetos = TelaProjetos(
            self,
            comando_abrir_detalhes=self.abrir_detalhes_temporario
        )
        
        self.tela_configs = TelaConfigs(
            self,
            comando_mudar_tema=ctk.set_appearance_mode,
            comando_limpar_historico=self.limpar_historico
        )

        # 3. Posiciona todas as telas no mesmo "quadrado"
        for tela in (self.tela_inicio, self.tela_projetos, self.tela_configs):
            tela.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
            
        self.mudar_tela("inicio")

    def mudar_tela(self, nome_tela):
        self.tela_inicio.grid_remove()
        self.tela_projetos.grid_remove()
        self.tela_configs.grid_remove()
        
        if nome_tela == "inicio":
            self.tela_inicio.grid()
        elif nome_tela == "projetos":
            self.tela_projetos.carregar_lista()
            self.tela_projetos.grid()
        elif nome_tela == "configs":
            self.tela_configs.grid()

    # --- Comandos secundários para as outras abas ---
    def limpar_historico(self):
        if messagebox.askyesno("Aviso", "Tem certeza que deseja apagar todo o histórico do banco de dados?"):
            historico_app.limpar_historico()
            messagebox.showinfo("Sucesso", "O histórico foi apagado!")

    def abrir_detalhes_temporario(self, proj):
        # Em breve, criaremos a TelaDetalhes. Por enquanto, avisa que concluiu e está salvo.
        messagebox.showinfo("Projeto Salvo", f"O arquivo foi convertido e salvo em:\n\n{proj[3]}")