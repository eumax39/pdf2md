import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from core.conversor import MotorConversao
from core.configuracao import config_app

class FakeReader:
    total_paginas = 1
    def __init__(self, caminho):
        self.caminho = caminho
    def extrair_markdown_rapido(self, index):
        return ""
    def pagina_tem_texto_nativo(self, index):
        return False
    def extrair_imagem_da_pagina(self, index):
        return [[0, 0, 0], [255, 255, 255]]
    def fechar(self):
        pass

class FakeWriter:
    def __init__(self, caminho):
        self.caminho = caminho
    def escrever_pagina(self, texto):
        print('WRITE', repr(texto))

class FakeHistorico:
    def adicionar_projeto(self, nome, caminho):
        print('HIST', nome, caminho)

import core.conversor as conversor_mod
conversor_mod.PDFReader = FakeReader
conversor_mod.MarkdownWriter = FakeWriter
conversor_mod.historico_app = FakeHistorico()
conversor_mod.ocr_engine = type('OCR', (), {'ler_imagem': lambda self, img: 'texto reconhecido'})()

cfg = config_app
cfg.set('modo_conversao', 'Forçar OCR em Todas as Páginas')

motor = MotorConversao(
    arquivos=['dummy.pdf'],
    pasta_destino='.',
    usar_ocr=True,
    cb_progresso=lambda *args, **kwargs: None,
    cb_concluido=lambda: print('DONE'),
    cb_erro=lambda *args, **kwargs: None,
)
motor._processar_fila()
