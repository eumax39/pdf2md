import os
import pathlib
import platform
import shutil
import sys
import tempfile
import traceback
from datetime import datetime

from core.utils import get_app_root, get_data_root, caminho_log_atual, log_info
from core.version import APP_VERSION


def _versao_pacote(modulo):
    try:
        mod = __import__(modulo)
        return str(getattr(mod, "__version__", "instalado"))
    except Exception as e:
        return f"indisponível ({type(e).__name__})"


def executar_healthcheck(ocr_engine=None):
    checks = {}
    checks["PyMuPDF"] = _versao_pacote("fitz")
    checks["Pillow"] = _versao_pacote("PIL")
    checks["CustomTkinter"] = _versao_pacote("customtkinter")

    # Escrita e temporários
    try:
        pasta = get_data_root()
        teste = pasta / ".healthcheck_write"
        teste.write_text("ok", encoding="utf-8")
        teste.unlink(missing_ok=True)
        checks["Escrita"] = "OK"
    except Exception as e:
        checks["Escrita"] = f"FALHA ({e})"

    try:
        with tempfile.NamedTemporaryFile(prefix="pdf2md_", delete=True):
            pass
        checks["Temporários"] = "OK"
    except Exception as e:
        checks["Temporários"] = f"FALHA ({e})"

    if ocr_engine is not None:
        try:
            indisponivel = (getattr(ocr_engine, "motor", None) == "ERRO") or bool(getattr(ocr_engine, "_desabilitado", False))
            checks["OCR"] = "Indisponível" if indisponivel else "OK"
            detalhe = str(getattr(ocr_engine, "_ultimo_erro_init", "") or "")
            if detalhe:
                checks["OCR detalhe"] = detalhe[:300]
        except Exception as e:
            checks["OCR"] = f"Falha ao consultar ({e})"
    else:
        checks["OCR"] = "Não testado"

    return checks


def texto_diagnostico(ocr_engine=None):
    checks = executar_healthcheck(ocr_engine)
    linhas = [
        "PDF2MD - Diagnóstico técnico",
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"Versão do aplicativo: {APP_VERSION}",
        f"Executável congelado: {'Sim' if getattr(sys, 'frozen', False) else 'Não'}",
        f"Python: {platform.python_version()} ({platform.architecture()[0]})",
        f"Sistema: {platform.platform()}",
        f"Pasta do aplicativo: {get_app_root()}",
        f"Pasta de dados: {get_data_root()}",
        f"Log atual: {caminho_log_atual()}",
        "",
        "Verificações:",
    ]
    for nome, valor in checks.items():
        linhas.append(f"- {nome}: {valor}")
    return "\n".join(linhas)


def salvar_crash_report(exc_type, exc_value, exc_tb):
    pasta = get_data_root() / "crash_reports"
    pasta.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = pasta / f"crash_{carimbo}.txt"
    texto = (
        texto_diagnostico(None)
        + "\n\nExceção não tratada:\n"
        + "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    )
    caminho.write_text(texto, encoding="utf-8")
    log_info(f"Crash report salvo em {caminho}")
    return caminho
