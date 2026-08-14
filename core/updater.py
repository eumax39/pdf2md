# core/updater.py

import sys
import subprocess
import tempfile
import requests
from pathlib import Path
from packaging.version import Version
import time

# ==========================================
# CONFIGURAÇÃO DO REPOSITÓRIO
# ==========================================
REPO_OWNER = "eumax39"           # Seu usuário do GitHub
REPO_NAME = "pdf2md"             # Nome do repositório
VERSAO_ATUAL = "1.9.9"           # Versão atual (atualize sempre que fizer build)


class Atualizador:
    def __init__(self):
        self.versao_atual = VERSAO_ATUAL
        self.api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
        self._cache_resultado = None
        self._ultima_verificacao = 0

    def verificar(self, timeout=10, force=False):
        """
        Verifica se há uma nova versão disponível no GitHub.
        Retorna um dicionário com as informações ou None.
        """
        agora = time.time()

        # Cache de 1 hora para evitar muitas requisições
        if not force and self._cache_resultado and (agora - self._ultima_verificacao) < 3600:
            return self._cache_resultado

        try:
            response = requests.get(self.api_url, timeout=timeout)
            if response.status_code != 200:
                return None

            data = response.json()
            ultima_versao = data.get("tag_name", "").lstrip("v")

            if Version(ultima_versao) > Version(self.versao_atual):
                result = {
                    "versao": ultima_versao,
                    "assets": data.get("assets", []),
                    "body": data.get("body", ""),
                }
                self._cache_resultado = result
                self._ultima_verificacao = agora
                return result

            self._cache_resultado = None
            self._ultima_verificacao = agora
            return None

        except Exception:
            return None

    def baixar_e_instalar(self, asset_url, nome_arquivo=None, callback_progress=None):
        """
        Baixa o instalador do GitHub e o executa em modo silencioso.
        O programa atual é encerrado após iniciar a instalação.
        """
        try:
            if not nome_arquivo:
                nome_arquivo = "PDF2MD_Setup.exe"

            # Pasta temporária para o download
            temp_dir = Path(tempfile.gettempdir()) / "PDF2MD_Update"
            temp_dir.mkdir(exist_ok=True)
            caminho_instalador = temp_dir / nome_arquivo

            # Download com progresso (opcional)
            response = requests.get(asset_url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(caminho_instalador, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if callback_progress and total_size > 0:
                        callback_progress((downloaded / total_size) * 100)

            # Executa o instalador em modo silencioso
            # /SILENT é suportado pelo Inno Setup
            subprocess.Popen([str(caminho_instalador), "/SILENT"], shell=True)

            # Encerra o aplicativo atual
            sys.exit(0)

        except Exception as e:
            print(f"[Updater] Erro: {e}")
            return False