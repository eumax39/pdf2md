# core/updater.py

from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

import requests
from packaging.version import InvalidVersion, Version

from core.version import APP_NAME, APP_VERSION, REPO_NAME, REPO_OWNER


class Atualizador:
    """Atualizador baseado em GitHub Releases.

    Fluxo esperado:
    1. Consulta ``/releases/latest`` do repositório público.
    2. Compara a tag do release (ex.: ``v2.0.1``) com ``APP_VERSION``.
    3. Seleciona o instalador Inno Setup anexado ao release.
    4. Baixa para uma pasta temporária, valida tamanho e SHA-256 quando
       o GitHub disponibilizar o digest do asset.
    5. O chamador inicia o instalador e encerra o aplicativo.
    """

    API_BASE = "https://api.github.com"
    CACHE_SEGUNDOS = 3600

    def __init__(self):
        self.versao_atual = APP_VERSION
        self.api_url = (
            f"{self.API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
        )
        self._cache_resultado = None
        self._ultima_verificacao = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "User-Agent": f"{APP_NAME.replace(' ', '-')}/{APP_VERSION}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    @staticmethod
    def _normalizar_tag(tag: str) -> str:
        tag = (tag or "").strip()
        if tag.lower().startswith("v"):
            tag = tag[1:]
        return tag.strip()

    def verificar(self, timeout: int = 10, force: bool = False):
        """Verifica se há uma versão estável mais nova no GitHub.

        Retorna um dicionário com as informações do release ou ``None``.
        Falhas de rede não interrompem a inicialização do aplicativo.
        """
        agora = time.time()

        if (
            not force
            and self._cache_resultado is not None
            and (agora - self._ultima_verificacao) < self.CACHE_SEGUNDOS
        ):
            return self._cache_resultado

        try:
            response = self.session.get(self.api_url, timeout=(5, timeout))
            response.raise_for_status()
            data = response.json()

            tag_original = data.get("tag_name", "")
            ultima_versao = self._normalizar_tag(tag_original)
            if not ultima_versao:
                self._ultima_verificacao = agora
                self._cache_resultado = None
                return None

            try:
                versao_remota = Version(ultima_versao)
                versao_local = Version(self.versao_atual)
            except InvalidVersion:
                self._ultima_verificacao = agora
                self._cache_resultado = None
                return None

            # O endpoint /latest já ignora drafts/prereleases; a checagem abaixo
            # é uma proteção adicional caso o formato da resposta mude.
            if data.get("draft") or data.get("prerelease"):
                self._ultima_verificacao = agora
                self._cache_resultado = None
                return None

            if versao_remota > versao_local:
                result = {
                    "versao": ultima_versao,
                    "tag": tag_original,
                    "assets": data.get("assets", []) or [],
                    "body": data.get("body", "") or "",
                    "html_url": data.get("html_url", "") or "",
                    "published_at": data.get("published_at", "") or "",
                }
                self._cache_resultado = result
                self._ultima_verificacao = agora
                return result

            self._cache_resultado = None
            self._ultima_verificacao = agora
            return None

        except requests.RequestException:
            # Atualização nunca deve impedir o programa de abrir.
            return None
        except Exception:
            return None

    @staticmethod
    def selecionar_instalador(assets):
        """Seleciona com segurança o instalador .exe do Release.

        Preferência:
        - nomes contendo ``setup``, ``installer`` ou ``instalador``;
        - nomes contendo ``pdf2md``;
        - se houver somente um .exe, ele é usado como fallback.

        Evita assets com nomes típicos de portable/uninstaller.
        """
        executaveis = []
        for asset in assets or []:
            nome = str(asset.get("name", "") or "")
            url = str(asset.get("browser_download_url", "") or "")
            if not nome or not url or not nome.lower().endswith(".exe"):
                continue

            baixo = nome.lower()
            if any(x in baixo for x in ("unins", "uninstall", "desinstal")):
                continue

            pontos = 0
            if "pdf2md" in baixo or "pdf_2_md" in baixo or "pdf-2-md" in baixo:
                pontos += 30
            if "setup" in baixo:
                pontos += 100
            if "installer" in baixo or "instalador" in baixo:
                pontos += 90
            if "portable" in baixo:
                pontos -= 100

            executaveis.append((pontos, asset))

        if not executaveis:
            return None

        executaveis.sort(key=lambda item: item[0], reverse=True)
        melhor_pontuacao, melhor = executaveis[0]

        # Se existe apenas um .exe no release, aceitá-lo mesmo com nome genérico.
        if len(executaveis) == 1:
            return melhor

        # Com vários executáveis, só escolher automaticamente um instalador claro.
        if melhor_pontuacao >= 90:
            return melhor
        return None

    @staticmethod
    def _digest_sha256(asset) -> Optional[str]:
        """Extrai ``sha256:<hash>`` do campo digest quando disponível."""
        digest = str((asset or {}).get("digest", "") or "").strip()
        if not digest:
            return None
        prefixo, sep, valor = digest.partition(":")
        if sep and prefixo.lower() == "sha256" and len(valor) == 64:
            return valor.lower()
        return None

    def baixar_instalador(
        self,
        asset,
        versao: str,
        callback_progress: Optional[Callable[[float], None]] = None,
        timeout_download: int = 120,
    ) -> Path:
        """Baixa e valida o instalador do Release.

        O arquivo só recebe o nome final depois que o download é concluído.
        Retorna o caminho local do instalador pronto para execução.
        """
        if not asset:
            raise RuntimeError("Asset do instalador não informado.")

        asset_url = str(asset.get("browser_download_url", "") or "").strip()
        nome_arquivo = Path(str(asset.get("name", "") or "PDF2MD_Setup.exe")).name
        if not asset_url or not nome_arquivo.lower().endswith(".exe"):
            raise RuntimeError("Instalador inválido no GitHub Release.")

        versao_segura = "".join(c for c in str(versao) if c.isalnum() or c in ".-_") or "latest"
        temp_dir = Path(tempfile.gettempdir()) / "PDF2MD_Update" / versao_segura
        temp_dir.mkdir(parents=True, exist_ok=True)

        caminho_final = temp_dir / nome_arquivo
        caminho_parcial = temp_dir / f"{nome_arquivo}.part"

        # Evita aproveitar um download parcial antigo.
        try:
            if caminho_parcial.exists():
                caminho_parcial.unlink()
        except OSError:
            pass

        hash_arquivo = hashlib.sha256()
        tamanho_esperado = int(asset.get("size", 0) or 0)
        total_header = 0
        downloaded = 0

        try:
            with self.session.get(
                asset_url,
                stream=True,
                timeout=(10, timeout_download),
                allow_redirects=True,
            ) as response:
                response.raise_for_status()
                try:
                    total_header = int(response.headers.get("content-length", 0) or 0)
                except (TypeError, ValueError):
                    total_header = 0

                total_para_progresso = tamanho_esperado or total_header

                with caminho_parcial.open("wb") as arquivo:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if not chunk:
                            continue
                        arquivo.write(chunk)
                        hash_arquivo.update(chunk)
                        downloaded += len(chunk)

                        if callback_progress and total_para_progresso > 0:
                            progresso = min(100.0, (downloaded / total_para_progresso) * 100.0)
                            callback_progress(progresso)

            if downloaded <= 0:
                raise RuntimeError("O GitHub retornou um instalador vazio.")

            if tamanho_esperado and downloaded != tamanho_esperado:
                raise RuntimeError(
                    f"Download incompleto: esperado {tamanho_esperado} bytes, recebido {downloaded}."
                )

            digest_esperado = self._digest_sha256(asset)
            if digest_esperado and hash_arquivo.hexdigest().lower() != digest_esperado:
                raise RuntimeError("Falha na validação SHA-256 do instalador baixado.")

            if caminho_final.exists():
                caminho_final.unlink()
            caminho_parcial.replace(caminho_final)

            if callback_progress:
                callback_progress(100.0)

            return caminho_final

        except Exception:
            try:
                if caminho_parcial.exists():
                    caminho_parcial.unlink()
            except OSError:
                pass
            raise

    @staticmethod
    def _preparar_ambiente_externo_windows():
        """Evita que um subprocesso externo herde o diretório de DLL do PyInstaller."""
        if sys.platform != "win32" or not getattr(sys, "frozen", False):
            return
        try:
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        except Exception:
            pass

    def executar_instalador(self, caminho_instalador: Path) -> subprocess.Popen:
        """Inicia o Inno Setup em modo silencioso e retorna o processo criado.

        O encerramento do PDF2MD é responsabilidade da interface principal,
        para que ocorra na thread do Tk e não em uma worker thread.
        """
        caminho = Path(caminho_instalador)
        if not caminho.exists() or caminho.suffix.lower() != ".exe":
            raise FileNotFoundError(f"Instalador não encontrado: {caminho}")

        self._preparar_ambiente_externo_windows()

        argumentos = [
            str(caminho),
            "/SILENT",
            "/SUPPRESSMSGBOXES",
            "/CLOSEAPPLICATIONS",
            "/RESTARTAPPLICATIONS",
        ]

        creationflags = 0
        if sys.platform == "win32":
            creationflags = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
            )

        return subprocess.Popen(
            argumentos,
            shell=False,
            cwd=str(caminho.parent),
            close_fds=(sys.platform != "win32"),
            creationflags=creationflags,
            env=os.environ.copy(),
        )

    # Compatibilidade com chamadas antigas. Não encerra a aplicação aqui.
    def baixar_e_instalar(
        self,
        asset_url,
        nome_arquivo=None,
        callback_progress=None,
    ):
        asset = {
            "browser_download_url": asset_url,
            "name": nome_arquivo or "PDF2MD_Setup.exe",
        }
        caminho = self.baixar_instalador(
            asset=asset,
            versao="latest",
            callback_progress=callback_progress,
        )
        self.executar_instalador(caminho)
        return True
