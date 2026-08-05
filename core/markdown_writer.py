import pathlib

class MarkdownWriter:
    def __init__(self, caminho_saida):
        self.caminho_saida = pathlib.Path(caminho_saida)
        # Quando iniciado, limpa o arquivo antigo se existir, ou cria um novo vazio
        self.caminho_saida.write_text("", encoding="utf-8")

    def escrever_pagina(self, texto):
        """Adiciona o texto lido no final do arquivo sem sobrecarregar a RAM."""
        with open(self.caminho_saida, "a", encoding="utf-8") as f:
            f.write(texto + "\n\n")