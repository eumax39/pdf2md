import customtkinter as ctk

class Sidebar(ctk.CTkFrame):
    def __init__(self, master, comando_navegacao, **kwargs):
        super().__init__(master, width=220, corner_radius=0, fg_color="#0b1118", border_width=1, border_color="#1e293b", **kwargs)
        
        self.comando_navegacao = comando_navegacao
        self.grid_rowconfigure(6, weight=1)

        # LOGO E TÍTULO
        frame_logo = ctk.CTkFrame(self, fg_color="transparent")
        frame_logo.grid(row=0, column=0, padx=16, pady=(24, 20), sticky="ew")
        
        ctk.CTkLabel(
            frame_logo, text="⚡ PDF2MD",
            font=ctk.CTkFont(size=22, weight="bold"), text_color="#2088ff"
        ).pack(anchor="w")
        ctk.CTkLabel(
            frame_logo, text="Conversor Processual v2.0",
            font=ctk.CTkFont(size=11), text_color="#8d99a8"
        ).pack(anchor="w")

        # BOTÕES DE NAVEGAÇÃO
        self.btn_inicio = ctk.CTkButton(
            self, text="  🏠  Início / Conversor", anchor="w", height=38,
            fg_color="#102a45", text_color="#ffffff", hover_color="#183b60",
            corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self.clicar("inicio")
        )
        self.btn_inicio.grid(row=1, column=0, padx=14, pady=4, sticky="ew")

        self.btn_projetos = ctk.CTkButton(
            self, text="  📁  Meus Projetos", anchor="w", height=38,
            fg_color="transparent", text_color="#a0aec0", hover_color="#151e29",
            corner_radius=8, font=ctk.CTkFont(size=13),
            command=lambda: self.clicar("projetos")
        )
        self.btn_projetos.grid(row=2, column=0, padx=14, pady=4, sticky="ew")

        self.btn_configs = ctk.CTkButton(
            self, text="  ⚙️  Configurações & IA", anchor="w", height=38,
            fg_color="transparent", text_color="#a0aec0", hover_color="#151e29",
            corner_radius=8, font=ctk.CTkFont(size=13),
            command=lambda: self.clicar("configs")
        )
        self.btn_configs.grid(row=3, column=0, padx=14, pady=4, sticky="ew")

        # CRÉDITOS E SUPORTE
        texto_creditos = "PDF2MD Pro v2.0\nAlmeida e Bandeira Adv.\nSuporte: maxwellbvras@gmail.com"
        ctk.CTkLabel(
            self, text=texto_creditos, font=ctk.CTkFont(size=10),
            text_color="#475569", justify="center"
        ).grid(row=7, column=0, padx=10, pady=(10, 16), sticky="s")

    def clicar(self, nome_tela):
        """Atualiza a cor dos botões e avisa a interface principal para mudar a tela."""
        for btn in (self.btn_inicio, self.btn_projetos, self.btn_configs):
            btn.configure(fg_color="transparent", text_color="#a0aec0", font=ctk.CTkFont(size=13))

        if nome_tela == "inicio":
            self.btn_inicio.configure(fg_color="#102a45", text_color="#ffffff", font=ctk.CTkFont(size=13, weight="bold"))
        elif nome_tela == "projetos":
            self.btn_projetos.configure(fg_color="#102a45", text_color="#ffffff", font=ctk.CTkFont(size=13, weight="bold"))
        elif nome_tela == "configs":
            self.btn_configs.configure(fg_color="#102a45", text_color="#ffffff", font=ctk.CTkFont(size=13, weight="bold"))

        self.comando_navegacao(nome_tela)