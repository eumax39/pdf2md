import pathlib
import json
import sys
from unittest.mock import MagicMock

# Mock paddleocr if not installed in current pytest runner env
if 'paddleocr' not in sys.modules:
    sys.modules['paddleocr'] = MagicMock()

import pytest
from core.conversor import MotorConversao
from core.utils import get_data_root

def test_registrar_manifesto_centralizado(tmp_path):
    pasta_destino_usuario = tmp_path / "saida_usuario"
    pasta_destino_usuario.mkdir()

    motor = MotorConversao(
        arquivos=[],
        pasta_destino=str(pasta_destino_usuario),
        usar_ocr=True,
        cb_progresso=None,
        cb_concluido=None,
        cb_erro=None
    )
    resumo_mock = {"test": True, "total": 1}
    
    caminho_manifesto = motor._registrar_manifesto(str(pasta_destino_usuario), resumo_mock)
    
    assert caminho_manifesto is not None
    assert pathlib.Path(caminho_manifesto).exists()
    
    # Garantir que o manifesto está dentro da pasta central de dados da aplicação em 'manifestos'
    assert get_data_root() / "manifestos" in pathlib.Path(caminho_manifesto).parents
    
    # Garantir que NENHUM arquivo .json foi criado na pasta de saída do usuário
    json_na_pasta_usuario = list(pasta_destino_usuario.glob("*.json"))
    assert len(json_na_pasta_usuario) == 0, "Nenhum arquivo JSON deve ser deixado na pasta de saída do usuário"
    
    # Validar conteúdo do manifesto
    conteudo = json.loads(pathlib.Path(caminho_manifesto).read_text(encoding="utf-8"))
    assert conteudo["pasta_destino"] == str(pasta_destino_usuario)
    assert conteudo["resumo"] == resumo_mock
