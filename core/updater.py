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
from core.utils import get_app_root, log_info, log_aviso, log_erro


class Atualizador:
    """Atualizador baseado em GitHub Releases."""

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
        """Verifica se há uma versão estável mais nova no GitHub."""
        agora = time.time()
        log_info(f"[UPDATER] Checando atualizações no GitHub... (Local: {self.versao_atual})")

        if (
            not force
            and self._cache_resultado is not None
            and (agora - self._ultima_verificacao) < self.CACHE_SEGUNDOS
        ):
            log_info("[UPDATER] Retornando resultado da verificação do cache.")
            return self._cache_resultado

        try:
            log_info(f"[UPDATER] Solicitando GET em: {self.api_url}")
            response = self.session.get(self.api_url, timeout=(5, timeout))
            response.raise_for_status()
            data = response.json()

            tag_original = data.get("tag_name", "")
            ultima_versao = self._normalizar_tag(tag_original)
            log_info(f"[UPDATER] Resposta do GitHub: tag='{tag_original}' -> versão_normalizada='{ultima_versao}'")
            
            if not ultima_versao:
                self._ultima_verificacao = agora
                self._cache_resultado = None
                log_aviso("[UPDATER] Tag remota vazia ou inválida.")
                return None

            try:
                versao_remota = Version(ultima_versao)
                versao_local = Version(self.versao_atual)
            except InvalidVersion as ve:
                self._ultima_verificacao = agora
                self._cache_resultado = None
                log_erro(f"[UPDATER] Versão inválida ao comparar {ultima_versao} com {self.versao_atual}", ve)
                return None

            if data.get("draft") or data.get("prerelease"):
                self._ultima_verificacao = agora
                self._cache_resultado = None
                log_info("[UPDATER] Release remoto é um draft/prerelease. Ignorado.")
                return None

            if versao_remota > versao_local:
                assets = data.get("assets", []) or []
                log_info(f"[UPDATER] ✨ Nova versão encontrada! Remote {versao_remota} > Local {versao_local}. Assets disponíveis: {[a.get('name') for a in assets]}")
                result = {
                    "versao": ultima_versao,
                    "tag": tag_original,
                    "assets": assets,
                    "body": data.get("body", "") or "",
                    "html_url": data.get("html_url", "") or "",
                    "published_at": data.get("published_at", "") or "",
                }
                self._cache_resultado = result
                self._ultima_verificacao = agora
                return result

            log_info(f"[UPDATER] Aplicativo já está na versão mais recente ({versao_local} >= {versao_remota}).")
            self._cache_resultado = None
            self._ultima_verificacao = agora
            return None

        except requests.RequestException as re:
            log_aviso(f"[UPDATER] Falha na comunicação HTTP com o GitHub: {re}")
            return None
        except Exception as e:
            log_erro("[UPDATER] Erro inesperado ao verificar atualizações", e)
            return None

    @staticmethod
    def selecionar_instalador(assets):
        """Seleciona com segurança o instalador .exe do Release."""
        executaveis = []
        log_info(f"[UPDATER] Selecionando instalador entre {len(assets or [])} assets...")
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

            log_info(f"[UPDATER] Asset avaliado: name='{nome}', pontos={pontos}")
            executaveis.append((pontos, asset))

        if not executaveis:
            log_aviso("[UPDATER] Nenhum executável (.exe) adequado encontrado nos assets.")
            return None

        executaveis.sort(key=lambda item: item[0], reverse=True)
        melhor_pontuacao, melhor = executaveis[0]

        if len(executaveis) == 1:
            log_info(f"[UPDATER] Selecionado o único instalador disponível: '{melhor.get('name')}'")
            return melhor

        if melhor_pontuacao >= 90:
            log_info(f"[UPDATER] Selecionado o instalador com maior pontuação ({melhor_pontuacao}): '{melhor.get('name')}'")
            return melhor

        log_aviso(f"[UPDATER] Pontuação máxima ({melhor_pontuacao}) insuficiente para seleção automática entre múltiplos assets.")
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
        log_info(f"[UPDATER] Baixando instalador de '{asset_url}' para '{caminho_final}'...")

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

            log_info(f"[UPDATER] Download concluído com sucesso ({downloaded} bytes). Arquivo: {caminho_final}")
            return caminho_final

        except Exception as e:
            log_erro(f"[UPDATER] Falha durante o download do instalador de {asset_url}", e)
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
        """Inicia o Inno Setup no diretório atual do app e reabre a aplicação após a instalação."""
        caminho = Path(caminho_instalador)
        if not caminho.exists() or caminho.suffix.lower() != ".exe":
            log_erro(f"[UPDATER] Arquivo de instalador não encontrado: {caminho}")
            raise FileNotFoundError(f"Instalador não encontrado: {caminho}")

        self._preparar_ambiente_externo_windows()

        pasta_app = get_app_root()
        exe_app = pasta_app / "PDF2MD_V2.exe"

        argumentos = [
            str(caminho),
            f"/DIR={pasta_app}",
            "/SILENT",
            "/SUPPRESSMSGBOXES",
            "/CLOSEAPPLICATIONS",
            "/NORESTART",
        ]

        log_info(f"[UPDATER] Executando instalador silencioso: {caminho}")
        log_info(f"[UPDATER] Parâmetros de execução: {argumentos}")
        log_info(f"[UPDATER] Pasta do app a atualizar (/DIR): {pasta_app}")

        creationflags = 0
        if sys.platform == "win32":
            creationflags = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
            )

        proc = subprocess.Popen(
            argumentos,
            shell=False,
            cwd=str(caminho.parent),
            close_fds=(sys.platform != "win32"),
            creationflags=creationflags,
            env=os.environ.copy(),
        )

        if sys.platform == "win32" and exe_app.exists():
            cmd_relaunch = (
                f"Start-Sleep -Seconds 1; "
                f"Wait-Process -Id {proc.pid} -ErrorAction SilentlyContinue; "
                f"Start-Sleep -Seconds 1; "
                f"Start-Process -FilePath '{exe_app}'"
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", cmd_relaunch],
                creationflags=creationflags,
                close_fds=True,
            )

        return proc

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
