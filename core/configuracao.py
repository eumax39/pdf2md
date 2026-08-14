import json
import pathlib

from core.utils import get_app_root

class Configuracao:
    def __init__(self):
        # O arquivo config.json fica ao lado da aplicação quando empacotada.
        self.caminho_config = get_app_root() / "config.json"
        
        # Configurações padrão de fábrica
        self.configs = {
            "tema": "Dark",
            "pasta_padrao": "",
            "usar_ocr_hibrido": True,
            "idioma_ocr": "pt",
            "extrair_imagens": False,
            "dpi_leitura": 100,
            "threads_cpu": 2,
            "ocr_timeout_segundos": 40,
            "ocr_timeout_inicial_segundos": 120,
            "ocr_dpi_timeout_retry": 110,
            "imagem_ref_min_area_ratio": 0.04,
            "modo_compatibilidade": False,
            "gerar_manifesto_conversao": True
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