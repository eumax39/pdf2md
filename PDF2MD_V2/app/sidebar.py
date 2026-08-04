import customtkinter as ctk

class Sidebar(ctk.CTkFrame):
    def __init__(self, master, comando_navegacao, **kwargs):
        # Inicializa o Frame da barra lateral
        super().__init__(master, width=200, corner_radius=0, **kwargs)
        
        self.comando_navegacao = comando_navegacao
        self.grid_rowconfigure(5, weight=1) # Empurra os créditos para o fundo

        # --- LOGO ---
        ctk.CTkLabel(self, text="📄 PDF a MD\nConverter", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 30))

        # --- BOTÕES DE NAVEGAÇÃO ---
        self.btn_inicio = ctk.CTkButton(self, text="🏠 Início", anchor="w", fg_color="#1f538d", command=lambda: self.clicar("inicio"))
        self.btn_inicio.grid(row=1, column=0, padx=20, pady=5, sticky="ew")

        self.btn_projetos = ctk.CTkButton(self, text="📁 Meus Projetos", anchor="w", fg_color="transparent", command=lambda: self.clicar("projetos"))
        self.btn_projetos.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.btn_configs = ctk.CTkButton(self, text="⚙️ Configurações", anchor="w", fg_color="transparent", command=lambda: self.clicar("configs"))
        self.btn_configs.grid(row=3, column=0, padx=20, pady=5, sticky="ew")

        # --- CRÉDITOS ---
        texto_creditos = "Desenvolvedor:\nMaxwell Barros Veras de Araujo\n\nSuporte:\nmaxwellbvras@gmail.com"
        ctk.CTkLabel(self, text=texto_creditos, font=ctk.CTkFont(size=11), text_color="gray50", justify="center").grid(row=6, column=0, padx=10, pady=(20, 20), sticky="s")

    def clicar(self, nome_tela):
        """Atualiza a cor dos botões e avisa a interface principal para mudar a tela."""
        # Reseta todas as cores
        self.btn_inicio.configure(fg_color="transparent")
        self.btn_projetos.configure(fg_color="transparent")
        self.btn_configs.configure(fg_color="transparent")

        # Pinta apenas o botão clicado
        if nome_tela == "inicio":
            self.btn_inicio.configure(fg_color="#1f538d")
        elif nome_tela == "projetos":
            self.btn_projetos.configure(fg_color="#1f538d")
        elif nome_tela == "configs":
            self.btn_configs.configure(fg_color="#1f538d")

        # Aciona o comando de mudar a tela principal
        self.comando_navegacao(nome_tela)