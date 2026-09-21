import logging
from logging.handlers import RotatingFileHandler
import pathlib
import sys
import os
import tempfile
from datetime import datetime


def get_app_root():
    """Retorna a pasta base da aplicação, tanto no código-fonte quanto no executável."""
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).parent.parent.resolve()


def get_resource_root():
    """Retorna a pasta de recursos empacotados em execução congelada ou a raiz do projeto."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return pathlib.Path(meipass)
    return get_app_root()


def get_resource_path(*parts):
    return get_resource_root().joinpath(*parts)


_DATA_ROOT_CACHE = None


def get_data_root():
    """Pasta gravável para logs/diagnósticos, configurações e histórico com fallback seguro.

    Mantém compatibilidade com instalações antigas ao preferir a pasta do app
    quando ela for gravável; caso contrário usa LOCALAPPDATA/APPDATA/TEMP.
    """
    global _DATA_ROOT_CACHE
    if _DATA_ROOT_CACHE is not None:
        return _DATA_ROOT_CACHE

    candidatos = [get_app_root()]
    local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if local:
        candidatos.append(pathlib.Path(local) / "PDF2MD")
    candidatos.append(pathlib.Path(tempfile.gettempdir()) / "PDF2MD")

    for pasta in candidatos:
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            teste = pasta / ".write_test"
            teste.write_text("ok", encoding="utf-8")
            teste.unlink(missing_ok=True)
            _DATA_ROOT_CACHE = pasta
            return pasta
        except Exception:
            continue
    _DATA_ROOT_CACHE = pathlib.Path(tempfile.gettempdir())
    return _DATA_ROOT_CACHE


def get_logs_dir():
    pasta = get_data_root() / "logs"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def configurar_logs():
    """Logs rotativos de operação, sem registrar conteúdo extraído dos PDFs."""
    logger = logging.getLogger("PDF2MD")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    caminho_log = get_logs_dir() / "pdf2md.log"
    handler = RotatingFileHandler(
        caminho_log,
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
    ))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = configurar_logs()


def log_info(mensagem):
    logger.info(str(mensagem))


def log_aviso(mensagem):
    logger.warning(str(mensagem))


def log_erro(mensagem, excecao=None):
    """Registra exceção técnica. Evite passar conteúdo extraído como mensagem."""
    if excecao:
        logger.error(f"{mensagem} | {type(excecao).__name__}: {excecao}", exc_info=True)
    else:
        logger.error(str(mensagem))


def caminho_log_atual():
    return get_logs_dir() / "pdf2md.log"


def calcular_tamanho_limpeza_temporarios():
    """Calcula o tamanho total em bytes de arquivos temporários e logs antigos (> 7 dias)."""
    import time
    total_bytes = 0
    arquivos_para_remover = []
    agora = time.time()
    limite_idade = 7 * 86400  # 7 dias

    pastas_temp = [
        get_data_root() / "temp",
        pathlib.Path.home() / ".paddlex" / "temp",
        pathlib.Path(tempfile.gettempdir()) / "PDF2MD",
    ]

    for pasta in pastas_temp:
        if pasta.exists():
            for item in pasta.rglob("*"):
                if item.is_file():
                    try:
                        sz = item.stat().st_size
                        total_bytes += sz
                        arquivos_para_remover.append(item)
                    except Exception:
                        pass

    pasta_logs = get_logs_dir()
    if pasta_logs.exists():
        for item in pasta_logs.glob("*.log.*"):
            if item.is_file():
                try:
                    if (agora - item.stat().st_mtime) > limite_idade:
                        sz = item.stat().st_size
                        total_bytes += sz
                        arquivos_para_remover.append(item)
                except Exception:
                    pass

    return total_bytes, arquivos_para_remover


def executar_limpeza_temporarios(arquivos=None):
    """Executa a remoção segura de arquivos temporários e logs desatualizados."""
    if arquivos is None:
        _, arquivos = calcular_tamanho_limpeza_temporarios()

    liberados = 0
    for arq in arquivos:
        try:
            sz = arq.stat().st_size
            arq.unlink(missing_ok=True)
            liberados += sz
        except Exception:
            pass

    return liberados
