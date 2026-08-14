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


def get_data_root():
    """Pasta gravável para logs/diagnósticos, com fallback seguro.

    Mantém compatibilidade com instalações antigas ao preferir a pasta do app
    quando ela for gravável; caso contrário usa LOCALAPPDATA/TEMP.
    """
    candidatos = [get_app_root()]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidatos.append(pathlib.Path(local) / "PDF2MD")
    candidatos.append(pathlib.Path(tempfile.gettempdir()) / "PDF2MD")

    for pasta in candidatos:
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            teste = pasta / ".write_test"
            teste.write_text("ok", encoding="utf-8")
            teste.unlink(missing_ok=True)
            return pasta
        except Exception:
            continue
    return pathlib.Path(tempfile.gettempdir())


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
