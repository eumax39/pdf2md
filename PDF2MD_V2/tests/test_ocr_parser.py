import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ocr.manager import GerenciadorOCR


def test_parser_extrai_texto_de_resultado_dict():
    gestor = GerenciadorOCR()
    resultado = [{
        'rec_texts': ['OCR', 'funcionando'],
        'rec_scores': [0.99, 0.97],
    }]

    texto = gestor._extrair_texto_do_resultado(resultado)
    assert texto == 'OCR funcionando'


def test_parser_extrai_texto_de_resultado_objeto():
    gestor = GerenciadorOCR()

    class ResultadoFake:
        def __init__(self):
            self.rec_texts = ['texto']
            self.rec_scores = [0.95]

    texto = gestor._extrair_texto_do_resultado([ResultadoFake()])
    assert texto == 'texto'


def test_parser_trata_resultado_vazio():
    gestor = GerenciadorOCR()
    assert gestor._extrair_texto_do_resultado([]) == ''


def test_parser_extra_texto_de_dict_aninhado():
    gestor = GerenciadorOCR()
    resultado = {'result': {'rec_texts': ['texto', 'aninhado']}}
    assert gestor._extrair_texto_do_resultado(resultado) == 'texto aninhado'
