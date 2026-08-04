import json
import pathlib

class Configuracao:
    def __init__(self):
        # O arquivo config.json ficará na raiz do projeto
        self.caminho_config = pathlib.Path(__file__).parent.parent / "config.json"
        
        # Configurações padrão de fábrica
        self.configs = {
            "tema": "Dark",
            "pasta_padrao": "",
            "usar_ocr_hibrido": True,
            "idioma_ocr": "pt",
            "extrair_imagens": False,
            "dpi_leitura": 100,
            "threads_cpu": 2
        }
        self.carregar()

    def carregar(self):
        """Lê o arquivo config.json. Se não existir, cria um com os padrões."""
        if self.caminho_config.exists():
            try:
                with open(self.caminho_config, "r", encoding="utf-8") as f:
                    configs_salvas = json.load(f)
                    self.configs.update(configs_salvas) # Atualiza os padrões com o que estava salvo
            except Exception as e:
                print(f"Erro ao ler configurações: {e}. Usando padrões.")
        else:
            self.salvar()

    def salvar(self):
        """Salva as configurações atuais no arquivo JSON."""
        try:
            with open(self.caminho_config, "w", encoding="utf-8") as f:
                json.dump(self.configs, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar configurações: {e}")

    def get(self, chave):
        """Pega uma configuração específica."""
        return self.configs.get(chave)

    def set(self, chave, valor):
        """Altera uma configuração e já salva no disco."""
        self.configs[chave] = valor
        self.salvar()

# Criamos uma instância global para ser importada por outras partes do programa
config_app = Configuracao()