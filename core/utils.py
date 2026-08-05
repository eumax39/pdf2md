import logging
import pathlib
import sys
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

def configurar_logs():
    """Configura o sistema de logs diários na pasta /logs"""
    pasta_logs = get_app_root() / "logs"
    pasta_logs.mkdir(exist_ok=True) # Garante que a pasta existe
    
    # Cria um arquivo de log com a data de hoje
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    caminho_log = pasta_logs / f"{data_hoje}.log"
    
    # Configuração do formato da mensagem de erro
    logging.basicConfig(
        filename=caminho_log,
        level=logging.ERROR, # Grava apenas erros e exceções
        format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
        datefmt='%d/%m/%Y %H:%M:%S'
    )
    
    return logging.getLogger("PDF2MD")

# Instância do logger para capturarmos os erros
logger = configurar_logs()

def log_erro(mensagem, excecao=None):
    """Função utilitária rápida para gravar erros de forma limpa."""
    if excecao:
        logger.error(f"{mensagem} | Detalhe: {str(excecao)}", exc_info=True)
    else:
        logger.error(mensagem)