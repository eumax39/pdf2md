import logging
import pathlib
from datetime import datetime

def configurar_logs():
    """Configura o sistema de logs diários na pasta /logs"""
    pasta_logs = pathlib.Path(__file__).parent.parent / "logs"
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